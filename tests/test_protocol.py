import json
import struct
import unittest
from server.protocol import FaceSerializer
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, InterruptionFrame, OutputTransportMessageFrame

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_viseme_offset_tracks_pcm_and_resets_on_interrupt(self):
        codec = FaceSerializer()
        await codec.serialize(OutputAudioRawFrame(bytes(1920),24000,1))
        frame = OutputTransportMessageFrame(message={'type':'visemes','cues':[[0,600,'open']]})
        event = json.loads(await codec.serialize(frame))
        self.assertEqual((event['offset'],event['epoch']),(960,0))
        await codec.serialize(InterruptionFrame())
        event = json.loads(await codec.serialize(frame))
        self.assertEqual((event['offset'],event['epoch']),(0,1))

    async def test_output_packet_boundary(self):
        codec = FaceSerializer()
        self.assertEqual(len(await codec.serialize(OutputAudioRawFrame(bytes(7680), 24000, 1))), 7688)
        for pcm in (b'', b'1', bytes(7682)):
            with self.assertRaises(ValueError):
                await codec.serialize(OutputAudioRawFrame(pcm, 24000, 1))

    async def test_audio_format_and_interrupt_epoch(self):
        codec = FaceSerializer()
        frame = await codec.deserialize(bytes(640))
        self.assertIsInstance(frame, InputAudioRawFrame)
        self.assertEqual(frame.sample_rate, 16000)
        audio = OutputAudioRawFrame(bytes(960), 24000, 1)
        self.assertEqual(struct.unpack('!Q', (await codec.serialize(audio))[:8])[0], 0)
        control = json.loads(await codec.serialize(InterruptionFrame()))
        self.assertEqual(control, {'type':'interrupt','epoch':1})
        self.assertEqual(struct.unpack('!Q', (await codec.serialize(audio))[:8])[0], 1)

    async def test_reject_bad_audio_and_commands(self):
        codec = FaceSerializer()
        for value in [b'', b'1', bytes(3202), '{"type":"shell"}', 'x'*257]:
            with self.assertRaises(ValueError):
                await codec.deserialize(value)

    async def test_client_interrupt(self):
        self.assertIsInstance(await FaceSerializer().deserialize('{"type":"interrupt"}'), InterruptionFrame)
