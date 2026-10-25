import json
import struct
import unittest
from server.protocol import FaceSerializer
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, InterruptionFrame

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
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
