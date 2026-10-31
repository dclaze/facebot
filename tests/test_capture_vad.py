"""CPU-only detector contract and negative controls; no speech/model downloads."""
import unittest
from unittest.mock import patch
import numpy as np
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADState, VADAnalyzer
from server.capture_vad import CaptureVAD, LENOVO_RAW_CAPTURE


class CaptureVADTests(unittest.TestCase):
    def test_only_exact_profile_enables_gain_and_existing_thresholds_stay(self):
        for profile, gain in (('',1),('unknown',1),('lenovo',1),(LENOVO_RAW_CAPTURE,4)):
            with self.subTest(profile=profile):
                vad=CaptureVAD(profile)
                self.addCleanup(vad._executor.shutdown)
                self.assertEqual(vad.confidence_gain,gain)
                self.assertEqual(vad.params.confidence,.7)
                self.assertEqual(vad.params.min_volume,.6)
                self.assertEqual(vad.params.start_secs,.1)
                self.assertEqual(vad.params.stop_secs,.45)

    def test_gain_is_saturating_and_cannot_change_original_pcm(self):
        vad=CaptureVAD(LENOVO_RAW_CAPTURE)
        self.addCleanup(vad._executor.shutdown)
        source=np.array([-32768,-9000,-1000,0,1000,9000,32767],dtype='<i2').tobytes()
        unchanged=bytes(source)
        with patch.object(SileroVADAnalyzer,'voice_confidence',return_value=.8) as model:
            self.assertEqual(vad.voice_confidence(source),.8)
            scaled=np.frombuffer(model.call_args.args[0],dtype='<i2').tolist()
        self.assertEqual(scaled,[-32768,-32768,-4000,0,4000,32767,32767])
        self.assertEqual(source,unchanged)

    def test_normal_profile_passes_original_bytes_to_model(self):
        vad=CaptureVAD()
        self.addCleanup(vad._executor.shutdown)
        pcm=bytes(1024)
        with patch.object(SileroVADAnalyzer,'voice_confidence',return_value=.8) as model:
            vad.voice_confidence(pcm)
            self.assertIs(model.call_args.args[0],pcm)

    def test_volume_analyzer_receives_unamplified_buffer(self):
        vad=CaptureVAD(LENOVO_RAW_CAPTURE)
        self.addCleanup(vad._executor.shutdown)
        vad.set_sample_rate(16000)
        pcm=np.full(512,1000,dtype='<i2').tobytes()
        with patch.object(SileroVADAnalyzer,'voice_confidence',return_value=.9) as model, \
             patch.object(vad,'_get_smoothed_volume',return_value=.2) as volume:
            self.assertEqual(vad._run_analyzer(pcm),VADState.QUIET)
            self.assertEqual(volume.call_args.args[0],pcm)
            self.assertTrue(np.all(np.frombuffer(model.call_args.args[0],dtype='<i2')==4000))

    def test_real_cpu_silero_keeps_silence_noise_and_tones_quiet(self):
        rng=np.random.default_rng(11);n=16000*3;t=np.arange(n)/16000
        fixtures={'silence':np.zeros(n),'white_noise':rng.normal(0,.01,n),
                  'low_noise':rng.normal(0,.0026,n),
                  'fan':.004*np.sin(2*np.pi*120*t)+rng.normal(0,.001,n),
                  'tone':.08*np.sin(2*np.pi*440*t),
                  'impulse':np.where(np.arange(n)%8000<80,.08,0)}
        for name,audio in fixtures.items():
            with self.subTest(name=name):
                vad=CaptureVAD(LENOVO_RAW_CAPTURE);vad.set_sample_rate(16000)
                self.addCleanup(vad._executor.shutdown)
                self.assertEqual(vad._model.session.get_providers(),['CPUExecutionProvider'])
                pcm=(np.clip(audio,-1,1)*32767).astype('<i2').tobytes()
                states=[vad._run_analyzer(pcm[offset:offset+640]) for offset in range(0,len(pcm),640)]
                self.assertNotIn(VADState.SPEAKING,states)

    def test_activity_counts_analysis_and_stable_transitions_without_content(self):
        vad=CaptureVAD();vad.set_sample_rate(16000)
        self.addCleanup(vad._executor.shutdown)
        pcm=bytes(1024)
        with patch.object(SileroVADAnalyzer,'voice_confidence',return_value=.9), \
             patch.object(VADAnalyzer,'_get_smoothed_volume',return_value=.8), \
             patch('server.capture_vad.time.monotonic',return_value=100):
            for _ in range(3):vad._run_analyzer(pcm)
        with patch.object(SileroVADAnalyzer,'voice_confidence',return_value=.1), \
             patch.object(VADAnalyzer,'_get_smoothed_volume',return_value=.2), \
             patch('server.capture_vad.time.monotonic',return_value=101):
            vad._run_analyzer(pcm) # STOPPING is not a stop event.
        with patch.object(SileroVADAnalyzer,'voice_confidence',return_value=.9), \
             patch.object(VADAnalyzer,'_get_smoothed_volume',return_value=.8):
            vad._run_analyzer(pcm) # SPEAKING continuation is not a new start.
        with patch.object(SileroVADAnalyzer,'voice_confidence',return_value=.1), \
             patch.object(VADAnalyzer,'_get_smoothed_volume',return_value=.2), \
             patch('server.capture_vad.time.monotonic',return_value=102):
            for _ in range(14):vad._run_analyzer(pcm)
        with patch('server.capture_vad.time.monotonic',return_value=103):
            activity=vad.report()['activity']
        self.assertEqual(activity['input_samples'],19*512)
        self.assertEqual(activity['input_frames'],19)
        self.assertEqual(activity['analysis_frames'],19)
        self.assertEqual(activity['candidate_frames'],4)
        self.assertEqual(activity['speech_starts'],1)
        self.assertEqual(activity['speech_stops'],1)
        self.assertEqual(activity['last_start_age_s'],3)
        self.assertEqual(activity['last_stop_age_s'],1)
        self.assertEqual(activity['state'],'quiet')
        self.assertEqual(activity['max_confidence'],.9)
        self.assertEqual(activity['max_volume'],.8)
        self.assertTrue(all(isinstance(v,(int,float,str,type(None))) for v in activity.values()))
        activity['speech_starts']=999
        self.assertEqual(vad.report()['activity']['speech_starts'],1)

    def test_partial_input_is_counted_without_claiming_analysis(self):
        vad=CaptureVAD();vad.set_sample_rate(16000)
        self.addCleanup(vad._executor.shutdown)
        self.assertIsNone(vad.report()['activity']['last_input_age_s'])
        vad._run_analyzer(bytes(640))
        activity=vad.report()['activity']
        self.assertEqual(activity['input_frames'],1)
        self.assertEqual(activity['input_samples'],320)
        self.assertEqual(activity['analysis_frames'],0)
        self.assertEqual(activity['candidate_frames'],0)
        self.assertIsNone(activity['last_start_age_s'])
