"""Grounded, prepared scene reactions; control data never enters spoken text."""
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame, OutputTransportMessageFrame
from pipecat.processors.frame_processor import FrameProcessor

from server.profiles import active
import time

# Prepared scene remarks bypass the LLM and its conversation history. Keep a
# bounded, process-local cooldown across reconnects and detection flicker.
_LAST_REMARK = {}
REMARK_COOLDOWN_SECONDS = 1800

# Compatibility export; processing reads the pinned deployment profile.
LINES = active()["visual_reactions"]


class VisualReaction(FrameProcessor):
    def __init__(self, state, mark=None, *, clock=time.monotonic, recent=None):
        super().__init__()
        self.state, self.mark = state, mark
        self.clock = clock
        self.recent = _LAST_REMARK if recent is None else recent

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        event = getattr(frame, 'scene_event', None)
        if isinstance(frame, LLMContextFrame) and event and event['kind'] == 'prepared_quip':
            if (self.state.scene.encounter.silenced or self.state.user_speaking
                    or self.state.bot_speaking or self.state.clock() > event['expires_at']):
                self.state.response_pending = False
                return
            if self.mark:
                self.mark('prepared_reply')
            await self.push_frame(OutputTransportMessageFrame(message={
                'type': 'expression', 'name': event['expression'], 'duration_ms': 1800}), direction)
            await self.push_frame(TTSSpeakFrame(event['text']), direction)
            return
        if isinstance(frame, LLMContextFrame) and event and event['kind'] in ('visual_labels', 'stable_visual_arrival', 'too_close', 'space_restored'):
            if self.state.scene.encounter.silenced:
                self.state.response_pending = False
                return
            # Face occupancy is not contact evidence. Owner rejected repeated
            # proximity nagging; consume these events without speech or backlog.
            if event['kind'] in ('too_close', 'space_restored'):
                self.state.response_pending = False
                return
            profile = active()
            lines = profile['visual_reactions']
            now = self.clock()
            for key, when in list(self.recent.items()):
                if now - when >= REMARK_COOLDOWN_SECONDS:
                    del self.recent[key]
            candidates = ([('arrival', profile['arrival'])] if event['kind'] == 'stable_visual_arrival' else
                          [(x, lines[x]) for x in lines if x in event.get('labels', ())])
            chosen = next(((key, value) for key, value in candidates
                           if (profile['id'], key) not in self.recent), None)
            selected = chosen[1] if chosen else None
            if selected:
                if len(self.recent) >= 128:
                    del self.recent[min(self.recent, key=self.recent.get)]
                self.recent[(profile['id'], chosen[0])] = now
                text, expression = selected
                if self.mark: self.mark('prepared_reply')
                await self.push_frame(OutputTransportMessageFrame(message={
                    'type': 'expression', 'name': expression, 'duration_ms': 1800}), direction)
                await self.push_frame(TTSSpeakFrame(text), direction)
            else:
                self.state.response_pending = False
            return
        await self.push_frame(frame, direction)
