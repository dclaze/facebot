#!/usr/bin/env python3
"""Optional owner-configured USB process watchdog; voice may remain on Wi-Fi.

Only an absent org.facebot process can be restarted. Never installs, changes
settings, reverses ports, wakes/unlocks, or steals focus from a running app.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time


class ConfigError(ValueError):
    pass


def load_config(path):
    path = Path(path)
    value = json.loads(path.read_text())
    allowed = {'enabled', 'adb', 'serial', 'pause_file', 'state_file', 'interval_s', 'max_restarts_per_10min'}
    if not isinstance(value, dict) or set(value)-allowed:
        raise ConfigError('Invalid watchdog configuration')
    if type(value.get('enabled', False)) is not bool:
        raise ConfigError('Invalid enabled flag')
    serial = value.get('serial')
    if not isinstance(serial, str) or (not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', serial) or serial.startswith('emulator-')):
        raise ConfigError('Missing authorized USB device selection')
    for name in ('adb', 'pause_file'):
        if not isinstance(value.get(name), str) or not Path(value[name]).is_absolute():
            raise ConfigError('Watchdog paths must be absolute')
    value['state_file'] = value.get('state_file', str(path.with_name('tablet-watchdog-state.json')))
    if not isinstance(value['state_file'], str) or not Path(value['state_file']).is_absolute():
        raise ConfigError('State path must be absolute')
    interval, limit = value.get('interval_s', 5), value.get('max_restarts_per_10min', 3)
    if type(interval) not in (int, float) or not 2 <= interval <= 60 or type(limit) is not int or not 1 <= limit <= 5:
        raise ConfigError('Invalid watchdog bounds')
    value.update(enabled=value.get('enabled', False), interval_s=interval, max_restarts_per_10min=limit)
    return value


class Watchdog:
    def __init__(self, config, runner=subprocess.run, wallclock=time.time, should_stop=lambda: False):
        self.config, self.runner, self.wallclock = config, runner, wallclock
        self.should_stop = should_stop
        self.state_path = Path(config['state_file'])
        self.env = dict(os.environ, ANDROID_SERIAL=config['serial'])

    def adb(self, *arguments):
        try:
            return self.runner([self.config['adb'], *arguments], env=self.env,
                               capture_output=True, text=True, timeout=4, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None

    def reserve_attempt(self):
        now = self.wallclock()
        try:
            if self.state_path.exists():
                value = json.loads(self.state_path.read_text())
                if not isinstance(value, dict) or set(value) != {'attempts'} or not isinstance(value['attempts'], list) or len(value['attempts']) > 1000:
                    return 'state_error'
                attempts = value['attempts']
                if any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 or t > now+1 for t in attempts):
                    return 'state_error'
            else:
                attempts = []
            attempts = [t for t in attempts if now-t < 600]
            if len(attempts) >= self.config['max_restarts_per_10min']:
                return 'restart_limited'
            if attempts and now-max(attempts) < 30:
                return 'restart_backoff'
            attempts.append(now)
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_name(self.state_path.name+'.tmp')
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w') as target:
                os.fchmod(target.fileno(), 0o600)
                json.dump({'attempts': attempts}, target)
                target.flush(); os.fsync(target.fileno())
            os.replace(temporary, self.state_path)
            return None
        except (OSError, ValueError, TypeError):
            return 'state_error'

    def check(self):
        if Path(self.config['pause_file']).exists():
            return {'state': 'paused'}
        device = self.adb('get-state')
        if device is None or device.returncode != 0 or device.stdout.strip() != 'device':
            return {'state': 'device_unavailable'}
        process = self.adb('shell', 'pidof', 'org.facebot')
        if process is None:
            return {'state': 'process_check_failed'}
        if process.returncode == 0 and re.fullmatch(r'\d+(?:\s+\d+)*', process.stdout.strip()):
            return {'state': 'process_present'}
        # No launch on ambiguous shell/permission errors or invalid pid output.
        if process.returncode != 1 or process.stdout.strip() or process.stderr.strip():
            return {'state': 'process_check_failed'}
        if not self.config['enabled']:
            return {'state': 'process_absent_observing'}
        if self.should_stop():
            return {'state': 'stopping'}
        if Path(self.config['pause_file']).exists():
            return {'state': 'paused'}
        refused = self.reserve_attempt()
        if refused:
            return {'state': refused}
        if self.should_stop():
            return {'state': 'stopping'}
        if Path(self.config['pause_file']).exists():
            return {'state': 'paused'}
        launched = self.adb('shell', 'am', 'start', '-n', 'org.facebot/.FaceActivity')
        # Successful dispatch is not proof of foreground, unlocked display or audio.
        return {'state': 'restart_requested' if launched is not None and launched.returncode == 0 else 'restart_request_failed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path, help='Private JSON config, including selected USB device; never print its contents')
    parser.add_argument('--once', action='store_true', help='One check; restart still requires enabled:true in private config')
    args = parser.parse_args()
    try:
        config = load_config(args.config.resolve())
        lock_path = Path(config['state_file']).with_suffix('.lock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock = os.fdopen(os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600), 'w')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ValueError, TypeError):
        print(json.dumps({'state': 'configuration_or_lock_error'}), flush=True)
        return 2
    stop = False
    def terminate(signum, frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    watchdog = Watchdog(config, should_stop=lambda: stop)
    previous = None
    try:
        while not stop:
            event = watchdog.check()
            if event != previous or event['state'].startswith('restart_request'):
                print(json.dumps(dict(at_utc=datetime.now(timezone.utc).isoformat(), **event)), flush=True)
                previous = event
            if args.once:
                break
            deadline = time.monotonic()+config['interval_s']
            while not stop and time.monotonic()<deadline:
                time.sleep(min(.25, max(0, deadline-time.monotonic())))
    finally:
        lock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
