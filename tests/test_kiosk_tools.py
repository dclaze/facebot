"""Public setup/report tests use temporary files and command plans only."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


setup = module('setup_kiosk', 'setup-kiosk.py')
certify = module('certify_kiosk', 'certify-kiosk.py')


class KioskToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.commit = 'a' * 40

    def receipt(self, kind, metrics):
        artifact = self.root / 'observed.txt'
        artifact.write_text('An isolated fixture, never actual physical evidence.')
        path = self.root / (kind + '.json')
        path.write_text(json.dumps(dict(schema_version=1, kind=kind,
            evidence_level='physical_observation', source_commit=self.commit,
            measured_at=datetime.now(timezone.utc).isoformat(), scope='Test fixture only',
            artifacts=[dict(path=artifact.name, sha256=certify.sha256(artifact))], metrics=metrics)))
        return path

    def test_archive_metadata_is_labelled_declaration_not_verified_source(self):
        (self.root / 'SOURCE_COMMIT').write_text(self.commit + '\n')
        state = certify.source_state(self.root)
        self.assertEqual(state['commit'], self.commit)
        self.assertEqual(state['provenance'], 'archive_declaration')
        self.assertIsNone(state['dirty'])
        (self.root / 'SOURCE_COMMIT').write_text('not a commit')
        self.assertIsNone(certify.source_state(self.root)['commit'])

    def test_check_does_not_create_environment_or_token(self):
        before = list(self.root.iterdir())
        checks = setup.check(self.root, find=lambda _: None)
        self.assertFalse(checks['uv_or_python312'])
        self.assertEqual(list(self.root.iterdir()), before)

    def test_existing_token_never_rotated_and_new_token_private(self):
        self.assertTrue(setup.ensure_token(self.root))
        token = self.root / '.local/pairing-token'
        first = token.read_bytes()
        self.assertGreaterEqual(len(first), 24)
        self.assertEqual(token.stat().st_mode & 0o777, 0o600)
        self.assertFalse(setup.ensure_token(self.root))
        self.assertEqual(token.read_bytes(), first)
        token.write_text('bad')
        with self.assertRaises(ValueError): setup.ensure_token(self.root)
        self.assertEqual(token.read_text(), 'bad')

    def test_uv_plan_is_explicit_and_does_not_install_system_services(self):
        plan = setup.commands(self.root, find=lambda name: '/tools/' + name)
        self.assertEqual(plan[0][1:4], ['venv', '--python', '3.12'])
        self.assertTrue(any(command[1:3] == ['pip', 'sync'] for command in plan))
        self.assertIn(['/tools/ollama', 'pull', 'qwen2.5:1.5b'], plan)
        self.assertNotIn('brew', ' '.join(' '.join(command) for command in plan))
        self.assertNotIn('launchctl', ' '.join(' '.join(command) for command in plan))
        offline = setup.commands(self.root, skip_models=True, find=lambda name: '/tools/' + name)
        self.assertFalse(any(command[0].endswith('ollama') for command in offline))

    def test_python_fallback_uses_explicit_312_venv(self):
        plan = setup.commands(self.root, skip_models=True,
                              find=lambda name: '/tools/python3.12' if name == 'python3.12' else None)
        self.assertEqual(plan[0][:3], ['/tools/python3.12', '-m', 'venv'])
        self.assertIn('pip', plan[2])
        with self.assertRaises(ValueError): setup.commands(self.root, find=lambda _: None)

    def test_receipts_require_exact_source_and_real_artifact_hash(self):
        path = self.receipt('wifi', {flag: True for flag in certify.REQUIRED_FLAGS['wifi']})
        self.assertEqual(certify.review_receipt(path, self.commit)['status'], 'pass')
        self.assertEqual(certify.review_receipt(path, 'b'*40)['status'], 'invalid')
        (self.root / 'observed.txt').write_text('changed')
        self.assertEqual(certify.review_receipt(path, self.commit)['status'], 'invalid')

    def test_replay_and_short_run_cannot_satisfy_physical_endurance(self):
        path = self.receipt('endurance', dict(duration_hours=11.99, unexpected_failures=0))
        self.assertEqual(certify.review_receipt(path, self.commit)['status'], 'fail')
        value = json.loads(path.read_text())
        value['metrics']['duration_hours'] = 12
        value['evidence_level'] = 'simulation'
        path.write_text(json.dumps(value))
        self.assertEqual(certify.review_receipt(path, self.commit)['status'], 'invalid')

    def test_cached_latency_never_satisfies_generated_target(self):
        metrics = dict(timing_basis='utterance_end_to_audible_generated_speech',
                       cached_responses=True, samples=20, median_ms=50, p95_ms=100)
        path = self.receipt('generated_latency', metrics)
        self.assertEqual(certify.review_receipt(path, self.commit)['status'], 'fail')
        metrics['cached_responses'] = False
        path = self.receipt('generated_latency', metrics)
        self.assertEqual(certify.review_receipt(path, self.commit)['status'], 'pass')
        metrics['p95_ms'] = 501
        path = self.receipt('generated_latency', metrics)
        self.assertEqual(certify.review_receipt(path, self.commit)['status'], 'fail')

    def test_paired_apk_is_identified_without_extracting_secret(self):
        apk = self.root / 'app.apk'
        with zipfile.ZipFile(apk, 'w') as archive:
            archive.writestr('assets/local-config.json', '{"token":"fixture-secret"}')
        record = certify.artifact_record(apk)
        self.assertFalse(record['unpaired_apk'])
        self.assertNotIn('fixture-secret', json.dumps(record))

    def test_check_report_never_passes_missing_device_or_endurance(self):
        report = self.root / 'out/report.json'
        process = subprocess.run([sys.executable, str(ROOT / 'scripts/certify-kiosk.py'),
                                  '--check', '--root', str(self.root), '--output', str(report)],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        value = json.loads(report.read_text())
        self.assertEqual(value['overall'], 'not_fully_verified')
        checks = {row['name']: row['status'] for row in value['checks']}
        self.assertEqual(checks['device'], 'missing')
        self.assertEqual(checks['endurance'], 'missing')
        self.assertEqual(checks['generated_latency'], 'missing')
        self.assertFalse((self.root / '.venv').exists())

    def test_timed_out_test_is_terminated_and_reported_failed(self):
        row = certify.run_check('timeout-fixture', [sys.executable, '-c', 'import time; time.sleep(10)'], self.root, timeout=.05)
        self.assertEqual(row['status'], 'fail')
        self.assertEqual(row['exit_code'], 'timeout')


if __name__ == '__main__': unittest.main()
