import json
import unittest
from pipecat.frames.frames import OutputTransportMessageFrame, OutputAudioRawFrame, InterruptionFrame
from server.network import validate_bind
from server.protocol import FaceSerializer
from server.playback_probe import PlaybackProbes


class BindTests(unittest.TestCase):
    def test_cleartext_requires_explicit_private_ipv4_opt_in(self):
        validate_bind('127.0.0.1')
        for host in ['192.168.4.32', '10.1.2.3', '172.16.2.5']:
            with self.assertRaises(ValueError): validate_bind(host)
            validate_bind(host, allow_private_lan=True)
        for host in ['0.0.0.0', '8.8.8.8', '169.254.1.2', '224.1.2.3', 'example.com', '::']:
            with self.assertRaises(ValueError): validate_bind(host, allow_private_lan=True)
        with self.assertRaises(ValueError): validate_bind('127.0.0.1', cert='only-cert')


class FaceCueTests(unittest.IsolatedAsyncioTestCase):
    async def test_playback_probe_requires_matching_epoch_and_real_progress(self):
        now = [0.]
        probes = PlaybackProbes(clock=lambda: now[0])
        serializer = FaceSerializer(probes=probes)
        identifier = probes.begin('joke')
        cue = json.loads(await serializer.serialize(OutputTransportMessageFrame(message={'type':'playback_probe','id':identifier})))
        self.assertEqual(cue['offset'], 0)
        now[0] = .123
        def receipt(epoch, sample):
            return json.dumps({'type':'playback_receipt','id':identifier,'epoch':epoch,'sample':sample})
        await serializer.deserialize(receipt(1, 50))
        await serializer.deserialize(receipt(0, 0))
        self.assertEqual(probes.report()['samples'], [])
        await serializer.deserialize(receipt(0, 50))
        self.assertEqual(probes.report()['samples'][0]['dispatch_to_native_ack_ms'], 123)
        await serializer.deserialize(receipt(0, 51))
        self.assertEqual(len(probes.report()['samples']), 1)
        probes.begin('welcome')
        await serializer.serialize(InterruptionFrame())
        self.assertEqual(probes.report()['samples'][-1]['status'], 'cancelled')
        probes.begin('candy')
        now[0] += 16
        self.assertEqual(probes.report()['samples'][-1]['status'], 'timeout')

    async def test_cue_uses_current_audio_clock_and_reset_epoch(self):
        serializer = FaceSerializer()
        await serializer.serialize(OutputAudioRawFrame(b'\0' * 960, 24000, 1))
        frame = OutputTransportMessageFrame(message={'type':'performance_face', 'name':'wolf_eyes', 'duration_samples':122805})
        cue = json.loads(await serializer.serialize(frame))
        self.assertEqual((cue['epoch'], cue['offset']), (0, 480))
        await serializer.serialize(InterruptionFrame())
        cue = json.loads(await serializer.serialize(frame))
        self.assertEqual((cue['epoch'], cue['offset']), (1, 0))
        for duration in [-1, True, 480001]:
            with self.assertRaises(ValueError):
                await serializer.serialize(OutputTransportMessageFrame(message={'type':'performance_face', 'name':'wolf_eyes', 'duration_samples':duration}))
