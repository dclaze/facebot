"""Isolated HTTP evidence only. Never contacts the tablet or production host."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SPEC=importlib.util.spec_from_file_location('benchmark_device',Path(__file__).resolve().parents[1]/'scripts/benchmark-device.py')
benchmark=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)
TOKEN='synthetic-test-token-no-real-secret'
ID='12345678-abcd-4321-abcd-123456789abc'


class Sink:
    def __init__(self): self.rows=[]
    def write(self,row): self.rows.append(row)


class FakeClock:
    def __init__(self): self.now=0.
    def __call__(self): return self.now
    def sleep(self,value): self.now+=value


class DeviceBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.paths=[];self.receipt=False;self.connected=True;self.receipt_id=ID
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def respond(self,data,status=200):
                payload=json.dumps(data).encode();self.send_response(status)
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)))
                self.end_headers();self.wfile.write(payload)
            def do_GET(self):
                owner.paths.append(('GET',self.path))
                if self.headers.get('Authorization')!='Bearer '+TOKEN:
                    return self.respond({},403)
                if self.path=='/health': return self.respond({'status':'ready','private':'PRIVATE VISITOR SENTINEL'})
                if self.path=='/diagnostics':
                    voice={'silenced':False,'user_speaking':False,'bot_speaking':False,'response_pending':False} if owner.connected else None
                    samples=[{'id':owner.receipt_id,'status':'played','dispatch_to_native_ack_ms':189.,'transcript':'PRIVATE VISITOR SENTINEL'}] if owner.receipt else []
                    return self.respond({'voice_state':voice,'playback_probes':{'pending':None,'samples':samples},'token':TOKEN,'visitor':'PRIVATE VISITOR SENTINEL'})
                self.respond({},404)
            def do_POST(self):
                owner.paths.append(('POST',self.path));owner.receipt=True
                self.respond({'id':ID,'status':'queued','token':TOKEN})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=benchmark.Client('http://127.0.0.1:'+str(self.server.server_port),TOKEN,.5)
        self.clock=FakeClock();self.sink=Sink()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(1)
    def run_probe(self,**kwargs):
        return benchmark.run(self.client,self.sink,clock=self.clock,sleep=self.clock.sleep,**kwargs)
    def assert_private(self):
        serialized=json.dumps(self.sink.rows)
        self.assertNotIn(TOKEN,serialized);self.assertNotIn('PRIVATE VISITOR SENTINEL',serialized)
    def test_default_only_reads_health_and_connected_state(self):
        summary=self.run_probe()
        self.assertEqual(self.paths,[('GET','/health'),('GET','/diagnostics')])
        self.assertTrue(summary['ok']);self.assertEqual(summary['probe_count'],0)
        self.assertFalse(summary['continuous_uptime_proven']);self.assert_private()
    def test_explicit_rehearsal_reports_only_matching_native_receipt(self):
        summary=self.run_probe(rehearse=True,scenarios=('joke',),interval=.25)
        self.assertEqual([p for p in self.paths if p[0]=='POST'],[('POST','/owner/rehearse/joke')])
        self.assertEqual(summary['latency']['p50_ms'],189.)
        self.assertEqual(summary['played_count'],1);self.assert_private()
    def test_idle_timeout_does_not_trigger_audio(self):
        self.connected=False
        summary=self.run_probe(rehearse=True,scenarios=('joke',),idle_timeout=1,interval=.25)
        self.assertFalse(any(method=='POST' for method,_ in self.paths))
        self.assertEqual(next(r['status'] for r in self.sink.rows if r['type']=='probe'),'idle_timeout')
        self.assertFalse(summary['ok'])
    def test_short_soak_reports_actual_duration_not_overnight_claim(self):
        summary=self.run_probe(soak_seconds=1,interval=.25)
        self.assertEqual(summary['observed_soak_seconds'],1)
        self.assertEqual(summary['requested_soak_seconds'],1)
        self.assertEqual(summary['observed_disconnect_transitions'],0)
        self.assertFalse(summary['continuous_uptime_proven'])
        self.assertFalse(any(method=='POST' for method,_ in self.paths));self.assert_private()
    def test_unrelated_probe_receipt_cannot_satisfy_requested_id(self):
        self.receipt_id='12345678-abcd-4321-abcd-123456789def'
        summary=self.run_probe(rehearse=True,scenarios=('joke',),receipt_timeout=1,interval=.25)
        self.assertEqual(summary['played_count'],0)
        self.assertEqual(next(r['status'] for r in self.sink.rows if r['type']=='probe'),'receipt_wait_timeout')
    def test_soak_counts_observed_disconnect_and_reconnect(self):
        def sleep(value):
            self.clock.sleep(value)
            self.connected=not .5 <= self.clock.now < 1
        summary=benchmark.run(self.client,self.sink,soak_seconds=1,interval=.25,clock=self.clock,sleep=sleep)
        self.assertEqual(summary['observed_disconnect_transitions'],1)
        self.assertEqual(summary['disconnected_samples'],2)
        self.assertFalse(summary['ok'])
    def test_private_receipts_never_overwrite_and_urls_reject_credential_leaks(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'receipt.jsonl';receipt=benchmark.Receipts(path)
            receipt.write({'type':'synthetic-test'});receipt.close()
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):benchmark.Receipts(path)
        for value in ('http://8.8.8.8','https://user:password@example.com','https://example.com?token=secret','http://example.com'):
            with self.assertRaises(ValueError):benchmark.validate_base(value)


if __name__=='__main__':unittest.main()
