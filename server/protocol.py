"""Small native-client protocol layered on Pipecat's audio transport.

Input: 16 kHz mono signed little-endian PCM, 20–100 ms per binary message.
Output: 8-byte big-endian epoch followed by 24 kHz mono signed LE PCM.
Output PCM is at most 7680 bytes (160 ms); normal transport pacing is 40 ms.
A JSON interrupt message advances epoch and requires immediate playback flush.
"""
import json
import struct
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, InterruptionFrame, OutputTransportMessageFrame
from pipecat.serializers.base_serializer import FrameSerializer

MAX_OUTPUT_PCM_BYTES = 7680

class FaceSerializer(FrameSerializer):
    def __init__(self, on_scene=None):
        super().__init__()
        self.epoch = 0
        self.output_samples = 0
        self.on_scene = on_scene

    async def serialize(self, frame):
        if isinstance(frame, InterruptionFrame):
            self.epoch += 1
            self.output_samples = 0
            return json.dumps({'type': 'interrupt', 'epoch': self.epoch})
        if isinstance(frame, OutputTransportMessageFrame) and frame.message.get('type') == 'visemes':
            return json.dumps({**frame.message, 'epoch': self.epoch, 'offset': self.output_samples})
        if isinstance(frame, OutputAudioRawFrame):
            if frame.sample_rate != 24000 or frame.num_channels != 1:
                raise ValueError('Output format must be mono 24 kHz')
            if not frame.audio or len(frame.audio) % 2 or len(frame.audio) > MAX_OUTPUT_PCM_BYTES:
                raise ValueError('Invalid output PCM packet size')
            self.output_samples += len(frame.audio)//2
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
        if isinstance(event, dict) and set(event) in ({'type', 'visible_faces', 'age_ms'}, {'type', 'visible_faces', 'age_ms', 'overflow'}) and event['type'] == 'scene':
            if type(event['visible_faces']) is not int or not 0 <= event['visible_faces'] <= 4096:
                raise ValueError('Invalid visible face count')
            if type(event['age_ms']) is not int or not 0 <= event['age_ms'] <= 10000:
                raise ValueError('Invalid observation age')
            if 'overflow' in event and type(event['overflow']) is not bool:
                raise ValueError('Invalid overflow flag')
            if event.get('overflow') and event['visible_faces'] < 32:
                raise ValueError('Overflow requires saturated count')
            normalized = dict(event, visible_faces=min(32, event['visible_faces']),
                              overflow=event.get('overflow', False) or event['visible_faces'] > 32)
            if self.on_scene:
                self.on_scene(normalized)
            return None
        raise ValueError('Unsupported control message')
