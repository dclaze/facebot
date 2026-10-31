"""Pure fake-ADB watchdog tests: no device, shell or production process touched."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('tablet_watchdog',Path(__file__).resolve().parents[1]/'scripts/tablet-watchdog.py')
module=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(module)


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        folder=Path(self.tmp.name)
        self.config=dict(enabled=True,adb='/synthetic/adb',serial='PRIVATE-SYNTHETIC-SERIAL',
                         pause_file=str(folder/'pause'),state_file=str(folder/'state.json'),
                         interval_s=5,max_restarts_per_10min=3)
        self.calls=[];self.now=1000.;self.present=False;self.connected=True;self.pid_error=False
        def runner(args,**kwargs):
            self.calls.append((args,kwargs))
            if args[1:]==['get-state']:
                return SimpleNamespace(returncode=0,stdout='device' if self.connected else 'offline',stderr='')
            if args[1:]==['shell','pidof','org.facebot']:
                return SimpleNamespace(returncode=127 if self.pid_error else 0 if self.present else 1,
                                       stdout='1234\n' if self.present else '',stderr='')
            self.assertEqual(args[1:],['shell','am','start','-n','org.facebot/.FaceActivity'])
            return SimpleNamespace(returncode=0,stdout='Starting synthetic activity',stderr='')
        self.runner=runner
        self.watchdog=module.Watchdog(self.config,runner=runner,wallclock=lambda:self.now)
    def launches(self):return [args for args,kwargs in self.calls if 'start' in args]
    def test_absent_process_only_restarts_without_identifier_in_argv(self):
        self.assertEqual(self.watchdog.check()['state'],'restart_requested')
        self.assertEqual(len(self.launches()),1)
        for args,kwargs in self.calls:
            self.assertNotIn(self.config['serial'],' '.join(args))
            self.assertEqual(kwargs['env']['ANDROID_SERIAL'],self.config['serial'])
        self.assertEqual(Path(self.config['state_file']).stat().st_mode & 0o777,0o600)
    def test_running_process_never_steals_foreground(self):
        self.present=True
        self.assertEqual(self.watchdog.check()['state'],'process_present')
        self.assertFalse(self.launches());self.assertFalse(Path(self.config['state_file']).exists())
    def test_pause_disabled_offline_and_ambiguous_errors_never_launch(self):
        Path(self.config['pause_file']).touch();self.assertEqual(self.watchdog.check()['state'],'paused');self.assertFalse(self.calls)
        Path(self.config['pause_file']).unlink();self.config['enabled']=False
        self.assertEqual(self.watchdog.check()['state'],'process_absent_observing')
        self.config['enabled']=True;self.connected=False
        self.assertEqual(self.watchdog.check()['state'],'device_unavailable')
        self.connected=True;self.pid_error=True
        self.assertEqual(self.watchdog.check()['state'],'process_check_failed');self.assertFalse(self.launches())
    def test_rate_limit_survives_new_watchdog_and_expires_after_ten_minutes(self):
        for _ in range(3):
            self.assertEqual(self.watchdog.check()['state'],'restart_requested');self.now+=31
        replacement=module.Watchdog(self.config,runner=self.runner,wallclock=lambda:self.now)
        self.assertEqual(replacement.check()['state'],'restart_limited');self.assertEqual(len(self.launches()),3)
        self.now+=600;self.assertEqual(replacement.check()['state'],'restart_requested')
    def test_backoff_and_corrupt_future_state_fail_closed(self):
        self.watchdog.check();self.assertEqual(self.watchdog.check()['state'],'restart_backoff')
        path=Path(self.config['state_file']);path.write_text('{bad')
        self.assertEqual(self.watchdog.check()['state'],'state_error')
        path.write_text(json.dumps({'attempts':[self.now+100]}))
        self.assertEqual(self.watchdog.check()['state'],'state_error');self.assertEqual(len(self.launches()),1)
    def test_termination_signal_prevents_pending_restart(self):
        watchdog=module.Watchdog(self.config,runner=self.runner,wallclock=lambda:self.now,should_stop=lambda:True)
        self.assertEqual(watchdog.check()['state'],'stopping');self.assertFalse(self.launches())
    def test_config_defaults_observe_and_rejects_unsafe_bounds(self):
        config=dict(self.config);config.pop('enabled');path=Path(self.tmp.name)/'config.json';path.write_text(json.dumps(config))
        self.assertFalse(module.load_config(path)['enabled'])
        config['interval_s']=.01;path.write_text(json.dumps(config))
        with self.assertRaises(module.ConfigError):module.load_config(path)


if __name__=='__main__':unittest.main()
