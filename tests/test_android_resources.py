"""Resource observer contracts; fake command output only, never actual ADB."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('android_resources', Path(__file__).resolve().parents[1] / 'scripts/observe-android-resources.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

BATTERY = '''Current Battery Service state:
  AC powered: false
  USB powered: true
  Wireless powered: false
  level: 82
  scale: 100
  temperature: 341
  technology: synthetic-private-value
'''


class ParserTests(unittest.TestCase):
    def test_device_selection_never_leaks_ids_and_refuses_ambiguity_or_replacement(self):
        self.assertEqual(observer.single_device('List of devices attached\nfixture-A\tdevice\n'), 'fixture-A')
        cases = [('fixture-A device\nfixture-B offline', 'ambiguous_devices'),
                 ('fixture-A unauthorized', 'device_not_authorized_or_ready'),
                 ('fixture-A offline', 'device_not_authorized_or_ready'),
                 ('', 'device_unavailable'), ('unexpected', 'invalid_device_inventory')]
        for raw, reason in cases:
            with self.subTest(reason=reason), self.assertRaises(observer.ObserverError) as caught:
                observer.single_device(raw)
            self.assertEqual(str(caught.exception), reason)
        with self.assertRaisesRegex(observer.ObserverError, '^device_changed$'):
            observer.single_device('fixture-B device', expected='fixture-A')

    def test_process_missing_differs_from_invalid_output(self):
        self.assertEqual(observer.parse_pids('55123 55123 55124\n'), (55123,55124))
        self.assertEqual(observer.parse_pids(''), ())
        for raw in ('permission denied', '-1', '0', '1;reboot', '9'*5000):
            self.assertIsNone(observer.parse_pids(raw))

    def test_pss_android_summary_and_legacy_table_without_guessing(self):
        self.assertEqual(observer.parse_pss(' TOTAL PSS: 12345 TOTAL RSS: 23456\n'), 12345)
        self.assertEqual(observer.parse_pss(' TOTAL 4321 123 456 12\n'), 4321)
        for raw in ('Permission Denial', ' TOTAL RSS: 111\n', ' TOTAL PSS: -1',
                    ' TOTAL PSS: 1\n TOTAL PSS: 2\n', ' TOTAL PSS: 12.5', ' TOTAL PSS: 12,345'):
            self.assertIsNone(observer.parse_pss(raw))

    def test_battery_strict_fields_temperature_units_and_unknowns(self):
        self.assertEqual(observer.parse_battery(BATTERY), dict(battery_plugged=True,
            battery_level_percent=82.0, battery_temperature_c=34.1))
        self.assertFalse(observer.parse_battery(BATTERY.replace('USB powered: true', 'USB powered: false'))['battery_plugged'])
        self.assertIsNone(observer.parse_battery('USB powered: false')['battery_plugged'])
        self.assertTrue(observer.parse_battery('USB powered: true')['battery_plugged'])
        for raw in ('level: 101\nscale: 100', 'level: 5\nscale: 0', 'level: 50',
                    'level: 4\nlevel: 5\nscale: 100'):
            self.assertIsNone(observer.parse_battery(raw)['battery_level_percent'])
        self.assertTrue(all(value is None for value in observer.parse_battery('unsupported').values()))

    def test_thermal_only_service_status_not_individual_sensor_guess(self):
        self.assertEqual(observer.parse_thermal('Thermal Status: 0\n'), 0)
        self.assertEqual(observer.parse_thermal(' Thermal Status: 4\n'), 4)
        for raw in ('Temperature{mStatus=4}', 'Thermal Status: 7', 'Thermal Status: -1',
                    'Thermal Status: 1\nThermal Status: 2', 'service not found'):
            self.assertIsNone(observer.parse_thermal(raw))


class CommandTests(unittest.TestCase):
    def runner(self, unavailable=False):
        self.calls = []
        def run(args, **kwargs):
            self.calls.append((args,kwargs))
            self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
            self.assertLessEqual(kwargs['timeout'], 5)
            tail = args[1:]
            if tail == ['devices']:
                data = b'List of devices attached\nprivate-device-fixture\tdevice\n'
            else:
                self.assertEqual(tail[:1], ['shell'])
                self.assertEqual(kwargs['env'].get('ANDROID_SERIAL'), 'private-device-fixture')
                self.assertNotIn('private-device-fixture', args)
                command = tail[1:]
                data = {('pidof','org.facebot'):b'55123\n',
                        ('dumpsys','meminfo','org.facebot'):b'TOTAL PSS: 12000\n',
                        ('dumpsys','battery'):BATTERY.encode(),
                        ('dumpsys','thermalservice'):b'Thermal Status: 0\n'}[tuple(command)]
                if unavailable and command == ['dumpsys','thermalservice']:
                    data = b'Cannot find service: thermalservice; private-device-fixture'
            return SimpleNamespace(returncode=0, stdout=data)
        return run

    def test_allowlisted_commands_and_numeric_projection_only(self):
        adb = observer.Adb(runner=self.runner(unavailable=True), clock=lambda:0)
        adb.select()
        row,pids = adb.sample(60)
        self.assertEqual(pids,(55123,))
        self.assertTrue(row['process_alive'])
        self.assertEqual(row['pss_kb'],12000)
        self.assertIsNone(row['thermal_status'])
        self.assertEqual(row['command_status']['thermal'],'unavailable')
        serialized=json.dumps(row)
        for private in ('private-device-fixture','synthetic-private-value','55123','Cannot find service'):
            self.assertNotIn(private,serialized)
        self.assertEqual(len(self.calls),6)

    def test_command_failures_have_fixed_codes_without_raw_exception(self):
        for failure, status in [(subprocess.TimeoutExpired('private-device-fixture',5,output=b'secret'), 'timeout'),
                                (OSError('secret'), 'unavailable')]:
            def run(*args, **kwargs):raise failure
            adb=observer.Adb(runner=run,clock=lambda:0)
            self.assertEqual(adb.command(['devices']), (None,status))
        runner=self.runner();adb=observer.Adb(runner=runner,clock=lambda:10)
        self.assertEqual(adb.command(['devices'],deadline=9), (None,'deadline_reached'))
        self.assertEqual(self.calls,[])
        adb.command(['devices'],deadline=11)
        self.assertEqual(self.calls[-1][1]['timeout'],1)

    def test_missing_process_is_false_but_disconnected_device_unknown(self):
        def runner(args,**kwargs):
            if args[-2:] == ['pidof','org.facebot']:
                return SimpleNamespace(returncode=1,stdout=b'')
            if args[-1]=='devices':return SimpleNamespace(returncode=0,stdout=b'fixture device')
            return SimpleNamespace(returncode=1,stdout=b'not available')
        adb=observer.Adb(runner=runner,clock=lambda:0);adb.select()
        row,pids=adb.sample(60)
        self.assertFalse(row['process_alive']);self.assertEqual(pids,())
        adb.runner=lambda *a,**kw:SimpleNamespace(returncode=0,stdout=b'List of devices attached\n')
        row,pids=adb.sample(60)
        self.assertFalse(row['device_available']);self.assertIsNone(row['process_alive']);self.assertIsNone(pids)


class ObserverTests(unittest.TestCase):
    def test_fixed_cadence_summary_and_pid_change_counts_without_pid_storage(self):
        now=[0.];rows=[];pids=iter([(55123,),None,(),(55124,)])
        def sample(deadline):
            identity=next(pids);now[0]+=3
            return dict(device_available=identity is not None, process_alive=None if identity is None else bool(identity),
                        process_count=None if identity is None else len(identity), pss_kb=12000,
                        battery_temperature_c=34.1,thermal_status=0),identity
        adb=SimpleNamespace(serial='private-device-fixture',sample=sample)
        result=observer.observe(adb,SimpleNamespace(write=rows.append),duration_seconds=240,
                                clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
        self.assertEqual(result,0)
        samples=[r for r in rows if r['type']=='resource_sample']
        self.assertEqual([r['elapsed_s'] for r in samples],[3,63,123,183])
        summary=rows[-1]
        self.assertEqual(summary['samples'],4)
        self.assertEqual(summary['pid_changes_observed'],1)
        self.assertEqual(summary['process_unknown_samples'],1)
        self.assertEqual(summary['process_absent_samples'],1)
        self.assertEqual(summary['max_sample_gap_s'],60)
        self.assertEqual(summary['elapsed_s'],240)
        self.assertIn('Point samples only',summary['evidence'])
        self.assertNotIn('private-device-fixture',json.dumps(rows))
        self.assertNotIn('55123',json.dumps(rows))

    def test_twelve_hour_bound_is_720_point_samples_with_no_deadline_probe(self):
        now=[0.];rows=[];starts=[]
        def sample(deadline):
            starts.append(now[0])
            return dict(device_available=True,process_alive=True,process_count=1,
                        pss_kb=None,battery_temperature_c=None,thermal_status=None),(1,)
        observer.observe(SimpleNamespace(serial='hidden',sample=sample),SimpleNamespace(write=rows.append),
                         duration_seconds=43200,clock=lambda:now[0],
                         sleep=lambda seconds:now.__setitem__(0,now[0]+seconds))
        self.assertEqual(len(starts),720)
        self.assertEqual(starts[0],0)
        self.assertEqual(starts[-1],43140)
        self.assertEqual(now[0],43200)
        self.assertEqual(rows[-1]['samples'],720)
        self.assertIsNone(rows[-1]['pss_kb_max'])

    def test_ambiguity_during_run_ends_with_safe_summary(self):
        rows=[]
        def sample(deadline):raise observer.ObserverError('ambiguous_devices')
        result=observer.observe(SimpleNamespace(serial='hidden',sample=sample),SimpleNamespace(write=rows.append),
                                duration_seconds=60,clock=lambda:0,sleep=lambda _:None)
        self.assertEqual(result,1);self.assertEqual(rows[-1]['reason'],'ambiguous_devices')
        self.assertEqual(rows[-1]['samples'],0)

    def test_duration_bounds_and_explicit_opt_in_precede_adb(self):
        for seconds in (0,59,43201,True,60.5):
            with self.assertRaises(ValueError):
                observer.observe(None,None,duration_seconds=seconds)
        with patch.object(observer,'Adb') as adb,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):observer.main(['--output','unused.jsonl'])
            with self.assertRaises(SystemExit):observer.main(['--observe-adb','--output','unused.jsonl','--duration-seconds','43201'])
            adb.assert_not_called()

    def test_receipts_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'private'/'observation.jsonl'
            sink=observer.Receipts(path);sink.write({'type':'fixture','value':None});sink.close()
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)
            original=path.read_bytes()
            with self.assertRaises(FileExistsError):observer.Receipts(path)
            self.assertEqual(path.read_bytes(),original)
