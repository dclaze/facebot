#!/usr/bin/env python3
"""Owner-invoked, content-free checks of an already connected Facebot tablet.

Default: read-only health/connection snapshot. --rehearse explicitly plays
allowlisted synthetic scenarios. No ADB, installs, wake/unlock or mute changes.
"""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

SCENARIOS = ('welcome', 'candy', 'joke', 'scare', 'laugh-invite', 'laugh-turn', 'sound', 'robin', 'goodbye')
UUID = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z')
EVIDENCE = ('Synthetic host dispatch to observed native AudioTrack playback-head acknowledgement; '
            'upper bound includes return network transit and native polling; excludes VAD, STT and acoustic output. '
            'Network path is not inferred: independently establish Wi-Fi transport before claiming Wi-Fi results '
            '(USB disconnected, or no ADB reverse mapping plus an explicit RFC1918 voice endpoint). '
            'USB may remain attached for power and recovery; verify tablet reconnection and voice/vision separately.')


class ProbeError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_base(base):
    value = urlsplit(base)
    if (value.scheme not in ('http', 'https') or not value.hostname or value.username or value.password
            or value.query or value.fragment or value.path not in ('', '/')):
        raise ValueError('Use an HTTP(S) origin without credentials, path, query or fragment')
    if value.scheme == 'http' and value.hostname != 'localhost':
        try:
            address = ipaddress.ip_address(value.hostname)
            private = any(address in network for network in (
                ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('172.16.0.0/12'),
                ipaddress.ip_network('192.168.0.0/16'))) if address.version == 4 else False
            if not (address.is_loopback or private):
                raise ValueError()
        except ValueError:
            raise ValueError('Cleartext benchmark requires loopback or an explicit private IPv4 address') from None
    return base.rstrip('/')


class Client:
    def __init__(self, base, token, timeout=3):
        self.base = validate_base(base)
        if not 24 <= len(token) <= 512 or any(ord(ch) < 33 or ord(ch) > 126 for ch in token):
            raise ValueError('Token file must contain the host pairing token')
        self.token, self.timeout = token, timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, method='GET'):
        request = Request(self.base + path, method=method,
                          headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'},
                          data=b'' if method == 'POST' else None)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ProbeError('response_too_large')
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ProbeError('invalid_response')
                return data
        except HTTPError as error:
            raise ProbeError('http_' + str(error.code)) from None
        except (URLError, TimeoutError, OSError):
            raise ProbeError('transport_error') from None
        except (ValueError, UnicodeError):
            raise ProbeError('invalid_json') from None


class Receipts:
    def __init__(self, output):
        self.path = Path(output)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.file = os.fdopen(descriptor, 'w')

    def write(self, item):
        self.file.write(json.dumps(item, separators=(',', ':'), allow_nan=False) + '\n')
        self.file.flush()

    def close(self):
        self.file.close()


def run(client, sink, *, rehearse=False, scenarios=('welcome', 'candy', 'joke'), repeats=1,
        soak_seconds=0, interval=2, idle_timeout=30, receipt_timeout=18,
        clock=time.monotonic, sleep=time.sleep):
    if not 1 <= repeats <= 5 or not scenarios or len(scenarios) * repeats > 30 or any(s not in SCENARIOS for s in scenarios):
        raise ValueError('Use 1–30 allowlisted rehearsals, at most 5 repetitions')
    if not 0 <= soak_seconds <= 43200 or not .25 <= interval <= 60 or not 1 <= idle_timeout <= 120 or not 1 <= receipt_timeout <= 30:
        raise ValueError('Invalid bounded duration')
    started = clock()
    checks, results = [], []
    interrupted = False
    soak_started = None
    soak_observed = 0.

    def emit(kind, **fields):
        row = dict(type=kind, at_utc=datetime.now(timezone.utc).isoformat(), elapsed_s=round(clock()-started, 3), **fields)
        sink.write(row)
        return row

    def sample():
        fields, diagnostics = {}, None
        for path in ('/health', '/diagnostics'):
            try:
                data = client.request(path)
                if path == '/health':
                    fields['health_ready'] = data.get('status') == 'ready'
                else:
                    diagnostics = data
                    voice = data.get('voice_state')
                    fields['voice_connected'] = isinstance(voice, dict)
                    if isinstance(voice, dict):
                        for key in ('silenced', 'user_speaking', 'bot_speaking', 'response_pending'):
                            fields[key] = voice.get(key) if type(voice.get(key)) is bool else None
            except ProbeError as error:
                fields['health_error' if path == '/health' else 'diagnostics_error'] = str(error)
        row = emit('health', **fields)
        checks.append(row)
        return row, diagnostics

    def ready(row, diagnostics):
        probes = diagnostics.get('playback_probes', {}) if diagnostics else {}
        return (row.get('health_ready') is True and row.get('voice_connected') is True
                and all(row.get(k) is False for k in ('silenced', 'user_speaking', 'bot_speaking', 'response_pending'))
                and isinstance(probes, dict) and not probes.get('pending'))

    try:
        sample()
        if rehearse:
            for repeat in range(repeats):
                for scenario in scenarios:
                    deadline = clock() + idle_timeout
                    while True:
                        row, diagnostics = sample()
                        if ready(row, diagnostics):
                            break
                        if clock() >= deadline:
                            results.append(emit('probe', scenario=scenario, repeat=repeat+1, status='idle_timeout'))
                            break
                        sleep(min(interval, max(0., deadline-clock())))
                    if not ready(row, diagnostics):
                        continue
                    try:
                        accepted = client.request('/owner/rehearse/' + scenario, 'POST')
                        identifier = accepted.get('id')
                        if not isinstance(identifier, str) or not UUID.fullmatch(identifier):
                            raise ProbeError('invalid_probe_id')
                    except ProbeError as error:
                        results.append(emit('probe', scenario=scenario, repeat=repeat+1, status=str(error)))
                        continue
                    deadline = clock() + receipt_timeout
                    result = None
                    while clock() < deadline:
                        _, diagnostics = sample()
                        probes = diagnostics.get('playback_probes', {}) if diagnostics else {}
                        values = probes.get('samples', []) if isinstance(probes, dict) else []
                        if isinstance(values, list):
                            for value in values:
                                if not isinstance(value, dict) or value.get('id') != identifier:
                                    continue
                                status = value.get('status')
                                if status not in ('played', 'cancelled', 'timeout'):
                                    continue
                                result = dict(id=identifier, status=status)
                                if status == 'played':
                                    duration = value.get('dispatch_to_native_ack_ms')
                                    if type(duration) not in (float, int) or not math.isfinite(duration) or not 0 <= duration <= 30000:
                                        result['status'] = 'invalid_native_timing'
                                    else:
                                        result['dispatch_to_native_ack_ms'] = duration
                                break
                        if result:
                            break
                        sleep(min(interval, max(0., deadline-clock())))
                    results.append(emit('probe', scenario=scenario, repeat=repeat+1,
                                        **(result or dict(id=identifier, status='receipt_wait_timeout'))))
                    # Avoid the authored-response duplicate-transcript throttle.
                    sleep(1.6)
        if soak_seconds:
            soak_started = clock()
            deadline = soak_started + soak_seconds
            while True:
                sample()
                if clock() >= deadline:
                    break
                sleep(min(interval, max(0., deadline-clock())))
            soak_observed = clock() - soak_started
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if soak_started is not None:
            soak_observed = clock() - soak_started
    values = sorted(r['dispatch_to_native_ack_ms'] for r in results if r['status'] == 'played')
    known = [r['voice_connected'] for r in checks if type(r.get('voice_connected')) is bool]
    transitions = sum(a is True and b is False for a, b in zip(known, known[1:]))
    summary = dict(type='summary', evidence=EVIDENCE, rehearsals_enabled=rehearse,
                   observed_duration_s=round(clock()-started, 3), requested_soak_seconds=soak_seconds,
                   observed_soak_seconds=round(soak_observed, 3), interrupted=interrupted,
                   health_samples=len(checks), connected_samples=sum(v is True for v in known),
                   disconnected_samples=sum(v is False for v in known),
                   unknown_connection_samples=len(checks)-len(known), observed_disconnect_transitions=transitions,
                   health_failures=sum(r.get('health_ready') is not True for r in checks),
                   requested_interval_s=interval,
                   max_observed_sample_gap_s=round(max((b['elapsed_s']-a['elapsed_s'] for a,b in zip(checks,checks[1:])), default=0), 3),
                   continuous_uptime_proven=False,
                   coverage='Point samples only; interruptions between samples may be missed. No physical Wi-Fi, lockscreen or acoustic inference.',
                   probe_count=len(results), played_count=len(values),
                   latency={'n':len(values), 'p50_ms':statistics.median(values),
                            'p95_ms':values[math.ceil(len(values)*.95)-1], 'max_ms':max(values)} if values else None)
    summary['ok'] = bool(checks) and not interrupted and all(r.get('health_ready') is True and r.get('voice_connected') is True for r in checks) and all(r['status']=='played' for r in results)
    sink.write(summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New private JSONL receipt file; never overwritten')
    parser.add_argument('--rehearse', action='store_true', help='Explicitly play allowlisted synthetic scenarios on the connected tablet')
    parser.add_argument('--scenarios', default='welcome,candy,joke', help='Comma-separated allowlisted scenario names, only with --rehearse')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--soak-seconds', type=float, default=0, help='Read-only sampling duration, 0–43200; report actual observed duration')
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--idle-timeout', type=float, default=30)
    parser.add_argument('--receipt-timeout', type=float, default=18)
    parser.add_argument('--request-timeout', type=float, default=3)
    args = parser.parse_args()
    try:
        if not 0.25 <= args.request_timeout <= 10:
            raise ValueError('Request timeout must be between 0.25 and 10 seconds')
        client = Client(args.base_url, args.token_file.read_text().strip(), args.request_timeout)
        sink = Receipts(args.output)
        try:
            summary = run(client, sink, rehearse=args.rehearse, scenarios=tuple(args.scenarios.split(',')),
                          repeats=args.repeats, soak_seconds=args.soak_seconds, interval=args.interval,
                          idle_timeout=args.idle_timeout, receipt_timeout=args.receipt_timeout)
        finally:
            sink.close()
        print(json.dumps(summary, indent=2))
        return 0 if summary['ok'] else 1
    except (ValueError, OSError) as error:
        # Never echo OS paths or token-file content in shared output.
        parser.error(str(error) if isinstance(error, ValueError) else 'Could not read token or create the private receipt file')


if __name__ == '__main__':
    raise SystemExit(main())
