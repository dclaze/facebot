"""Conservative output checks. These reduce risk, not a safety guarantee."""
import re
from server.spoken_text import spoken_text
from server.reactions import parse_reply
from pipecat.frames.frames import LLMFullResponseStartFrame, LLMFullResponseEndFrame, LLMTextFrame, InterruptionFrame, OutputTransportMessageFrame
from pipecat.processors.frame_processor import FrameProcessor

FALLBACK = "I'll keep that one to myself."
LENGTH_FALLBACK = "That needs a shorter answer. Ask me one part at a time."
# Explicit family-event exclusions. Adversarial validation remains required.
UNSUITABLE = re.compile(r'\b(fuck\w*|shit\w*|bitch\w*|sex\w*|porn\w*|suicid\w*|kill\w*|murder\w*|stupid|idiot|ugly|fat|gun\w*|bomb\w*)\b', re.I)
PRIVATE = re.compile(r'https?://|www\.|@|\d{3}[- .]?\d{3}[- .]?\d{4}', re.I)

def checked_reply(text):
    text = spoken_text(text)
    if not text or UNSUITABLE.search(text) or PRIVATE.search(text):
        return FALLBACK
    if len(text) > 240 or len(text.split()) > 32:
        return LENGTH_FALLBACK
    return text

class ReplyGuard(FrameProcessor):
    def __init__(self, is_silenced=lambda: False):
        super().__init__()
        self.text = ''
        self.is_silenced = is_silenced
    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, (LLMFullResponseStartFrame, InterruptionFrame)):
            self.text = ''
        if isinstance(frame, LLMTextFrame):
            # Bound collection even if a provider ignores its output token limit.
            self.text = (self.text + frame.text)[:1024]
            return
        if isinstance(frame, LLMFullResponseEndFrame):
            if not self.is_silenced():
                safe = checked_reply(self.text)
                if self.text.lstrip().startswith('{') and safe != FALLBACK:
                    try:
                        _, expression = parse_reply(self.text)
                        await self.push_frame(OutputTransportMessageFrame(message=expression), direction)
                    except (ValueError, TypeError, KeyError):
                        safe = FALLBACK
                await self.push_frame(LLMTextFrame(safe), direction)
            self.text = ''
        await self.push_frame(frame, direction)
