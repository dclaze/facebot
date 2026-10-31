#!/usr/bin/env python3
"""Internal kiosk readiness report; never an external certification or live fault drill."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CORE_TESTS = ('test_kiosk_experiences.py', 'test_skill_store.py', 'test_kiosk_transport.py', 'test_kiosk_service.py', 'test_kiosk_tools.py', 'test_kiosk_control.py', 'test_skill_runtime.py', 'test_benchmark_device.py', 'test_tablet_watchdog.py', 'test_vision_setup.py')
EXTRA_TESTS = ('test_reply_quality.py', 'test_tts_stream.py', 'test_protocol.py')
NATIVE = ('ConnectionPolicy', 'PerformanceFaceCue', 'PlaybackProbe', 'KioskStatus', 'PlaybackQueue', 'CaptionTimeline', 'PerformanceVideoCue')
PHYSICAL = ('device', 'wifi', 'recovery', 'visual', 'endurance', 'generated_latency')
REQUIRED_FLAGS = {
    'device': ('voice_and_vision_connected', 'audible_response_verified', 'owner_mute_verified', 'owner_exit_verified'),
    'wifi': ('tablet_reconnected', 'voice_and_vision_connected'),
    'recovery': ('child_restart_verified', 'supervisor_restart_verified', 'tablet_reconnected', 'settings_preserved'),
    'visual': ('desktop_reviewed', 'mobile_reviewed', 'tablet_reviewed', 'readable', 'no_clipping', 'controls_verified'),
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source_state(root):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()
    try:
        # An extracted archive inside another checkout must not inherit the
        # enclosing repository's unrelated commit or cleanliness claim.
        if Path(git('rev-parse', '--show-toplevel')).resolve() == Path(root).resolve():
            return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain', '--untracked-files=normal')),
                    'provenance': 'git_checkout'}
    except (OSError, subprocess.SubprocessError):
        pass
    declaration = Path(root) / 'SOURCE_COMMIT'
    try:
        commit = declaration.read_text().strip()
        if len(commit) == 40 and all(character in '0123456789abcdef' for character in commit):
            return {'commit': commit, 'dirty': None, 'provenance': 'archive_declaration',
                    'declaration_sha256': sha256(declaration),
                    'note': 'Release metadata identifies the intended commit; extracted source integrity is not established by this declaration alone.'}
    except OSError:
        pass
    return {'commit': None, 'dirty': None, 'provenance': 'unknown'}


def item(name, status, level, **detail):
    return {'name': name, 'status': status, 'evidence_level': level, **detail}


def run_check(name, command, root, timeout=180):
    start = time.monotonic()
    try:
        # Test commands use no credentials. Output is deliberately not copied
        # into a public report; rerun a failing command for local diagnostics.
        process = subprocess.Popen(command, cwd=root, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
            status = 'pass' if code == 0 else 'fail'
        except subprocess.TimeoutExpired:
            # Only this freshly created isolated test process group is signaled.
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            status, code = 'fail', 'timeout'
    except OSError:
        status, code = 'missing', 'tool_unavailable'
    return item(name, status, 'isolated_software_check', command=command, exit_code=code,
                duration_seconds=round(time.monotonic()-start, 3), observed_at=stamp())


def artifact_record(path):
    path = Path(path).resolve()
    result = {'path': str(path), 'sha256': sha256(path), 'bytes': path.stat().st_size}
    if path.suffix.lower() == '.apk':
        with zipfile.ZipFile(path) as archive:
            result['unpaired_apk'] = 'assets/local-config.json' not in archive.namelist()
    return result


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def private_voice_host(value):
    if not isinstance(value, str):
        return False
    try:
        host = ipaddress.IPv4Address(value)
        return any(host in ipaddress.IPv4Network(network)
                   for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    except ValueError:
        return False


def review_receipt(path, commit):
    """Check declared observations and bindings; do not pretend to inspect media."""
    path = Path(path)
    try:
        if path.stat().st_size > 262144:
            raise ValueError('Receipt exceeds size limit')
        receipt = json.loads(path.read_text())
        if not isinstance(receipt, dict) or receipt.get('kind') not in PHYSICAL:
            raise ValueError('Unknown receipt kind')
        kind = receipt['kind']
        if receipt.get('schema_version') != 1 or receipt.get('evidence_level') != 'physical_observation':
            raise ValueError('Physical observation schema required; replay is not physical evidence')
        if not commit or receipt.get('source_commit') != commit:
            raise ValueError('Receipt does not identify this exact source commit')
        measured = datetime.fromisoformat(receipt['measured_at'].replace('Z', '+00:00'))
        if measured.tzinfo is None or (measured-datetime.now(timezone.utc)).total_seconds() > 300:
            raise ValueError('Observation timestamp is invalid or in the future')
        if not isinstance(receipt.get('scope'), str) or not receipt['scope'].strip():
            raise ValueError('An actual device/setup scope is required')
        artifacts = receipt.get('artifacts')
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError('At least one hash-bound evidence artifact is required')
        for evidence in artifacts:
            target = Path(evidence['path'])
            if not target.is_absolute():
                target = path.parent / target
            if sha256(target) != evidence['sha256']:
                raise ValueError('Evidence artifact missing or hash mismatch')
        metrics = receipt.get('metrics')
        if not isinstance(metrics, dict):
            raise ValueError('Observation metrics required')
        flags = REQUIRED_FLAGS.get(kind, ())
        passed = all(metrics.get(flag) is True for flag in flags)
        if kind == 'wifi':
            private_endpoint = private_voice_host(metrics.get('voice_endpoint_host'))
            transport = (metrics.get('usb_disconnected') is True or
                         (metrics.get('usb_reverse_absent') is True and private_endpoint))
            # Preserve earlier unplugged receipts, but reject a contradictory
            # endpoint whenever supplied. USB power/control can remain attached.
            endpoint_consistent = 'voice_endpoint_host' not in metrics or private_endpoint
            passed = passed and transport and endpoint_consistent
        elif kind == 'endurance':
            passed = (finite_number(metrics.get('duration_hours')) and metrics['duration_hours'] >= 12
                      and type(metrics.get('unexpected_failures')) is int and metrics['unexpected_failures'] == 0)
        elif kind == 'generated_latency':
            passed = (metrics.get('timing_basis') == 'utterance_end_to_audible_generated_speech'
                      and metrics.get('cached_responses') is False
                      and type(metrics.get('samples')) is int and metrics['samples'] >= 20
                      and finite_number(metrics.get('median_ms')) and finite_number(metrics.get('p95_ms'))
                      and metrics['median_ms'] <= 200 and metrics['median_ms'] <= metrics['p95_ms'] <= 500)
        return item(kind, 'pass' if passed else 'fail', 'physical_observation_receipt',
                    receipt_path=str(path.resolve()), receipt_sha256=sha256(path), measured_at=receipt['measured_at'],
                    scope=receipt['scope'], metrics=metrics,
                    note='Operator observations accepted from this receipt; the runner has not interpreted its media.')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, zipfile.BadZipFile) as error:
        return item('receipt:' + path.name, 'invalid', 'unverified_receipt', reason=str(error)[:200])


def software_checks(root, python, quick, check_only, work):
    rows = []
    for filename in CORE_TESTS + EXTRA_TESTS:
        name = 'python:' + filename
        if not (root / 'tests' / filename).is_file():
            rows.append(item(name, 'missing', 'none'))
        elif check_only or (quick and filename in EXTRA_TESTS):
            rows.append(item(name, 'not_run', 'none', reason='check-only' if check_only else 'quick mode'))
        else:
            rows.append(run_check(name, [python, '-m', 'unittest', 'discover', '-s', 'tests', '-p', filename], root))
    replay = root / 'scripts/benchmark-kiosk.py'
    if not replay.is_file():
        rows.append(item('processor_replay', 'missing', 'none'))
    elif check_only or quick:
        rows.append(item('processor_replay', 'not_run', 'none'))
    else:
        rows.append(run_check('processor_replay', [python, str(replay), '--output', str(work / 'processor-replay.json')], root))
        if (work / 'processor-replay.json').is_file():
            # Preserve the actual replay receipt alongside the aggregate report.
            rows[-1]['replay_sha256'] = sha256(work / 'processor-replay.json')
    source = root / 'android/app/src/main/java/org/facebot'
    java_home = os.environ.get('JAVA_HOME')
    bundled = root / '.local/toolchains/jdk-17.0.21+9/Contents/Home'
    javac = str(Path(java_home) / 'bin/javac') if java_home else str(bundled / 'bin/javac') if (bundled / 'bin/javac').is_file() else shutil.which('javac')
    java = str(Path(javac).with_name('java')) if javac else None
    for name in NATIVE:
        inputs = [source / (name + '.java'), root / 'tests' / (name + 'Test.java')]
        if not all(path.is_file() for path in inputs):
            rows.append(item('android:' + name, 'missing', 'none'))
        elif check_only or quick:
            rows.append(item('android:' + name, 'not_run', 'none'))
        elif not javac:
            rows.append(item('android:' + name, 'missing', 'none', reason='JDK required'))
        else:
            output = work / name
            output.mkdir()
            row = run_check('android:' + name + ':compile', [javac, '-d', str(output), *map(str, inputs)], root)
            rows.append(row)
            if row['status'] == 'pass':
                rows.append(run_check('android:' + name, [java, '-cp', str(output), 'org.facebot.' + name + 'Test'], root))
    return rows


def markdown(report):
    lines = ['# Facebot internal readiness', '', '**Overall: ' + report['overall'] + '**', '',
             'Generated: ' + report['generated_at'], 'Source commit: ' + str(report['source']['commit']),
             'Uncommitted changes: ' + str(report['source']['dirty']),
             'Source provenance: ' + report['source'].get('provenance', 'unknown'), '',
             'This is an internal evidence report, not external certification. Software/replay results do not prove physical behavior.', '',
             '| Check | Status | Evidence |', '| --- | --- | --- |']
    for row in report['checks']:
        lines.append('| ' + ' | '.join(str(row[key]).replace('|', '/') for key in ('name', 'status', 'evidence_level')) + ' |')
    lines += ['', 'Full acceptance requires measured 12-hour endurance and generated audible latency (median ≤200 ms, p95 ≤500 ms; at least20 measured samples). Cached or synthetic timings do not satisfy generated speech latency.',
              '', 'Physical receipt media must be reviewed by the owner/reviewer; this runner validates declared observations, source binding and file hashes only.', '', '## Artifacts', '']
    for artifact in report['artifacts']:
        lines.append('- `' + artifact['path'] + '` — SHA256 `' + artifact['sha256'] + '`')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--python', help='Defaults to this release .venv interpreter')
    parser.add_argument('--output', type=Path, default=Path('.local/kiosk-readiness/report.json'))
    parser.add_argument('--receipt', action='append', type=Path, default=[])
    parser.add_argument('--artifact', action='append', type=Path, default=[])
    parser.add_argument('--expected-sha256', action='append', default=[], metavar='PATH=HASH', help='Verify an artifact against a separately published digest')
    parser.add_argument('--quick', action='store_true', help='Run core checks; leave replay/native/extra checks explicitly not_run')
    parser.add_argument('--check', action='store_true', help='Plan and validate receipts/artifacts without executing tests; writes report only')
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    source = source_state(root)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    python = args.python or str(root / '.venv/bin/python')
    with tempfile.TemporaryDirectory(prefix='facebot-certify-') as directory:
        work = Path(directory)
        checks = software_checks(root, python, args.quick, args.check, work)
        replay = work / 'processor-replay.json'
        if replay.exists():
            shutil.copyfile(replay, output.with_name(output.stem + '-processor-replay.json'))
    artifacts = []
    expected = {}
    for binding in args.expected_sha256:
        try:
            name, digest = binding.rsplit('=', 1)
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError()
            expected[str(Path(name).resolve())] = digest
        except ValueError:
            parser.error('--expected-sha256 requires PATH=64-lowercase-hex-characters')
    for path in args.artifact:
        try:
            artifacts.append(artifact_record(path))
        except (OSError, ValueError, zipfile.BadZipFile):
            checks.append(item('artifact:' + path.name, 'fail', 'artifact_validation'))
    for name, digest in expected.items():
        matched = next((artifact for artifact in artifacts if artifact['path'] == name), None)
        checks.append(item('sha256:' + Path(name).name, 'pass' if matched and matched['sha256'] == digest else 'fail', 'artifact_validation'))
    apks = [artifact for artifact in artifacts if 'unpaired_apk' in artifact]
    checks.append(item('public_unpaired_apk', 'pass' if apks and all(a['unpaired_apk'] for a in apks) else 'fail' if apks else 'missing', 'artifact_validation'))
    receipts = [review_receipt(path, source['commit']) for path in args.receipt]
    checks.extend(receipts)
    for kind in PHYSICAL:
        matching = [row for row in receipts if row['name'] == kind]
        if not matching:
            checks.append(item(kind, 'missing', 'none'))
        elif len(matching) > 1:
            checks.append(item(kind + ':duplicate', 'invalid', 'conflicting_receipts', reason='Supply one authoritative receipt per kind'))
    clean = source['commit'] is not None and source['dirty'] is False
    checks.append(item('committed_source', 'pass' if clean else 'unverified', 'git_observation'))
    full = all(row['status'] == 'pass' for row in checks)
    report = {'schema_version': 1, 'generated_at': stamp(), 'source': source,
              'mode': 'check' if args.check else 'quick' if args.quick else 'full',
              'overall': 'internal_acceptance_passed' if full else 'not_fully_verified',
              'checks': checks, 'artifacts': artifacts}
    output.write_text(json.dumps(report, indent=2) + '\n')
    output.with_suffix('.md').write_text(markdown(report))
    print(json.dumps({'overall': report['overall'], 'report': str(output),
                      'statuses': {status: sum(row['status'] == status for row in checks)
                                   for status in sorted({row['status'] for row in checks})}}, indent=2))
    return 0 if full else 1 if any(row['status'] == 'fail' for row in checks) else 2


if __name__ == '__main__':
    raise SystemExit(main())
