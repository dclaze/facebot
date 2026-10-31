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
    BotStartedSpeakingFrame, BotStoppedSpeakingFrame, LLMContextFrame, OutputTransportMessageFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

STOP = re.compile(r"^(?:(?:please|boo)[ ,]+)?(?:stop(?: talking| speaking| laughing| the game| game)?|be quiet|quiet|silence|shut up|leave me alone)(?: please)?[.!?]*$", re.I)
RESUME = re.compile(r"^(?:please )?(?:you can talk again|talk again|start talking|continue talking|you can speak now)[.!?]*$", re.I)


class InteractionState:
    def __init__(self, scene, clock=time.monotonic):
        self.scene, self.clock = scene, clock
        self.control_epoch = 0
        self.user_speaking = False
        self.bot_speaking = False
        self.response_pending = False
        self.quiet_until = 0.
        self.last_activity = float('-inf')

    def observe_frame(self, frame):
        if isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame)):
            self.user_speaking = True
            self.scene.encounter.engaged()
        elif isinstance(frame, (UserStoppedSpeakingFrame, VADUserStoppedSpeakingFrame)):
            self.user_speaking = False
            self.last_activity = self.clock()
            self.quiet_until = self.clock()+1.
        elif isinstance(frame, BotStartedSpeakingFrame):
            self.bot_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self.bot_speaking = False
            self.last_activity = self.clock()
            self.response_pending = False
            self.quiet_until = self.clock()+1.
        elif isinstance(frame, InterruptionFrame):
            self.response_pending = False


class VisitorControl(FrameProcessor):
    """Before user aggregation, so stop commands do not ask the LLM to comply."""
    def __init__(self, state, on_mute=None):
        super().__init__()
        self.state = state
        self.on_mute = on_mute

    async def send_state(self):
        await self.push_frame(OutputTransportMessageFrame(message={
            'type': 'kiosk_state', 'muted': self.state.scene.encounter.silenced}), FrameDirection.DOWNSTREAM)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        self.state.observe_frame(frame)
        if isinstance(frame, StartFrame) and direction == FrameDirection.DOWNSTREAM:
            # Initialize the transport before replaying the persisted state.
            await self.push_frame(frame, direction)
            await self.send_state()
            return
        if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
            self.state.scene.encounter.engaged()
            text = frame.text.strip()
            if STOP.fullmatch(text):
                self.state.control_epoch += 1
                self.state.scene.encounter.silenced = True
                if self.on_mute:
                    self.on_mute(True)
                self.state.response_pending = False
                await self.broadcast_frame(InterruptionFrame)
                await self.send_state()
                return
            if RESUME.fullmatch(text):
                effective = self.on_mute(False) if self.on_mute else False
                self.state.scene.encounter.silenced = effective if type(effective) is bool else False
                await self.send_state()
                if self.state.scene.encounter.silenced:
                    return
            elif self.state.scene.encounter.silenced:
                return
        await self.push_frame(frame, direction)


class ProactiveTurn(FrameProcessor):
    """After user aggregation; shares its context but never invents a user turn."""
    def __init__(self, state, context, vision=None, quips=None):
        super().__init__()
        self.state, self.context = state, context
        self.vision = vision
        self.quips = quips
        self._ticker = None

    async def tick(self):
        state = self.state
        if state.clock() < state.quiet_until:
            return
        free = not (state.scene.encounter.silenced or state.user_speaking or state.bot_speaking or state.response_pending)
        if self.quips:
            # A single director arbitrates all spontaneous speech for this pack.
            # Existing conversation/skill requests continue through the pipeline.
            arrival = state.scene.encounter.take_event(
                user_speaking=state.user_speaking,
                bot_speaking=state.bot_speaking or state.response_pending)
            state.scene.space.take_event()  # Never turn proximity into nagging.
            event = self.quips.take_event(state, self.vision, arrival=bool(arrival))
            if event:
                state.response_pending = True
                frame = LLMContextFrame(self.context)
                frame.scene_event = event
                await self.push_frame(frame)
            return
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
