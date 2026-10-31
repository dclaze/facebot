#!/usr/bin/env python3
"""Model-free Facebot process supervision and macOS user LaunchAgent management."""
import argparse
import fcntl
import json
import ipaddress
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import plistlib
import re
import signal
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

LABEL = 'org.facebot.kiosk'
DEFAULT_STATE = Path.home() / 'Library/Application Support/Facebot/kiosk'
# Shared across release trees and state directories: never run two local kiosks.
LOCK = Path.home() / 'Library/Application Support/Facebot/kiosk-owner.lock'


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, indent=2)
        stream.write('\n')
    temp.replace(path)


def private_lan_host(value):
    address = ipaddress.ip_address(value)
    return address.version == 4 and any(address in ipaddress.ip_network(network)
                                         for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def port_occupied(port, host='127.0.0.1'):
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex((host, port)) == 0


def healthy(config):
    # No token, remote host, response body or exception is logged.
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        route = '/api/settings' if config.get('role') == 'admin' else '/health'
        with opener.open(f"http://{config.get('host', '127.0.0.1')}:{config['port']}{route}",
                         timeout=config['health_timeout']) as response:
            value = json.loads(response.read(65537))
        if config.get('role') == 'admin':
            return value.get('profile') == config['profile'] and isinstance(value.get('etag'), str)
        return (value.get('status') == 'ready' and
                value.get('profile') == config['profile'] and
                value.get('tts', {}).get('backend') == config['tts'])
    except (OSError, ValueError, AttributeError):
        return False


class SleepGuard:
    """Own one idle-sleep inhibitor; -w also releases it if its parent dies."""
    def __init__(self, stop_event, logger, command=None, label='idle_sleep_protection', stop_timeout=2):
        self.stop_event, self.logger = stop_event, logger
        self.command = command or ['/usr/bin/caffeinate', '-i', '-w', str(os.getpid())]
        self.process = None
        self.label = label
        self.stop_timeout = stop_timeout

    def active(self):
        process = self.process
        return process is not None and process.poll() is None

    def run(self):
        delay = 2
        try:
            while not self.stop_event.is_set():
                born = time.monotonic()
                try:
                    self.process = subprocess.Popen(self.command, stdin=subprocess.DEVNULL,
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.logger.info('%s_started', self.label)
                    while not self.stop_event.wait(.5) and self.process.poll() is None:
                        pass
                    if self.process.poll() is not None:
                        self.process.wait()
                except OSError:
                    self.logger.warning('%s_unavailable', self.label)
                if not self.stop_event.is_set():
                    if time.monotonic() - born >= 120:
                        delay = 2
                    self.stop_event.wait(delay)
                    delay = min(60, delay * 2)
        finally:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=self.stop_timeout)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=2)
                self.process = None


class Supervisor:
    def __init__(self, config, state, lock_path=LOCK):
        self.config, self.state, self.lock_path = config, Path(state), Path(lock_path)
        self.stop_event = threading.Event()
        self.child = None
        self.restarts = 0
        self.admin = self.admin_thread = None
        self.sleep_guard = self.sleep_thread = None
        self.tablet_guard = self.tablet_thread = None
        self.logger = logging.getLogger(f'facebot.kiosk.{id(self)}')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def report(self, phase, **fields):
        value = dict(phase=phase, supervisor_pid=os.getpid(),
                     child_pid=self.child.pid if self.child else None,
                     updated_at=time.time(), restarts=self.restarts,
                     profile=self.config['profile'], model=self.config['model'],
                     tts=self.config['tts'], root=self.config['root'],
                     host=self.config.get('host', '127.0.0.1'), role=self.config.get('role', 'voice'), **fields)
        if self.admin is not None:
            try:
                value['admin'] = json.loads((self.state / 'admin/status.json').read_text())
            except (OSError, ValueError):
                value['admin'] = {'phase': 'starting'}
            value['admin']['watchdog_alive'] = self.admin_thread.is_alive()
        if self.sleep_guard is not None:
            value['idle_sleep_protected'] = self.sleep_guard.active()
        if self.tablet_guard is not None:
            value['tablet_watchdog_active'] = self.tablet_guard.active()
        atomic_json(self.state / 'status.json', value)
        if phase != 'ready' or fields:
            self.logger.info('%s', json.dumps(value, sort_keys=True))

    def stop_child(self):
        if self.child is None:
            return
        if self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=self.config['stop_timeout'])
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=5)
        self.child = None

    def spawn(self):
        env = os.environ.copy()
        if self.config.get('role') != 'admin':
            token = Path(self.config['token_file']).read_text().strip()
            if len(token) < 24 or '\n' in token:
                raise ValueError('Invalid token file')
            env['FACEBOT_TOKEN'] = token
        else:
            env.pop('FACEBOT_TOKEN', None)
        env.update(FACEBOT_PROFILE=self.config['profile'],
                   FACEBOT_LLM=self.config['model'], FACEBOT_TTS=self.config['tts'],
                   FACEBOT_SPEECH_RATE=str(self.config['speech_rate']),
                   FACEBOT_KIOSK_MODE='1')
        # Same process group intentionally: launchd removes descendants when the
        # supervisor is killed. Do not set start_new_session or AbandonProcessGroup.
        self.child = subprocess.Popen(self.config['command'], cwd=self.config['root'],
                                      env=env, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.report('starting')

    def start_support(self):
        if self.stop_event.is_set():
            return
        if self.config.get('admin'):
            config = {**self.config, **self.config['admin']}
            config.pop('admin', None)
            config.pop('tablet_watchdog', None)
            config['prevent_sleep'] = False
            self.admin = Supervisor(config, self.state / 'admin', self.state / 'admin-owner.lock')
            self.admin_thread = threading.Thread(target=self.admin.run, name='facebot-admin-watchdog', daemon=True)
            self.admin_thread.start()
        if self.config.get('prevent_sleep', False):
            self.sleep_guard = SleepGuard(self.stop_event, self.logger)
            self.sleep_thread = threading.Thread(target=self.sleep_guard.run, name='facebot-sleep-guard', daemon=True)
            self.sleep_thread.start()
        if self.config.get('tablet_watchdog'):
            self.tablet_guard = SleepGuard(self.stop_event, self.logger,
                                          command=self.config['tablet_watchdog']['command'], label='tablet_watchdog', stop_timeout=10)
            self.tablet_thread = threading.Thread(target=self.tablet_guard.run, name='facebot-tablet-guard', daemon=True)
            self.tablet_thread.start()

    def stop_support(self):
        self.stop_event.set()
        if self.admin is not None:
            self.admin.stop_event.set()
        # Both independent watchdogs begin shutdown before we reap voice, so
        # admin's grace period does not get added to voice's grace period.
        self.stop_child()
        if self.admin_thread is not None:
            self.admin_thread.join(self.config['stop_timeout'] + self.config['health_timeout'] + 5)
            if self.admin_thread.is_alive():
                raise TimeoutError('Owner watchdog shutdown timed out')
        if self.sleep_thread is not None:
            self.sleep_thread.join(5)
            if self.sleep_thread.is_alive():
                raise TimeoutError('Sleep guard shutdown timed out')
        if self.tablet_thread is not None:
            self.tablet_thread.join(13)
            if self.tablet_thread.is_alive():
                raise TimeoutError('Tablet watchdog shutdown timed out')

    def run(self):
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Never unlink the lock: replacing its inode lets another owner bypass it.
        with self.lock_path.open('a') as lock:
            os.chmod(self.lock_path, 0o600)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 73
            handler = RotatingFileHandler(self.state / 'recovery.log',
                                          maxBytes=262144, backupCount=2)
            os.chmod(self.state / 'recovery.log', 0o600)
            self.logger.addHandler(handler)
            failures = 0
            try:
                self.start_support()
                while not self.stop_event.is_set():
                    if port_occupied(self.config['port'], self.config.get('host', '127.0.0.1')):
                        # A manual release or orphan is not ours to kill/adopt.
                        self.report('port_conflict')
                        self.stop_event.wait(self.config['backoff_max'])
                        continue
                    try:
                        self.spawn()
                        born = time.monotonic()
                        ready_since = None
                        stable_since = None
                        misses = 0
                        reason = 'stopped'
                        while not self.stop_event.is_set():
                            if self.child.poll() is not None:
                                reason = 'child_exit'
                                break
                            now = time.monotonic()
                            if healthy(self.config):
                                if stable_since is None:
                                    stable_since = now
                                if ready_since is None:
                                    ready_since = now
                                    self.report('ready', recovered=self.restarts > 0)
                                else:
                                    self.report('ready')
                                misses = 0
                                if now - stable_since >= self.config['stable_reset']:
                                    failures = 0
                            elif ready_since is None:
                                stable_since = None
                                if now - born >= self.config['startup_timeout']:
                                    reason = 'startup_timeout'
                                    break
                            else:
                                stable_since = None
                                misses += 1
                                self.report('health_miss', consecutive=misses)
                                if misses >= self.config['health_failures']:
                                    reason = 'health_timeout'
                                    break
                            self.stop_event.wait(self.config['interval'])
                        self.stop_child()
                        if self.stop_event.is_set():
                            break
                    except (OSError, ValueError, subprocess.SubprocessError):
                        # Paths, environment, token and exception strings stay private.
                        self.stop_child()
                        reason = 'start_error'
                    failures += 1
                    self.restarts += 1
                    delay = min(self.config['backoff_max'],
                                self.config['backoff_initial'] * 2 ** min(failures - 1, 16))
                    self.report('backoff', reason=reason, retry_seconds=delay)
                    self.stop_event.wait(delay)
            finally:
                self.stop_support()
                self.report('stopped')
                self.logger.removeHandler(handler)
                handler.close()
        return 0


def plist_path():
    return Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')


def launchctl(*args, check=True, timeout=10):
    return subprocess.run(['/bin/launchctl', *args], check=check,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)


def service_target():
    return f'gui/{os.getuid()}/{LABEL}'


def is_loaded(timeout=10):
    return launchctl('print', service_target(), check=False, timeout=timeout).returncode == 0


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError('LaunchAgent transition deadline expired')
    return value


def transition_pause(deadline, delay):
    time.sleep(min(delay, remaining(deadline)))


def stop_service(timeout=30):
    """bootout acknowledgement can precede completion of job removal."""
    deadline = time.monotonic() + timeout
    if not is_loaded(timeout=min(5, remaining(deadline))):
        return
    try:
        launchctl('bootout', service_target(), timeout=remaining(deadline))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # A concurrent stop can remove the job after print. Determine the actual
        # resulting state; never assume an error means the old job still exists.
        pass
    while is_loaded(timeout=min(5, remaining(deadline))):
        transition_pause(deadline, .25)


def start_service(timeout=30):
    """Allow launchd's transient post-bootout registration race to settle."""
    deadline = time.monotonic() + timeout
    delay = .25
    while True:
        if is_loaded(timeout=min(5, remaining(deadline))):
            return
        if not plist_path().is_file():
            raise FileNotFoundError('Install the service before starting it')
        try:
            launchctl('bootstrap', f'gui/{os.getuid()}', str(plist_path()),
                      timeout=remaining(deadline))
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # No exception/command/environment contents enter logs. A print on
            # the next iteration also makes concurrent successful starts safe.
            transition_pause(deadline, delay)
            delay = min(2, delay * 2)


def restart_service():
    stop_service()
    start_service()


def select_usb_tablet(adb_override=None):
    """Read-only inventory; never put a device identifier in output or argv."""
    candidates = [Path(adb_override).expanduser()] if adb_override else []
    if not candidates:
        located = shutil.which('adb')
        if located:
            candidates.append(Path(located))
        sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        if sdk:
            candidates.append(Path(sdk) / 'platform-tools/adb')
        candidates.append(Path.home() / 'Library/Android/sdk/platform-tools/adb')
    adb = next((path.resolve() for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)
    if adb is None:
        raise ValueError('An existing Android platform-tools adb is required for tablet monitoring')
    inventory = subprocess.run([str(adb), 'devices', '-l'], check=True, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5).stdout
    serials = []
    for line in inventory.splitlines():
        fields = line.split()
        if (len(fields) >= 3 and fields[1] == 'device' and re.fullmatch(r'[A-Za-z0-9._-]{1,128}', fields[0])
                and not fields[0].startswith('emulator-') and any(field.startswith('usb:') for field in fields[2:])):
            serials.append(fields[0])
    if len(serials) != 1:
        raise ValueError('Connect exactly one already-authorized USB tablet; no device was changed')
    return {'enabled': True, 'adb': str(adb), 'serial': serials[0], 'interval_s': 5,
            'max_restarts_per_10min': 3}


def build_config(args):
    root = Path(args.root).expanduser().resolve()
    python = Path(args.python or root / '.venv/bin/python').expanduser().absolute()
    token = Path(args.token_file or root / '.local/pairing-token').expanduser().resolve()
    if not (root / 'server/app.py').is_file() or not python.is_file() or not token.is_file():
        raise ValueError('Root, interpreter and existing pairing-token file must exist')
    if len(token.read_text().strip()) < 24:
        raise ValueError('Existing pairing-token file is invalid')
    sys.path.insert(0, str(root))
    from server.profiles import load
    load(args.profile)
    command = [str(python), '-m', 'server.app', '--host', args.host, '--port', str(args.port)]
    if args.host != '127.0.0.1':
        if not args.trusted_lan or not private_lan_host(args.host):
            raise ValueError('LAN requires --trusted-lan and an explicit RFC1918 IPv4 address')
        command.append('--allow-private-lan')
    elif args.trusted_lan:
        raise ValueError('--trusted-lan requires an explicit private LAN address')
    config = dict(root=str(root), command=command, host=args.host,
                token_file=str(token), port=args.port, profile=args.profile,
                model=args.model, tts=args.tts, speech_rate=args.speech_rate,
                interval=5, health_timeout=2, health_failures=3, startup_timeout=180,
                stop_timeout=10, backoff_initial=2, backoff_max=60, stable_reset=120)
    config['prevent_sleep'] = not getattr(args, 'no_sleep_protection', False)
    if not getattr(args, 'no_admin', False):
        if not (root / 'server/admin.py').is_file():
            raise ValueError('Owner-controls module missing from release')
        if args.port != 8765:
            raise ValueError('Owner controls require voice port 8765; use --no-admin for custom voice ports')
        if token != (root / '.local/pairing-token').resolve():
            raise ValueError('Owner controls require this release pairing-token path; use --no-admin for an external token')
        admin_port = getattr(args, 'admin_port', 8766)
        if not 1 <= admin_port <= 65535 or admin_port == args.port:
            raise ValueError('Choose a distinct valid owner-controls port')
        admin_command = [str(python), '-m', 'server.admin', '--host', args.host, '--port', str(admin_port)]
        for owner in getattr(args, 'owner_client', []):
            if not private_lan_host(owner):
                raise ValueError('Owner clients require explicit RFC1918 IPv4 addresses')
            admin_command.extend(['--allow-client', owner])
        config['admin'] = dict(role='admin', host=args.host, port=admin_port, command=admin_command)
    elif getattr(args, 'owner_client', []):
        raise ValueError('--owner-client requires owner controls')
    if getattr(args, 'tablet_watchdog', False):
        if not (root / 'scripts/tablet-watchdog.py').is_file():
            raise ValueError('Tablet watchdog script missing from release')
        config['tablet_watchdog_selection'] = select_usb_tablet(getattr(args, 'adb', None))
    return config


def install(args, state):
    if is_loaded():
        raise ValueError('Service already loaded; stop it before changing the release')
    config = build_config(args)
    if port_occupied(config['port'], config.get('host', '127.0.0.1')):
        raise ValueError('Port occupied; the runtime owner must stop the previous server first')
    if config.get('admin') and port_occupied(config['admin']['port'], config['admin']['host']):
        raise ValueError('Owner-controls port occupied; its owner must stop it before installation')
    if plist_path().exists():
        raise ValueError('Existing installation; uninstall before replacing its configuration')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    selection = config.pop('tablet_watchdog_selection', None)
    if selection is not None:
        selection.update(pause_file=str(state / 'tablet-watchdog.paused'),
                         state_file=str(state / 'tablet-watchdog-state.json'))
        private_config = state / 'tablet-watchdog.json'
        atomic_json(private_config, selection)
        config['tablet_watchdog'] = {'command': [config['command'][0],
            str(Path(config['root']) / 'scripts/tablet-watchdog.py'), '--config', str(private_config)]}
    atomic_json(state / 'config.json', config)
    plist = dict(Label=LABEL,
                 ProgramArguments=[sys.executable, str(Path(__file__).resolve()),
                                   '--state-dir', str(state), 'run'],
                 WorkingDirectory=config['root'], RunAtLoad=True, KeepAlive=True,
                 ThrottleInterval=30, ExitTimeOut=20, AbandonProcessGroup=False,
                 StandardOutPath='/dev/null', StandardErrorPath='/dev/null',
                 EnvironmentVariables={'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin',
                                       'PYTHONUNBUFFERED': '1'})
    plist_path().parent.mkdir(parents=True, exist_ok=True)
    with plist_path().open('wb') as stream:
        os.chmod(plist_path(), 0o600)
        plistlib.dump(plist, stream)
    start_service()
    print('Installed and started. Use status to check readiness; login is required after reboot.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest='action', required=True)
    setup = sub.add_parser('install')
    setup.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    setup.add_argument('--python')
    setup.add_argument('--token-file')
    setup.add_argument('--profile', required=True)
    setup.add_argument('--model', required=True, choices=['qwen2.5:1.5b', 'qwen3.5:9b', 'qwen3:1.7b'])
    setup.add_argument('--tts', required=True, choices=['kokoro', 'qwen3'])
    setup.add_argument('--speech-rate', type=float, default=1.12)
    setup.add_argument('--port', type=int, default=8765)
    setup.add_argument('--host', default='127.0.0.1', help='Loopback or explicit RFC1918 IPv4 address')
    setup.add_argument('--trusted-lan', action='store_true', help='Opt into unencrypted service on a trusted private LAN')
    setup.add_argument('--no-admin', action='store_true', help='Disable the independently supervised owner controls')
    setup.add_argument('--admin-port', type=int, default=8766)
    setup.add_argument('--owner-client', action='append', default=[], help='Allow an explicit owner device RFC1918 IP to use controls; repeat if needed')
    setup.add_argument('--no-sleep-protection', action='store_true', help='Do not inhibit idle system sleep while service runs')
    setup.add_argument('--tablet-watchdog', action='store_true', help='Opt into restarting a missing Facebot process on one already-authorized USB tablet')
    setup.add_argument('--adb', help='Existing adb executable for optional USB tablet monitoring')
    for action in ('run', 'start', 'stop', 'restart', 'status', 'uninstall'):
        sub.add_parser(action)
    args = parser.parse_args()
    state = args.state_dir.expanduser().resolve()
    if args.action == 'run':
        os.umask(0o077)
        supervisor = Supervisor(json.loads((state / 'config.json').read_text()), state)
        signal.signal(signal.SIGTERM, lambda *_: supervisor.stop_event.set())
        signal.signal(signal.SIGINT, lambda *_: supervisor.stop_event.set())
        return supervisor.run()
    if args.action == 'status':
        value = json.loads((state / 'status.json').read_text()) if (state / 'status.json').exists() else {'phase': 'never_started'}
        value['observation_age_seconds'] = round(time.time() - value.get('updated_at', time.time()), 1)
        value['launchd_loaded'] = is_loaded() if sys.platform == 'darwin' else False
        config_file = state / 'config.json'
        config = json.loads(config_file.read_text()) if config_file.exists() else None
        value['healthy_now'] = healthy(config) if config else False
        if config and config.get('admin'):
            value['admin_healthy_now'] = healthy({**config, **config['admin']})
        print(json.dumps(value, indent=2))
        return 0
    if sys.platform != 'darwin':
        parser.error('LaunchAgent commands require macOS; run supports isolated POSIX testing')
    if args.action == 'install':
        if not .8 <= args.speech_rate <= 1.3 or not 1 <= args.port <= 65535:
            parser.error('Speech rate must be 0.8–1.3 and port 1–65535')
        install(args, state)
    elif args.action in ('stop', 'uninstall'):
        stop_service()
        if args.action == 'uninstall':
            plist_path().unlink(missing_ok=True)
            # Retain private configuration and bounded logs for explicit rollback.
        print('Stopped.' if args.action == 'stop' else 'Uninstalled; private configuration and logs retained.')
    elif args.action == 'start':
        start_service()
        print('Started; use status to check readiness.')
    elif args.action == 'restart':
        # SIGTERM lets the supervisor reap its child before launchd starts again.
        restart_service()
        print('Restart requested; use status to check readiness.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError):
        print('Service operation failed. Check paths, configuration, port ownership and launchd status; no secrets logged.', file=sys.stderr)
        raise SystemExit(1)
