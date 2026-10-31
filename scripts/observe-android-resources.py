#!/usr/bin/env python3
"""Explicitly opt-in, read-only resource samples from one already authorized tablet.

Never connects, pairs, installs, wakes, changes settings or restarts anything.
No device identifiers, raw command output, audio or visitor data enter receipts.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

PACKAGE = 'org.facebot'
INTERVAL_SECONDS = 60
MAX_DURATION_SECONDS = 12 * 60 * 60
COMMAND_TIMEOUT_SECONDS = 5
MAX_OUTPUT_BYTES = 262144
EVIDENCE = ('Point samples only; gaps between samples are unobserved. PID changes can be missed '
            'or hidden by PID reuse. These receipts do not establish continuous uptime, memory '
            'leak absence, thermal safety, voice transport or acoustic performance.')


class ObserverError(Exception):
    """Fixed non-sensitive reason codes only."""


def single_device(output, expected=None):
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith('List of devices attached'):
            continue
        fields = line.split()
        if len(fields) < 2:
            raise ObserverError('invalid_device_inventory')
        rows.append(fields)
    if len(rows) > 1:
        raise ObserverError('ambiguous_devices')
    if not rows:
        raise ObserverError('device_unavailable')
    serial, state = rows[0][:2]
    if expected is not None and serial != expected:
        raise ObserverError('device_changed')
    if state != 'device':
        raise ObserverError('device_not_authorized_or_ready')
    return serial  # In memory only; never included in an exception or receipt.


def parse_pids(output):
    value = output.strip()
    if not value:
        return ()
    if not re.fullmatch(r'[1-9]\d{0,9}(?:\s+[1-9]\d{0,9})*', value):
        return None
    return tuple(sorted(set(int(part) for part in value.split())))


def parse_pss(output):
    values = re.findall(r'^\s*TOTAL PSS:\s*(\d{1,12})(?=\s|$)', output, re.M)
    if not values:
        values = re.findall(r'^\s*TOTAL\s+(\d{1,12})\s+', output, re.M)
    return int(values[0]) if len(values) == 1 else None


def unique_field(output, key, pattern):
    values = re.findall(r'^\s*' + re.escape(key) + r':\s*(' + pattern + r')\s*$', output, re.M | re.I)
    return values[0] if len(values) == 1 else None


def parse_battery(output):
    powered = [unique_field(output, source + ' powered', 'true|false')
               for source in ('AC', 'USB', 'Wireless')]
    dock = unique_field(output, 'Dock powered', 'true|false')
    if dock is not None:
        powered.append(dock)
    plugged = True if any(value and value.lower() == 'true' for value in powered) else (
        False if all(value and value.lower() == 'false' for value in powered) else None)
    level = unique_field(output, 'level', r'\d{1,6}')
    scale = unique_field(output, 'scale', r'\d{1,6}')
    level_percent = None
    if level is not None and scale is not None and 0 <= int(level) <= int(scale) and int(scale) > 0:
        level_percent = round(100 * int(level) / int(scale), 2)
    temperature = unique_field(output, 'temperature', r'-?\d{1,6}')
    return {'battery_plugged': plugged, 'battery_level_percent': level_percent,
            'battery_temperature_c': int(temperature) / 10 if temperature is not None else None}


def parse_thermal(output):
    value = unique_field(output, 'Thermal Status', '[0-6]')
    return int(value) if value is not None else None


class Adb:
    def __init__(self, executable='adb', *, runner=subprocess.run, clock=time.monotonic):
        self.executable, self.runner, self.clock = executable, runner, clock
        self.serial = None

    def command(self, args, deadline=None, *, absent_ok=False, target=False):
        timeout = COMMAND_TIMEOUT_SECONDS
        if deadline is not None:
            timeout = min(timeout, deadline - self.clock())
        if timeout <= 0:
            return None, 'deadline_reached'
        environment = dict(os.environ)
        environment.pop('ANDROID_SERIAL', None)
        if target:
            environment['ANDROID_SERIAL'] = self.serial
        try:
            result = self.runner([self.executable, *args], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, timeout=timeout, check=False,
                                 env=environment)
        except subprocess.TimeoutExpired:
            return None, 'timeout'
        except OSError:
            return None, 'unavailable'
        if len(result.stdout) > MAX_OUTPUT_BYTES:
            return None, 'output_too_large'
        if result.returncode != 0 and not (absent_ok and result.returncode == 1 and not result.stdout.strip()):
            return None, 'unavailable'
        try:
            return result.stdout.decode('utf-8', errors='strict'), 'ok'
        except UnicodeError:
            return None, 'invalid_output'

    def select(self):
        raw, status = self.command(['devices'])
        if status != 'ok':
            raise ObserverError('device_inventory_' + status)
        self.serial = single_device(raw)

    def sample(self, deadline):
        raw, status = self.command(['devices'], deadline)
        if status == 'ok':
            try:
                single_device(raw, self.serial)
            except ObserverError as error:
                if str(error) in ('ambiguous_devices', 'device_changed', 'invalid_device_inventory'):
                    raise
                status = str(error)
        result = {'device_available': status == 'ok', 'process_alive': None, 'process_count': None,
                  'pss_kb': None, **parse_battery(''), 'thermal_status': None,
                  'command_status': {'inventory': status}}
        if status != 'ok':
            return result, None
        commands = {'process': ['pidof', PACKAGE], 'memory': ['dumpsys', 'meminfo', PACKAGE],
                    'battery': ['dumpsys', 'battery'], 'thermal': ['dumpsys', 'thermalservice']}
        pids = None
        for name, command in commands.items():
            raw, command_status = self.command(['shell', *command], deadline,
                                                absent_ok=name == 'process', target=True)
            if command_status == 'ok':
                if name == 'process':
                    pids = parse_pids(raw)
                    if pids is not None:
                        result.update(process_alive=bool(pids), process_count=len(pids))
                    else:
                        command_status = 'invalid_output'
                elif name == 'memory':
                    result['pss_kb'] = parse_pss(raw)
                    if result['pss_kb'] is None:
                        command_status = 'unavailable'
                elif name == 'battery':
                    result.update(parse_battery(raw))
                    if all(result[key] is None for key in parse_battery('')):
                        command_status = 'unavailable'
                else:
                    result['thermal_status'] = parse_thermal(raw)
                    if result['thermal_status'] is None:
                        command_status = 'unavailable'
            result['command_status'][name] = command_status
        return result, pids


class Receipts:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.file = os.fdopen(fd, 'w')

    def write(self, row):
        self.file.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
        self.file.flush()

    def close(self):
        self.file.close()


def observe(adb, sink, *, duration_seconds=MAX_DURATION_SECONDS, clock=time.monotonic, sleep=time.sleep):
    if type(duration_seconds) is not int or not INTERVAL_SECONDS <= duration_seconds <= MAX_DURATION_SECONDS:
        raise ValueError('Duration must be an integer from 60 to 43200 seconds')
    if adb.serial is None:
        raise ObserverError('device_not_selected')
    start = clock()
    deadline = start + duration_seconds
    last_pids, last_sample = None, None
    summary = dict(samples=0, pid_changes_observed=0, process_absent_samples=0,
                   process_unknown_samples=0, max_sample_gap_s=0.0,
                   pss_kb_min=None, pss_kb_max=None, battery_temperature_c_max=None,
                   thermal_status_max=None)
    reason = 'duration_complete'

    def emit(kind, **values):
        sink.write(dict(type=kind, at_utc=datetime.now(timezone.utc).isoformat(),
                        elapsed_s=round(clock()-start, 3), **values))

    emit('resource_observer_start', package=PACKAGE, duration_seconds=duration_seconds,
         interval_seconds=INTERVAL_SECONDS, command_timeout_seconds=COMMAND_TIMEOUT_SECONDS,
         evidence=EVIDENCE)
    try:
        while clock() < deadline:
            sample_start = clock()
            row, pids = adb.sample(deadline)
            now = clock()
            summary['samples'] += 1
            if last_sample is not None:
                summary['max_sample_gap_s'] = round(max(summary['max_sample_gap_s'], now-last_sample), 3)
            last_sample = now
            if pids:
                if last_pids is not None and pids != last_pids:
                    summary['pid_changes_observed'] += 1
                last_pids = pids
            if row['process_alive'] is False:
                summary['process_absent_samples'] += 1
            elif row['process_alive'] is None:
                summary['process_unknown_samples'] += 1
            for field, source, operation in (('pss_kb_min', 'pss_kb', min), ('pss_kb_max', 'pss_kb', max),
                                             ('battery_temperature_c_max', 'battery_temperature_c', max),
                                             ('thermal_status_max', 'thermal_status', max)):
                value = row[source]
                if value is not None:
                    summary[field] = value if summary[field] is None else operation(summary[field], value)
            emit('resource_sample', sample_duration_s=round(now-sample_start, 3),
                 pid_changes_observed=summary['pid_changes_observed'], **row)
            # Absolute cadence; host delays never trigger catch-up bursts.
            next_sample = start + (math.floor((clock()-start)/INTERVAL_SECONDS)+1)*INTERVAL_SECONDS
            sleep(max(0, min(next_sample, deadline)-clock()))
    except KeyboardInterrupt:
        reason = 'interrupted'
    except ObserverError as error:
        reason = str(error)
    emit('resource_observer_summary', reason=reason, **summary, evidence=EVIDENCE)
    return 0 if reason == 'duration_complete' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-adb', action='store_true', help='Explicitly enable read-only ADB sampling')
    parser.add_argument('--adb', default='adb', help='Existing adb executable')
    parser.add_argument('--output', type=Path, required=True, help='New private JSONL file; never overwritten')
    parser.add_argument('--duration-seconds', type=int, default=MAX_DURATION_SECONDS,
                        help='60–43200 seconds; sample interval is fixed at 60 seconds')
    args = parser.parse_args(argv)
    if not args.observe_adb:
        parser.error('--observe-adb is required; nothing was sampled')
    if not INTERVAL_SECONDS <= args.duration_seconds <= MAX_DURATION_SECONDS:
        parser.error('Duration must be 60–43200 seconds')
    sink = None
    try:
        adb = Adb(args.adb)
        adb.select()
        sink = Receipts(args.output)
        return observe(adb, sink, duration_seconds=args.duration_seconds)
    except ObserverError as error:
        print('Observer unavailable: ' + str(error))
        return 1
    except OSError:
        print('Observer output unavailable; use a new writable output path.')
        return 1
    finally:
        if sink is not None:
            sink.close()


if __name__ == '__main__':
    raise SystemExit(main())
