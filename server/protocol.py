"""Small native-client protocol layered on Pipecat's audio transport.

Input: 16 kHz mono signed little-endian PCM, 20–100 ms per binary message.
Output: 8-byte big-endian epoch followed by 24 kHz mono signed LE PCM.
A JSON interrupt message advances epoch and requires immediate playback flush.
"""
import json
import struct
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, InterruptionFrame
from pipecat.serializers.base_serializer import FrameSerializer


class FaceSerializer(FrameSerializer):
    def __init__(self):
        super().__init__()
        self.epoch = 0

    async def serialize(self, frame):
        if isinstance(frame, InterruptionFrame):
            self.epoch += 1
            return json.dumps({'type': 'interrupt', 'epoch': self.epoch})
        if isinstance(frame, OutputAudioRawFrame):
            if frame.sample_rate != 24000 or frame.num_channels != 1:
                raise ValueError('Output format must be mono 24 kHz')
            return struct.pack('!Q', self.epoch) + frame.audio
        return None

    async def deserialize(self, data):
        if isinstance(data, bytes):
            if not data or len(data) % 2 or len(data) > 3200:
                raise ValueError('Invalid PCM packet size')
            return InputAudioRawFrame(data, 16000, 1)
        if len(data) > 256:
            raise ValueError('Control message too large')
        event = json.loads(data)
        if event == {'type': 'interrupt'}:
            return InterruptionFrame()
        raise ValueError('Unsupported control message')
