"""Real subprocess fault injection; no live Facebot, device, launchd or model calls."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/kiosk-service.py'
spec = importlib.util.spec_from_file_location('kiosk_service', SCRIPT)
kiosk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kiosk)

FAKE_SERVER = r'''
import json, os, signal, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
root = Path(sys.argv[1])
(root / 'observed.json').write_text(json.dumps({key:os.environ[key] for key in
 ['FACEBOT_PROFILE','FACEBOT_LLM','FACEBOT_TTS','FACEBOT_SPEECH_RATE','FACEBOT_KIOSK_MODE']}))
(root / 'vision-env.json').write_text(json.dumps({key:os.environ.get(key) for key in
 ['OLLAMA_HOST','OLLAMA_MODELS','OLLAMA_NUM_PARALLEL','OLLAMA_MAX_LOADED_MODELS','FACEBOT_VISION_URL','FACEBOT_TOKEN']}))
with (root / 'starts').open('a') as stream: stream.write(str(time.time()) + '\n')
print(os.environ.get('FACEBOT_TOKEN',''), flush=True)
mode = root / 'mode'
if mode.read_text() == 'exit': sys.exit(7)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if mode.read_text() == 'hang': time.sleep(30)
  value = {'status':'ready','profile':os.environ['FACEBOT_PROFILE'], 'etag':'fixture', 'tts':{'backend':os.environ['FACEBOT_TTS']}}
  if self.path == '/api/tags': value = {'models':[]}
  if mode.read_text() == 'wrong_profile': value['profile'] = 'wrong'
  raw = json.dumps(value).encode()
  self.send_response(200); self.end_headers(); self.wfile.write(raw)
 def log_message(self,*args): pass
HTTPServer(('127.0.0.1', int(sys.argv[2])), Handler).serve_forever()
'''


def wait_for(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('Timed out waiting for isolated fixture condition')


class KioskRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.fixture = self.root / 'server.py'
        self.fixture.write_text(FAKE_SERVER)
        self.token = 'private-pairing-token-do-not-log-123456'
        (self.root / 'token').write_text(self.token)
        (self.root / 'mode').write_text('ready')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.config = dict(root=str(self.root), command=[sys.executable, str(self.fixture), str(self.root), str(port)],
                           token_file=str(self.root / 'token'), port=port, profile='halloween',
                           model='qwen2.5:1.5b', tts='kokoro', speech_rate=1.12,
                           interval=.05, health_timeout=.08, health_failures=2, startup_timeout=.4,
                           stop_timeout=.1, backoff_initial=.1, backoff_max=.4, stable_reset=2)
        self.supervisor = kiosk.Supervisor(self.config, self.state, self.root / 'owner.lock')
        self.thread = None

    def tearDown(self):
        self.supervisor.stop_event.set()
        if self.thread:
            self.thread.join(5)
            self.assertFalse(self.thread.is_alive())
        self.temp.cleanup()

    def start(self):
        self.thread = threading.Thread(target=self.supervisor.run)
        self.thread.start()

    def status(self):
        try:
            return json.loads((self.state / 'status.json').read_text())
        except FileNotFoundError:
            return {}

    def ready(self):
        return wait_for(lambda: self.status().get('phase') == 'ready')

    def test_lan_host_validation_accepts_only_rfc1918_ipv4(self):
        for host in ('10.2.3.4', '172.16.1.2', '172.31.255.254', '192.168.4.12'):
            self.assertTrue(kiosk.private_lan_host(host))
        for host in ('0.0.0.0', '127.0.0.1', '172.32.1.2', '169.254.1.2', '8.8.8.8', '::1'):
            self.assertFalse(kiosk.private_lan_host(host))

    def test_install_config_requires_explicit_lan_opt_in_and_preserves_arguments(self):
        args = SimpleNamespace(root=str(SCRIPT.parents[1]), python=sys.executable,
                               token_file=str(self.root / 'token'), profile='halloween',
                               model='qwen2.5:1.5b', tts='kokoro', speech_rate=1.12,
                               host='192.168.1.50', trusted_lan=False, port=8765, no_admin=True)
        with self.assertRaises(ValueError): kiosk.build_config(args)
        args.trusted_lan = True
        config = kiosk.build_config(args)
        self.assertEqual(config['host'], args.host)
        self.assertEqual(config['command'][-1], '--allow-private-lan')
        self.assertIn(args.host, config['command'])
        self.assertEqual(config['profile'], args.profile)
        self.assertEqual(config['model'], args.model)
        self.assertEqual(config['tts'], args.tts)
        args.host = '0.0.0.0'
        with self.assertRaises(ValueError): kiosk.build_config(args)

    def configure_admin_fixture(self):
        directory = self.root / 'admin-fixture'
        directory.mkdir()
        (directory / 'mode').write_text('ready')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.config['admin'] = dict(role='admin', host='127.0.0.1', port=port,
            command=[sys.executable, str(self.fixture), str(directory), str(port)])
        return directory

    def admin_ready(self):
        def ready():
            try:
                return json.loads((self.state / 'admin/status.json').read_text()).get('phase') == 'ready'
            except FileNotFoundError:
                return False
        wait_for(ready)

    def test_vision_ollama_config_is_opt_in_loopback_and_dedicated_models(self):
        args = SimpleNamespace(root=str(SCRIPT.parents[1]), python=sys.executable,
                               token_file=str(self.root / 'token'), profile='halloween',
                               model='qwen2.5:1.5b', tts='kokoro', speech_rate=1.12,
                               host='127.0.0.1', trusted_lan=False, port=8765, no_admin=True)
        self.assertNotIn('vision_ollama', kiosk.build_config(args))
        args.vision_ollama = sys.executable
        config = kiosk.build_config(args)
        vision = config['vision_ollama']
        self.assertEqual((vision['host'], vision['port']), ('127.0.0.1', 11435))
        self.assertEqual(vision['command'], [str(Path(sys.executable).resolve()), 'serve'])
        self.assertEqual(Path(vision['models_dir']), (SCRIPT.parents[1] / '.local/ollama-vision/models').resolve())
        args.vision_models = str(self.root / 'models')
        self.assertEqual(kiosk.build_config(args)['vision_ollama']['models_dir'], str(Path(args.vision_models).resolve()))
        args.port = 11435
        with self.assertRaises(ValueError): kiosk.build_config(args)
        args.port = 8765
        args.vision_ollama = str(self.root / 'absent')
        with self.assertRaises(ValueError): kiosk.build_config(args)
        args.vision_ollama = None
        with self.assertRaises(ValueError): kiosk.build_config(args)

    def test_vision_ollama_recovers_death_and_hang_independently_then_reaps(self):
        self.configure_admin_fixture()
        directory = self.root / 'vision-fixture'
        directory.mkdir()
        (directory / 'mode').write_text('ready')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.config['vision_ollama'] = dict(role='vision_ollama', host='127.0.0.1', port=port,
            models_dir=str(directory / 'models'),
            command=[sys.executable, str(self.fixture), str(directory), str(port)])
        self.start()
        self.ready()
        self.admin_ready()
        def vision_ready():
            try: return json.loads((self.state / 'vision_ollama/status.json').read_text()).get('phase') == 'ready'
            except FileNotFoundError: return False
        wait_for(vision_ready)
        voice_pid, admin_pid = self.supervisor.child.pid, self.supervisor.admin.child.pid
        sidecar = self.supervisor.vision_ollama
        first = sidecar.child.pid
        observed = json.loads((directory / 'vision-env.json').read_text())
        self.assertEqual(observed['OLLAMA_HOST'], f'127.0.0.1:{port}')
        self.assertEqual(observed['OLLAMA_MODELS'], str(directory / 'models'))
        self.assertEqual(observed['OLLAMA_NUM_PARALLEL'], '1')
        self.assertEqual(observed['OLLAMA_MAX_LOADED_MODELS'], '1')
        self.assertIsNone(observed['FACEBOT_TOKEN'])
        self.assertEqual(json.loads((self.root / 'vision-env.json').read_text())['FACEBOT_VISION_URL'],
                         f'http://127.0.0.1:{port}/api/chat')
        self.assertIsNone(self.supervisor.admin.vision_ollama)
        self.assertIsNone(sidecar.admin)
        os.kill(first, signal.SIGKILL)
        wait_for(lambda: sidecar.child and sidecar.child.pid != first)
        wait_for(vision_ready)
        second = sidecar.child.pid
        (directory / 'mode').write_text('hang')
        wait_for(lambda: sidecar.restarts >= 2)
        (directory / 'mode').write_text('ready')
        wait_for(lambda: sidecar.child and sidecar.child.pid != second)
        wait_for(vision_ready)
        self.assertEqual((self.supervisor.child.pid, self.supervisor.admin.child.pid), (voice_pid, admin_pid))
        final = sidecar.child.pid
        self.supervisor.stop_event.set()
        self.thread.join(4)
        self.assertFalse(self.thread.is_alive())
        for pid in (first, second, final, voice_pid, admin_pid):
            with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    def test_admin_and_voice_crashes_recover_independently_then_both_reap(self):
        self.configure_admin_fixture()
        self.start()
        self.ready()
        self.admin_ready()
        voice_pid = self.supervisor.child.pid
        admin_pid = self.supervisor.admin.child.pid
        os.kill(admin_pid, signal.SIGKILL)
        wait_for(lambda: self.supervisor.admin.child and self.supervisor.admin.child.pid != admin_pid)
        self.admin_ready()
        self.assertEqual(self.supervisor.child.pid, voice_pid)
        admin_pid = self.supervisor.admin.child.pid
        os.kill(voice_pid, signal.SIGKILL)
        wait_for(lambda: self.supervisor.child and self.supervisor.child.pid != voice_pid)
        self.ready()
        self.assertEqual(self.supervisor.admin.child.pid, admin_pid)
        voice_pid = self.supervisor.child.pid
        self.supervisor.stop_event.set()
        self.thread.join(4)
        self.assertFalse(self.thread.is_alive())
        for pid in (voice_pid, admin_pid):
            with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    def test_hung_admin_recovers_without_interrupting_voice(self):
        directory = self.configure_admin_fixture()
        self.start()
        self.ready()
        self.admin_ready()
        voice_pid = self.supervisor.child.pid
        admin_pid = self.supervisor.admin.child.pid
        (directory / 'mode').write_text('hang')
        wait_for(lambda: self.supervisor.admin.restarts >= 1)
        (directory / 'mode').write_text('ready')
        wait_for(lambda: self.supervisor.admin.child and self.supervisor.admin.child.pid != admin_pid)
        self.admin_ready()
        self.assertEqual(self.supervisor.child.pid, voice_pid)
        self.assertTrue(kiosk.healthy(self.config))

    def test_admin_install_defaults_host_only_and_requires_explicit_private_owner(self):
        root = self.root / 'release'
        (root / 'server').mkdir(parents=True)
        (root / 'server/app.py').touch()
        (root / 'server/admin.py').touch()
        (root / '.local').mkdir()
        (root / '.local/pairing-token').write_text(self.token)
        args = SimpleNamespace(root=str(root), python=sys.executable, token_file=None,
                               profile='halloween', model='qwen2.5:1.5b', tts='kokoro', speech_rate=1.12,
                               host='192.168.1.50', trusted_lan=True, port=8765, owner_client=[])
        config = kiosk.build_config(args)
        self.assertTrue(config['prevent_sleep'])
        self.assertEqual(config['admin']['host'], args.host)
        self.assertEqual(config['admin']['port'], 8766)
        self.assertNotIn('--allow-client', config['admin']['command'])
        args.owner_client = ['192.168.1.60']
        self.assertEqual(kiosk.build_config(args)['admin']['command'][-2:], ['--allow-client', '192.168.1.60'])
        args.owner_client = ['8.8.8.8']
        with self.assertRaises(ValueError): kiosk.build_config(args)
        args.owner_client = []
        args.port = 9000
        with self.assertRaises(ValueError): kiosk.build_config(args)
        args.no_admin = args.no_sleep_protection = True
        config = kiosk.build_config(args)
        self.assertNotIn('admin', config)
        self.assertFalse(config['prevent_sleep'])

    def test_sleep_guard_is_scoped_to_stop_and_reaps_its_owned_helper(self):
        stop = threading.Event()
        guard = kiosk.SleepGuard(stop, self.supervisor.logger,
                                 command=[sys.executable, '-c', 'import time; time.sleep(30)'])
        thread = threading.Thread(target=guard.run)
        thread.start()
        try:
            wait_for(guard.active)
            pid = guard.process.pid
            stop.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertFalse(guard.active())
            with self.assertRaises(ProcessLookupError): os.kill(pid, 0)
        finally:
            stop.set()
            thread.join(5)
        self.assertEqual(kiosk.SleepGuard(stop, self.supervisor.logger).command,
                         ['/usr/bin/caffeinate', '-i', '-w', str(os.getpid())])

    def test_usb_selection_is_authorized_unique_and_never_in_command_arguments(self):
        adb = self.root / 'adb'
        adb.write_text('test fixture')
        adb.chmod(0o700)
        inventory = 'List of devices attached\nfixture-usb device usb:123 product:fixture\n192.168.1.3:5555 device product:wireless\n'
        with patch.object(kiosk.subprocess, 'run', return_value=SimpleNamespace(stdout=inventory)) as command:
            selected = kiosk.select_usb_tablet(str(adb))
            self.assertEqual(selected['serial'], 'fixture-usb')
            self.assertNotIn('fixture-usb', command.call_args.args[0])
            self.assertEqual(command.call_args.args[0][1:], ['devices', '-l'])
        for inventory in ('fixture-usb unauthorized usb:123\n',
                          'first device usb:1\nsecond device usb:2\n',
                          '192.168.1.3:5555 device usb:fake\n'):
            with patch.object(kiosk.subprocess, 'run', return_value=SimpleNamespace(stdout=inventory)):
                with self.assertRaises(ValueError): kiosk.select_usb_tablet(str(adb))

    def test_tablet_identifier_is_private_config_only(self):
        args = type('Args', (), {})()
        destination = self.root / 'fixture.plist'
        config = {**self.config, 'tablet_watchdog_selection': dict(enabled=True, adb='/fixture/adb',
                    serial='fixture-private-identifier', interval_s=5, max_restarts_per_10min=3)}
        with patch.object(kiosk, 'is_loaded', return_value=False), \
             patch.object(kiosk, 'build_config', return_value=config), \
             patch.object(kiosk, 'port_occupied', return_value=False), \
             patch.object(kiosk, 'plist_path', return_value=destination), \
             patch.object(kiosk, 'launchctl'):
            kiosk.install(args, self.state)
        private = self.state / 'tablet-watchdog.json'
        self.assertEqual(json.loads(private.read_text())['serial'], 'fixture-private-identifier')
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        for public in (destination, self.state / 'config.json'):
            self.assertNotIn('fixture-private-identifier', public.read_text())
        command = json.loads((self.state / 'config.json').read_text())['tablet_watchdog']['command']
        self.assertEqual(command[-2:], ['--config', str(private)])

    def test_tablet_helper_has_one_owner_and_stops_with_voice_and_admin(self):
        self.configure_admin_fixture()
        self.config['tablet_watchdog'] = {'command': [sys.executable, '-c', 'import time; time.sleep(30)']}
        self.start()
        self.ready()
        self.admin_ready()
        wait_for(lambda: self.supervisor.tablet_guard and self.supervisor.tablet_guard.active())
        self.assertIsNone(self.supervisor.admin.tablet_guard)
        helper_pid = self.supervisor.tablet_guard.process.pid
        self.supervisor.stop_event.set()
        self.thread.join(4)
        self.assertFalse(self.thread.is_alive())
        with self.assertRaises(ProcessLookupError): os.kill(helper_pid, 0)

    def test_child_death_recovers_same_configuration_without_token_logs(self):
        self.start()
        self.ready()
        first = self.supervisor.child.pid
        os.kill(first, signal.SIGKILL)
        wait_for(lambda: self.supervisor.child and self.supervisor.child.pid != first)
        self.ready()
        observed = json.loads((self.root / 'observed.json').read_text())
        self.assertEqual(observed, dict(FACEBOT_PROFILE='halloween', FACEBOT_LLM='qwen2.5:1.5b',
                                       FACEBOT_TTS='kokoro', FACEBOT_SPEECH_RATE='1.12', FACEBOT_KIOSK_MODE='1'))
        self.assertGreaterEqual(self.status()['restarts'], 1)
        self.assertNotIn(self.token, (self.state / 'recovery.log').read_text())

    def test_hung_child_is_killed_and_recovers(self):
        self.start()
        self.ready()
        first = self.supervisor.child.pid
        (self.root / 'mode').write_text('hang')
        wait_for(lambda: self.status().get('reason') == 'health_timeout')
        (self.root / 'mode').write_text('ready')
        wait_for(lambda: self.supervisor.child and self.supervisor.child.pid != first)
        self.ready()
        with self.assertRaises(ProcessLookupError):
            os.kill(first, 0)

    def transient_listener_recovers(self, role):
        # Use the production crash-loop maximum: the previous code reused this
        # 60-second delay even for an old listener disappearing during bootout.
        self.config.update(role=role, backoff_max=60)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', self.config['port']))
            listener.listen()
            self.start()
            wait_for(lambda: self.status().get('phase') == 'port_conflict')
            self.assertIsNone(self.supervisor.child)
            self.assertFalse((self.root / 'starts').exists())
        started = time.monotonic()
        wait_for(lambda: self.status().get('phase') == 'ready', timeout=2)
        self.assertLess(time.monotonic() - started, 2)

    def test_voice_recovers_promptly_after_transient_old_listener_releases(self):
        self.transient_listener_recovers('voice')

    def test_admin_recovers_promptly_after_transient_old_listener_releases(self):
        self.transient_listener_recovers('admin')

    def test_occupied_port_recheck_has_independent_capped_backoff(self):
        class RecordedStop:
            def __init__(self): self.waits = []; self.stopped = False
            def is_set(self): return self.stopped or len(self.waits) >= 8
            def wait(self, seconds): self.waits.append(seconds)
            def set(self): self.stopped = True
        stop = RecordedStop()
        self.supervisor.stop_event = stop
        self.config['backoff_max'] = 60
        with patch.object(kiosk, 'port_occupied', return_value=True):
            self.supervisor.run()
        self.assertEqual(stop.waits, [.25, .5, 1, 2, 4, 5, 5, 5])
        self.assertIsNone(self.supervisor.child)
        self.assertFalse((self.root / 'starts').exists())

    def test_foreign_listener_is_never_killed_or_adopted(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', self.config['port']))
            listener.listen()
            self.start()
            wait_for(lambda: self.status().get('phase') == 'port_conflict')
            self.assertIsNone(self.supervisor.child)
            self.assertFalse((self.root / 'starts').exists())
        self.ready()

    def test_second_supervisor_cannot_start_or_overwrite_owner(self):
        self.start()
        self.ready()
        second = kiosk.Supervisor(self.config, self.root / 'other-state', self.root / 'owner.lock')
        self.assertEqual(second.run(), 73)
        self.assertEqual(len((self.root / 'starts').read_text().splitlines()), 1)
        self.assertFalse((self.root / 'other-state/status.json').exists())

    def test_crash_loop_has_capped_exponential_backoff(self):
        (self.root / 'mode').write_text('exit')
        self.start()
        # The in-memory count advances before its log record is emitted.
        wait_for(lambda: (self.state / 'recovery.log').exists() and
                 (self.state / 'recovery.log').read_text().count('"phase": "backoff"') >= 4)
        entries = [json.loads(line) for line in (self.state / 'recovery.log').read_text().splitlines()]
        retries = [entry['retry_seconds'] for entry in entries if entry['phase'] == 'backoff']
        self.assertEqual(retries[:4], [.1, .2, .4, .4])
        starts = [float(value) for value in (self.root / 'starts').read_text().splitlines()]
        for difference, lower_bound in zip([b-a for a,b in zip(starts,starts[1:])], [.1, .2, .4]):
            self.assertGreaterEqual(difference, lower_bound)

    def test_wrong_health_configuration_times_out_startup(self):
        (self.root / 'mode').write_text('wrong_profile')
        self.start()
        wait_for(lambda: self.status().get('reason') == 'startup_timeout')
        self.assertNotIn('"phase": "ready"', (self.state / 'recovery.log').read_text())

    def test_stop_reaps_term_ignoring_child_and_releases_lease(self):
        self.start()
        self.ready()
        child = self.supervisor.child.pid
        self.supervisor.stop_event.set()
        self.thread.join(3)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.status()['phase'], 'stopped')
        with self.assertRaises(ProcessLookupError): os.kill(child, 0)
        second = kiosk.Supervisor(self.config, self.state, self.root / 'owner.lock')
        second.stop_event.set()
        self.assertEqual(second.run(), 0)

    def test_lifecycle_logs_rotate_with_bounded_retention(self):
        self.start()
        self.ready()
        for _ in range(3500):
            self.supervisor.logger.info('x' * 300)
        logs = list(self.state.glob('recovery.log*'))
        self.assertEqual(len(logs), 3)
        self.assertLessEqual(sum(path.stat().st_size for path in logs), 3 * 262144)

    def test_generated_launchagent_retains_process_group_and_no_token(self):
        args = type('Args', (), {})()
        destination = self.root / 'fixture.plist'
        with patch.object(kiosk, 'is_loaded', return_value=False), \
             patch.object(kiosk, 'build_config', return_value=self.config), \
             patch.object(kiosk, 'port_occupied', return_value=False), \
             patch.object(kiosk, 'plist_path', return_value=destination), \
             patch.object(kiosk, 'launchctl') as launch:
            kiosk.install(args, self.state)
        plist = kiosk.plistlib.loads(destination.read_bytes())
        self.assertFalse(plist['AbandonProcessGroup'])
        self.assertTrue(plist['KeepAlive'])
        self.assertGreaterEqual(plist['ThrottleInterval'], 30)
        self.assertEqual(plist['StandardErrorPath'], '/dev/null')
        self.assertNotIn(self.token, destination.read_text())
        self.assertNotIn(self.token, (self.state / 'config.json').read_text())
        launch.assert_called_once()


class LaunchctlTransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plist = Path(self.temp.name) / 'fixture.plist'
        self.plist.write_text('isolated fixture')
        self.now = 0.
        self.sleeps = []
        def sleep(duration):
            self.sleeps.append(duration)
            self.now += duration
        for patcher in (patch.object(kiosk, 'plist_path', return_value=self.plist),
                        patch.object(kiosk.time, 'monotonic', side_effect=lambda: self.now),
                        patch.object(kiosk.time, 'sleep', side_effect=sleep)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_restart_waits_for_unload_then_recovers_transient_bootstrap_failure(self):
        events = []
        loaded = iter([True, True, False, False, False])
        attempts = 0
        def observe(**kwargs):
            value = next(loaded)
            events.append(('loaded', value))
            return value
        def command(*args, **kwargs):
            nonlocal attempts
            events.append((args[0], None))
            if args[0] == 'bootstrap':
                attempts += 1
                if attempts == 1:
                    raise subprocess.CalledProcessError(5, ['launchctl', 'bootstrap'])
        with patch.object(kiosk, 'is_loaded', side_effect=observe), \
             patch.object(kiosk, 'launchctl', side_effect=command):
            kiosk.restart_service()
        self.assertEqual(attempts, 2)
        self.assertLess(events.index(('loaded', False)), events.index(('bootstrap', None)))
        self.assertEqual(self.sleeps, [.25, .25])

    def test_permanent_bootstrap_failure_stops_at_deadline_without_busy_loop(self):
        error = subprocess.CalledProcessError(5, ['launchctl', 'bootstrap'])
        with patch.object(kiosk, 'is_loaded', return_value=False), \
             patch.object(kiosk, 'launchctl', side_effect=error) as command:
            with self.assertRaises(TimeoutError):
                kiosk.start_service(timeout=1)
        self.assertEqual(self.now, 1)
        self.assertEqual(self.sleeps, [.25, .5, .25])
        self.assertEqual(command.call_count, 3)
        for call in command.call_args_list:
            self.assertLessEqual(call.kwargs['timeout'], 1)

    def test_start_and_stop_are_idempotent(self):
        with patch.object(kiosk, 'is_loaded', return_value=True), \
             patch.object(kiosk, 'launchctl') as command:
            kiosk.start_service()
            kiosk.start_service()
            command.assert_not_called()
        with patch.object(kiosk, 'is_loaded', return_value=False), \
             patch.object(kiosk, 'launchctl') as command:
            kiosk.stop_service()
            kiosk.stop_service()
            command.assert_not_called()
        self.assertEqual(self.sleeps, [])

    def test_concurrent_stop_error_accepts_observed_unloaded_state(self):
        with patch.object(kiosk, 'is_loaded', side_effect=[True, False]), \
             patch.object(kiosk, 'launchctl', side_effect=subprocess.CalledProcessError(3, ['launchctl', 'bootout'])):
            kiosk.stop_service()
        self.assertEqual(self.sleeps, [])

    def test_unload_deadline_does_not_bootstrap_a_competing_job(self):
        with patch.object(kiosk, 'is_loaded', return_value=True), \
             patch.object(kiosk, 'launchctl') as command:
            with self.assertRaises(TimeoutError):
                kiosk.stop_service(timeout=.5)
        self.assertEqual(self.now, .5)
        self.assertEqual(command.call_args.args[0], 'bootout')
        self.assertEqual(command.call_count, 1)

    def test_concurrent_start_failure_returns_if_job_is_now_loaded(self):
        with patch.object(kiosk, 'is_loaded', side_effect=[False, True]), \
             patch.object(kiosk, 'launchctl', side_effect=subprocess.CalledProcessError(5, ['launchctl', 'bootstrap'])) as command:
            kiosk.start_service()
        self.assertEqual(command.call_count, 1)
        self.assertEqual(self.sleeps, [.25])


if __name__ == '__main__': unittest.main()
