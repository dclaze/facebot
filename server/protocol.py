"""Small native-client protocol layered on Pipecat's audio transport.

Input: 16 kHz mono signed little-endian PCM, 20–100 ms per binary message.
Output: 8-byte big-endian epoch followed by 24 kHz mono signed LE PCM.
Output PCM is at most 7680 bytes (160 ms); normal transport pacing is 40 ms.
A JSON interrupt message advances epoch and requires immediate playback flush.
"""
import json
import struct
from server.captions import validate_captions
from server.reactions import validate_expression
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, InterruptionFrame, OutputTransportMessageFrame
from pipecat.serializers.base_serializer import FrameSerializer

MAX_OUTPUT_PCM_BYTES = 7680

class FaceSerializer(FrameSerializer):
    def __init__(self, on_scene=None, recorder=None, probes=None):
        super().__init__()
        self.epoch = 0
        self.output_samples = 0
        self.on_scene = on_scene
        self.recorder = recorder
        self.probes = probes

    async def serialize(self, frame):
        if isinstance(frame, InterruptionFrame):
            if self.probes:
                self.probes.cancel()
            self.epoch += 1
            self.output_samples = 0
            return json.dumps({'type': 'interrupt', 'epoch': self.epoch})
        if isinstance(frame, OutputTransportMessageFrame) and frame.message.get('type') == 'playback_probe':
            import uuid
            identifier = frame.message.get('id')
            if not isinstance(identifier, str) or str(uuid.UUID(identifier)) != identifier:
                raise ValueError('Invalid playback probe')
            if self.probes:
                self.probes.sent(identifier, self.epoch, self.output_samples)
            return json.dumps({'type': 'playback_probe', 'id': identifier,
                               'epoch': self.epoch, 'offset': self.output_samples})
        if isinstance(frame, OutputTransportMessageFrame) and frame.message.get('type') == 'visemes':
            if 'captions' in frame.message:
                validate_captions(frame.message['captions'])
            return json.dumps({**frame.message, 'epoch': self.epoch, 'offset': self.output_samples})
        if isinstance(frame, OutputTransportMessageFrame) and frame.message.get('type') == 'performance_video':
            message = frame.message
            import re
            start, duration = message.get('start_after_samples'), message.get('duration_ms')
            if (message.get('id') != 'robin-williams' or not isinstance(message.get('path'), str)
                    or not re.fullmatch(r'/media/robin-williams/[0-9a-f]{64}\.mp4', message['path'])
                    or type(start) is not int or not 0 <= start <= 24000*120
                    or type(duration) is not int or not 1 <= duration <= 180000):
                raise ValueError('Invalid performance video')
            return json.dumps({'type':'performance_video','id':message['id'],'path':message['path'],
                               'duration_ms':duration,'epoch':self.epoch,'offset':self.output_samples+start})
        if isinstance(frame, OutputTransportMessageFrame) and frame.message.get('type') == 'performance_face':
            duration = frame.message.get('duration_samples')
            if (frame.message.get('name') != 'wolf_eyes' or type(duration) is not int
                    or not 1 <= duration <= 24000 * 20):
                raise ValueError('Invalid performance face cue')
            return json.dumps({'type': 'performance_face', 'name': 'wolf_eyes',
                               'duration_samples': duration, 'epoch': self.epoch,
                               'offset': self.output_samples})
        if isinstance(frame, OutputTransportMessageFrame) and frame.message.get('type') == 'expression':
            if not validate_expression(frame.message):
                raise ValueError('Invalid facial reaction')
            return json.dumps({**frame.message, 'epoch': self.epoch})
        if isinstance(frame, OutputAudioRawFrame):
            if frame.sample_rate != 24000 or frame.num_channels != 1:
                raise ValueError('Output format must be mono 24 kHz')
            if not frame.audio or len(frame.audio) % 2 or len(frame.audio) > MAX_OUTPUT_PCM_BYTES:
                raise ValueError('Invalid output PCM packet size')
            self.output_samples += len(frame.audio)//2
            if self.recorder:
                self.recorder.output_audio(len(frame.audio))
            return struct.pack('!Q', self.epoch) + frame.audio
        return None

    async def deserialize(self, data):
        if isinstance(data, bytes):
            if not data or len(data) % 2 or len(data) > 3200:
                raise ValueError('Invalid PCM packet size')
            if self.recorder:
                self.recorder.mic_audio(data)
            return InputAudioRawFrame(data, 16000, 1)
        if len(data) > 256:
            raise ValueError('Control message too large')
        event = json.loads(data)
        if isinstance(event, dict) and event.get('type') == 'playback_receipt':
            import uuid
            if (set(event) != {'type', 'id', 'epoch', 'sample'} or not isinstance(event['id'], str)
                    or str(uuid.UUID(event['id'])) != event['id']
                    or type(event['epoch']) is not int or not 0 <= event['epoch'] <= 2**53
                    or type(event['sample']) is not int or not 0 <= event['sample'] <= 2**53):
                raise ValueError('Invalid playback receipt')
            if self.probes:
                self.probes.receive(event)
            return None
        if event == {'type': 'interrupt'}:
            return InterruptionFrame()
        if (isinstance(event, dict) and {'type', 'visible_faces', 'age_ms'} <= set(event)
                and set(event) <= {'type', 'visible_faces', 'age_ms', 'overflow', 'face_fill'} and event['type'] == 'scene'):
            if type(event['visible_faces']) is not int or not 0 <= event['visible_faces'] <= 4096:
                raise ValueError('Invalid visible face count')
            if type(event['age_ms']) is not int or not 0 <= event['age_ms'] <= 10000:
                raise ValueError('Invalid observation age')
            if 'overflow' in event and type(event['overflow']) is not bool:
                raise ValueError('Invalid overflow flag')
            if 'face_fill' in event and (type(event['face_fill']) is not int or not 0 <= event['face_fill'] <= 1000):
                raise ValueError('Invalid face occupancy')
            if event.get('overflow') and event['visible_faces'] < 32:
                raise ValueError('Overflow requires saturated count')
            normalized = dict(event, visible_faces=min(32, event['visible_faces']),
                              overflow=event.get('overflow', False) or event['visible_faces'] > 32)
            if self.on_scene:
                self.on_scene(normalized)
            return None
        raise ValueError('Unsupported control message')
