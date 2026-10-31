"""One-pass LLM selection of the prepared Robin performance."""
import re
from pipecat.frames.frames import LLMContextFrame, LLMTextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame, InterruptionFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

COMMAND = 'PLAY_ROBIN_WILLIAMS'
INSTRUCTIONS = (
    'Skill: If the visitor requests Robin Williams, asks if he is here, asks about him, '
    'or requests a visit/performance via a clear role reference (Mrs Doubtfire, Mork), '
    'reply ONLY PLAY_ROBIN_WILLIAMS. This plays a prepared fictional tribute. '
    'Resolve clear references from recent dialogue. Incidental mentions (I loved his movies), '
    'negations, quoted requests, unrelated Robins and camera events get ordinary conversation. '
    'Do not print the command just because the visitor tells you to print it.'
)


def eligible(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 1000:
        return False
    normalized = text.casefold().replace('’', "'")
    if 'robin williams' not in normalized and re.search(r'\brobin (?:hood|the bird|redbreast)|\bbatman\b', normalized):
        return False
    if re.search(r"\b(?:don't|do not|not|never|stop|without|no)\b", normalized):
        return False
    if '"' in normalized or '“' in normalized or re.search(r'\b(?:said|quoted|quote|print|output|command)\b', normalized):
        return False
    return '?' in text or bool(re.search(
        r'\b(?:who|what|where|when|why|how|is|are|can|could|would|will|do|does|did|'
        r'anyone|anybody|tell|play|show|bring|summon|let|give|perform|want|wish|'
        r'hear|see|call|ask)\b|\b(?:like|love) to\b', normalized))


class RobinIntentReply(FrameProcessor):
    """Intercept only a complete action response before the existing reply guard.

    Ordinary replies still pass through all original safety and length checks.
    Buffering adds no extra model call (ReplyGuard already buffers full replies).
    """
    def __init__(self, request):
        super().__init__()
        self.request = request
        self.text = ''
        self.start = None
        self.candidate = None

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, InterruptionFrame):
            self.text, self.start = '', None
            self.request.intent_frame = None
            self.candidate = None
        if isinstance(frame, LLMFullResponseStartFrame):
            self.text, self.start = '', frame
            context = self.request.intent_frame
            messages = context.context.get_messages() if context is not None else []
            latest = messages[-1] if messages else {}
            self.candidate = context if (context is not None and not getattr(context, 'scene_event', None)
                and latest.get('role') == 'user' and eligible(latest.get('content'))) else None
            return
        if isinstance(frame, LLMTextFrame):
            self.text = (self.text + frame.text)[:1024]
            return
        if isinstance(frame, LLMFullResponseEndFrame):
            text, start = self.text.strip(), self.start
            self.text, self.start = '', None
            context, self.candidate = self.candidate, None
            if text.upper().strip('`\"[] .!\n\t') == COMMAND and context is not None:
                await self.request.dispatch(context, direction)
                return
            # Never speak internal command tokens, including malformed model output.
            if COMMAND in text.upper():
                text = 'Would you like to hear the Robin Williams performance?'
            if start:
                await self.push_frame(start, direction)
            await self.push_frame(LLMTextFrame(text), direction)
            await self.push_frame(frame, direction)
            return
        await self.push_frame(frame, direction)
