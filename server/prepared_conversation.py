"""Small authored answers for event facts the conversation model must not invent."""
import re
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameProcessor
from server.profiles import active

QUANTITY = re.compile(
    r'\b(?:how many|how much|(?:can|could|may) (?:i|we) (?:please )?(?:take|have|get)|'
    r'(?:take|have|get) (?:two|three|four|extra|another|more|\d+)|'
    r'(?:one|two|three|four|extra|another|more|\d+) (?:pieces?|cand(?:y|ies)|treats?))\b', re.I)
CANDY = re.compile(r'\b(?:cand(?:y|ies)|treats?|pieces?|sweets?)\b', re.I)
EXCLUDE = re.compile(r'\b(?:allerg\w*|ingredients?|nuts?|peanuts?|sugar|calories|diabet\w*|safe|eat|bought|buy|brought|bowl|price|cost)\b', re.I)


def candy_quantity_question(text):
    return bool(isinstance(text, str) and len(text) <= 300
                and CANDY.search(text) and QUANTITY.search(text) and not EXCLUDE.search(text))


class PreparedConversation(FrameProcessor):
    def __init__(self, state, mark=None):
        super().__init__()
        self.state, self.mark = state, mark

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if (isinstance(frame, LLMContextFrame) and not getattr(frame, 'scene_event', None)
                and active()['id'] == 'halloween'):
            messages = frame.context.get_messages()
            latest = messages[-1] if messages else {}
            if latest.get('role') == 'user' and candy_quantity_question(latest.get('content')):
                if self.state.scene.encounter.silenced:
                    self.state.response_pending = False
                    return
                if self.mark:
                    self.mark('prepared_reply')
                await self.push_frame(TTSSpeakFrame('One piece per person, please. Save some for the next monster!'), direction)
                return
        await self.push_frame(frame, direction)
