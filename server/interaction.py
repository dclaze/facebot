"""Event-driven initiation and deterministic visitor silence controls.

Only ephemeral state; no visitor text is stored here. Camera events remain
labeled observations rather than fabricated user dialogue.
"""
import asyncio
import re
import time
from pipecat.frames.frames import (
    StartFrame, EndFrame, CancelFrame, TranscriptionFrame, InterruptionFrame,
    UserStartedSpeakingFrame, UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame,
    BotStartedSpeakingFrame, BotStoppedSpeakingFrame, LLMContextFrame,
)
from pipecat.processors.frame_processor import FrameProcessor

STOP = re.compile(r"^(?:(?:please|boo)[ ,]+)?(?:stop(?: talking| speaking)?|be quiet|quiet|silence|shut up|leave me alone)(?: please)?[.!?]*$", re.I)
RESUME = re.compile(r"^(?:please )?(?:you can talk again|talk again|start talking|continue talking|you can speak now)[.!?]*$", re.I)


class InteractionState:
    def __init__(self, scene, clock=time.monotonic):
        self.scene, self.clock = scene, clock
        self.user_speaking = False
        self.bot_speaking = False
        self.response_pending = False
        self.quiet_until = 0.

    def observe_frame(self, frame):
        if isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame)):
            self.user_speaking = True
            self.scene.encounter.engaged()
        elif isinstance(frame, (UserStoppedSpeakingFrame, VADUserStoppedSpeakingFrame)):
            self.user_speaking = False
            self.quiet_until = self.clock()+1.
        elif isinstance(frame, BotStartedSpeakingFrame):
            self.bot_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self.bot_speaking = False
            self.response_pending = False
            self.quiet_until = self.clock()+1.
        elif isinstance(frame, InterruptionFrame):
            self.response_pending = False


class VisitorControl(FrameProcessor):
    """Before user aggregation, so stop commands do not ask the LLM to comply."""
    def __init__(self, state):
        super().__init__()
        self.state = state

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        self.state.observe_frame(frame)
        if isinstance(frame, TranscriptionFrame):
            self.state.scene.encounter.engaged()
            text = frame.text.strip()
            if STOP.fullmatch(text):
                self.state.scene.encounter.silenced = True
                self.state.response_pending = False
                await self.broadcast_frame(InterruptionFrame)
                return
            if RESUME.fullmatch(text):
                self.state.scene.encounter.silenced = False
            elif self.state.scene.encounter.silenced:
                return
        await self.push_frame(frame, direction)


class ProactiveTurn(FrameProcessor):
    """After user aggregation; shares its context but never invents a user turn."""
    def __init__(self, state, context, vision=None):
        super().__init__()
        self.state, self.context = state, context
        self.vision = vision
        self._ticker = None

    async def tick(self):
        state = self.state
        if state.clock() < state.quiet_until:
            return
        free = not (state.scene.encounter.silenced or state.user_speaking or state.bot_speaking or state.response_pending)
        event = state.scene.space.take_event() if free else None
        event = event or state.scene.encounter.take_event(
            user_speaking=state.user_speaking,
            bot_speaking=state.bot_speaking or state.response_pending)
        if (not event and self.vision and not state.scene.encounter.silenced
                and not state.user_speaking and not state.bot_speaking and not state.response_pending
                and state.scene.received_at is not None and state.clock()-state.scene.received_at < .75
                and state.scene.faces):
            event = self.vision.take_event()
        if event:
            state.response_pending = True
            frame = LLMContextFrame(self.context)
            frame.scene_event = event
            await self.push_frame(frame)

    async def _run(self):
        while True:
            await asyncio.sleep(.1)
            await self.tick()

    async def cleanup(self):
        if self._ticker:
            self._ticker.cancel()
            try:
                await self._ticker
            except asyncio.CancelledError:
                pass
            self._ticker = None
        await super().cleanup()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame):
            if self.state.scene.encounter.silenced:
                return
            self.state.response_pending = True
        await self.push_frame(frame, direction)
        if isinstance(frame, StartFrame) and self._ticker is None:
            self._ticker = self.create_task(self._run())
        elif isinstance(frame, (EndFrame, CancelFrame)):
            if self._ticker:
                await self.cancel_task(self._ticker)
                self._ticker = None
