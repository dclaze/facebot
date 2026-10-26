"""Checksum-bound spoken intro followed by an audio-clock-synchronized video."""
import asyncio
import hashlib
import json
from pathlib import Path
import re
from fastapi import Header, HTTPException
from fastapi.responses import FileResponse
import hmac
from pipecat.frames.frames import OutputTransportMessageFrame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from server.robin_skit import RobinSkit, RobinSkitFrame, ROOT

MAX_VIDEO_BYTES = 64 * 1024 * 1024
FULL_ROOT = ROOT.parent / 'robin-williams-performance'


class RobinPerformance(RobinSkit):
    def __init__(self, root=None):
        root = Path(root) if root is not None else (FULL_ROOT if (FULL_ROOT/'manifest.json').exists() else ROOT)
        super().__init__(root)
        self.video = None
        self.video_path = None
        self.source_root = Path(root)
        try:
            manifest = json.loads((self.source_root/'manifest.json').read_text())
            video = manifest.get('video')
            if video is None:
                return
            if not self.pcm:
                raise ValueError('Performance audio unavailable')
            digest = video['sha256']
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Invalid video digest')
            if video['file'] != digest + '.mp4':
                raise ValueError('Invalid video filename')
            path = self.source_root / video['file']
            if not 1 <= path.stat().st_size <= MAX_VIDEO_BYTES:
                raise ValueError('Invalid video size')
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError('Video checksum mismatch')
            start, duration = video['start_samples'], video['duration_ms']
            if (type(start) is not int or start < 0 or type(duration) is not int
                    or not 1 <= duration <= 180000 or start + duration*24 > len(self.pcm)//2 + 2400):
                raise ValueError('Invalid video timing')
            self.video = {'type':'performance_video','id':'robin-williams',
                          'path':'/media/robin-williams/'+video['file'],
                          'start_after_samples':start,'duration_ms':duration}
            self.video_path = path
        except (OSError, ValueError, KeyError, TypeError):
            # A malformed full performance never degrades into a misleading partial show.
            self.pcm, self.video, self.video_path = b'', None, None

    def report(self):
        return {**super().report(), 'routing_version':2, 'full_performance':self.video is not None,
                'video_duration_ms':self.video['duration_ms'] if self.video else None}

    def media_path(self, filename):
        if (not self.video_path or filename != self.video_path.name
                or not self.video_path.is_file()):
            return None
        if hashlib.sha256(self.video_path.read_bytes()).hexdigest() != filename[:-4]:
            return None
        return self.video_path


def add_media_route(app, performance, token):
    @app.get('/media/robin-williams/{filename}')
    async def media(filename: str, authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        path = performance.media_path(filename)
        if path is None:
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type='video/mp4', headers={'Cache-Control':'private, max-age=31536000, immutable'})


def relative_cues(cues, start, end):
    return [[max(a,start)-start,min(b,end)-start,text] for a,b,text in cues if b>start and a<end]


class RobinPerformancePlayback(FrameProcessor):
    def __init__(self, skit, state, mark=None, video_enabled=False):
        super().__init__()
        self.skit, self.state, self.mark, self.video_enabled = skit, state, mark, video_enabled

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if not isinstance(frame,RobinSkitFrame) or direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame,direction)
            return
        if self.state.scene.encounter.silenced or not self.skit.pcm:
            self.state.response_pending=False
            return
        if self.video_enabled and self.skit.video:
            # Queued before the intro audio, allowing the client to preload hidden.
            await self.push_frame(OutputTransportMessageFrame(message=self.skit.video),direction)
        await self.push_frame(TTSStartedFrame(),direction)
        if self.mark:self.mark('tts_start')
        # Native mouth packets have a 30-second limit. Keep each cue packet at
        # 20 seconds; serializer offsets each packet using emitted PCM samples.
        segment_bytes=24000*2*20
        for start in range(0,len(self.skit.pcm),segment_bytes):
            end=min(start+segment_bytes,len(self.skit.pcm))
            await self.push_frame(OutputTransportMessageFrame(message={
                'type':'visemes','cues':relative_cues(self.skit.cues,start//2,end//2),
                'captions':relative_cues(self.skit.captions,start//2,end//2)}),direction)
            for offset in range(start,end,960):
                if self.state.scene.encounter.silenced:
                    await self.push_frame(TTSStoppedFrame(),direction)
                    return
                audio=TTSAudioRawFrame(self.skit.pcm[offset:min(offset+960,end)],24000,1)
                audio.sound_effect=True
                await self.push_frame(audio,direction)
                if offset==0 and self.mark:self.mark('first_pcm')
                await asyncio.sleep(0)
        await self.push_frame(TTSStoppedFrame(),direction)
