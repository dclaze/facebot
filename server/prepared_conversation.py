"""Small authored answers for event facts the conversation model must not invent."""
import re
import os
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame, OutputTransportMessageFrame, EndFrame, CancelFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from server.profiles import active
from server.kiosk_experiences import KioskDirector
from server.kiosk_playback import KioskCackleFrame

QUANTITY = re.compile(
    r'\b(?:how many|how much|(?:can|could|may) (?:i|we) (?:please )?(?:take|have|get)|'
    r'(?:take|have|get) (?:two|three|four|extra|another|more|\d+)|'
    r'(?:one|two|three|four|extra|another|more|\d+) (?:pieces?|cand(?:y|ies)|treats?))\b', re.I)
CANDY = re.compile(r'\b(?:cand(?:y|ies)|treats?|pieces?|sweets?)\b', re.I)
EXCLUDE = re.compile(r'\b(?:allerg\w*|ingredients?|nuts?|peanuts?|sugar|calories|diabet\w*|safe|eat|bought|buy|brought|bowl|price|cost)\b', re.I)
EXTRA = re.compile(r'\b(?:two|three|four|five|six|seven|eight|nine|ten|extra|another|more|[2-9]\d*|1\d+)\b', re.I)


def candy_quantity_question(text):
    return bool(isinstance(text, str) and len(text) <= 300
                and CANDY.search(text) and QUANTITY.search(text) and not EXCLUDE.search(text))


class PreparedConversation(FrameProcessor):
    def __init__(self, state, mark=None, name_provider=lambda: 'Boo', enabled=lambda pack: True, kiosk_mode=None):
        super().__init__()
        self.state, self.mark = state, mark
        self.director = KioskDirector(state, name_provider, enabled)
        self.kiosk_mode = (os.getenv("FACEBOT_KIOSK_MODE", "0") == "1" if kiosk_mode is None else kiosk_mode)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, (EndFrame, CancelFrame)):
            self.director.reset()
        if (direction == FrameDirection.DOWNSTREAM and isinstance(frame, LLMContextFrame) and not getattr(frame, 'scene_event', None)
                and active()['id'] == 'halloween'):
            messages = frame.context.get_messages()
            latest = messages[-1] if messages else {}
            if latest.get('role') == 'user' and candy_quantity_question(latest.get('content')):
                if self.state.scene.encounter.silenced:
                    self.state.response_pending = False
                    return
                if self.mark:
                    self.mark('prepared_reply')
                extra = EXTRA.search(latest['content'])
                if extra:
                    await self.push_frame(OutputTransportMessageFrame(message={
                        'type': 'expression', 'name': 'scared', 'duration_ms': 1200}), direction)
                text = 'ONE ONLY, PLEASE!' if extra else 'One piece per person, please.'
                await self.push_frame(TTSSpeakFrame(text), direction)
                return
            if latest.get('role') == 'user':
                text = latest.get('content')
                if self.state.scene.encounter.silenced:
                    self.director.reset()
                    self.state.response_pending = False
                    return
                # Empty/non-string aggregation output is not a visitor request.
                if not isinstance(text, str) or not text.strip():
                    self.state.response_pending = False
                    return
                reply = self.director.route(text)
                if reply is None and self.kiosk_mode:
                    reply = self.director.reply('fallback')
                if reply is not None:
                    if self.mark:
                        self.mark('prepared_reply')
                    if reply['category'] == 'cackle':
                        await self.push_frame(KioskCackleFrame(requested_at=self.state.clock(), control_epoch=self.state.control_epoch), direction)
                    elif reply['text']:
                        await self.push_frame(OutputTransportMessageFrame(message={
                            'type': 'expression', 'name': reply['expression'], 'duration_ms': 1800}), direction)
                        await self.push_frame(TTSSpeakFrame(reply['text']), direction)
                    else:
                        self.state.response_pending = False
                    return
        await self.push_frame(frame, direction)
