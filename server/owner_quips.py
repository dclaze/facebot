"""Immediate owner-authored speech, never fabricated visitor dialogue."""
import time
from dataclasses import dataclass
from uuid import UUID
from pipecat.frames.frames import DataFrame, TTSSpeakFrame, OutputTransportMessageFrame
from pipecat.processors.frame_processor import FrameProcessor
from server.guard import checked_reply, FALLBACK, LENGTH_FALLBACK
from server.spoken_text import spoken_text
from server.reactions import EXPRESSIONS


def validate_quip(value):
    if not isinstance(value, dict) or set(value) != {'id', 'text', 'expression', 'interrupt'}:
        raise ValueError('Expected id, text, expression and interrupt')
    if not isinstance(value['id'], str) or str(UUID(value['id'])) != value['id']:
        raise ValueError('Invalid command id')
    text = value['text']
    if (not isinstance(text, str) or not text.strip() or len(text) > 240
            or len(text.split()) > 32 or text != spoken_text(text)
            or '[' in text or ']' in text or checked_reply(text) in (FALLBACK, LENGTH_FALLBACK)):
        raise ValueError('Use 1–32 plain, child-safe spoken words, up to 240 characters; no stage tags')
    if value['expression'] not in EXPRESSIONS or type(value['interrupt']) is not bool:
        raise ValueError('Invalid delivery or interruption option')
    return dict(value)


@dataclass
class OwnerQuipFrame(DataFrame):
    command: dict
    created: float


class OwnerQuips(FrameProcessor):
    def __init__(self, state, mark=None, clock=time.monotonic):
        super().__init__()
        self.state, self.mark, self.clock = state, mark, clock
        self.latest = None
        self.receipts = {}

    async def submit(self, value):
        command = validate_quip(value)
        identifier = command['id']
        if identifier in self.receipts:
            return self.receipts[identifier]
        if self.state.scene.encounter.silenced:
            raise RuntimeError('The ghost is muted; quip was not queued')
        if self.state.user_speaking:
            raise RuntimeError('A visitor is speaking; quip was not queued')
        if not command['interrupt'] and (self.state.bot_speaking or self.state.response_pending):
            raise RuntimeError('The ghost is busy; quip was not queued')
        if len(self.receipts) >= 64:
            del self.receipts[next(iter(self.receipts))]
        self.latest = identifier
        receipt = {'id': identifier, 'status': 'accepted',
                   'evidence': 'owner command accepted; playback not yet confirmed'}
        self.receipts[identifier] = receipt
        if command['interrupt']:
            # Supported Pipecat control path cancels generation and flushes native
            # audio epochs. Never inject invented user text to provoke a reply.
            await self.broadcast_interruption()
        self.state.response_pending = True
        await self.queue_frame(OwnerQuipFrame(command, self.clock()))
        return receipt

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, OwnerQuipFrame):
            command = frame.command
            receipt = self.receipts[command['id']]
            if (command['id'] != self.latest or self.clock()-frame.created > 3
                    or self.state.scene.encounter.silenced or self.state.user_speaking):
                receipt['status'] = 'discarded'
                if command['id'] == self.latest:
                    self.state.response_pending = False
                return
            if self.mark:
                self.mark('prepared_reply')
            self.state.response_pending = True
            await self.push_frame(OutputTransportMessageFrame(message={
                'type':'expression','name':command['expression'],'duration_ms':1800}), direction)
            await self.push_frame(TTSSpeakFrame(command['text']), direction)
            receipt.update(status='dispatched', evidence='sent to local TTS; acoustic playback not confirmed')
            return
        await self.push_frame(frame, direction)


def add_routes(app, token, current):
    import hmac
    from fastapi import Request, Header, HTTPException

    @app.post('/owner/quips')
    async def send_quip(request: Request, authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(403)
        if len(await request.body()) > 2048:
            raise HTTPException(413)
        processor = current()
        if processor is None:
            raise HTTPException(409, 'No connected face; nothing was queued')
        try:
            return await processor.submit(await request.json())
        except (ValueError, TypeError, KeyError):
            raise HTTPException(400, 'Invalid quip: use plain child-safe text and a valid delivery')
        except RuntimeError as error:
            raise HTTPException(409, str(error))

    @app.get('/owner/quips/{identifier}')
    async def quip_status(identifier: str, authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(403)
        processor = current()
        if processor is None or identifier not in processor.receipts:
            raise HTTPException(404, 'Command not found in this connection')
        return processor.receipts[identifier]
