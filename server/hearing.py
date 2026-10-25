"""Prepared repair for direct hearing checks, never a generated-latency sample."""
import re
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameProcessor

class HearingRepair(FrameProcessor):
    def __init__(self, name='Boo', mark=None, name_provider=None):
        super().__init__()
        self.mark=mark
        self.name_provider = name_provider
        self.set_name(name)

    def set_name(self, name):
        # Whisper tiny rendered the synthetic configured name Boo as "Bo".
        # This alias is only for this narrow intent, never identity or wake gating.
        names = '(?:boo|bo)' if name.casefold() == 'boo' else re.escape(name.casefold())
        self.pattern=re.compile(r'(?:(?:hey|hi) )?(?:'+names+r' )?(?:(?:can|do) you hear me(?: now)?|are you listening|(?:are )?you there)')

    async def process_frame(self, frame, direction):
        await super().process_frame(frame,direction)
        if self.name_provider:
            self.set_name(self.name_provider())
        if isinstance(frame,LLMContextFrame) and not getattr(frame,'scene_event',None):
            messages=frame.context.get_messages()
            latest=messages[-1] if messages else {}
            text=latest.get('content','')
            if latest.get('role')=='user' and isinstance(text,str):
                normalized=' '.join(re.sub(r'[,!?.]',' ',text.casefold()).split())
                if self.pattern.fullmatch(normalized):
                    if self.mark:self.mark('prepared_reply')
                    # Successful transcription proves receipt of this utterance,
                    # not earlier speech, a specific identity or acoustic quality.
                    await self.push_frame(TTSSpeakFrame('I heard that. Go ahead.'),direction)
                    return
        await self.push_frame(frame,direction)
