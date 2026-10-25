import unittest
from unittest.mock import AsyncMock
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from server.hearing import HearingRepair

class HearingTests(unittest.IsolatedAsyncioTestCase):
    async def test_presence_check_needs_no_special_wake_word(self):
        p=HearingRepair(); p.push_frame=AsyncMock()
        for text in ('Hey Boo you there?', 'Hey, Bo, you there?', 'Are you there?', 'Do you hear me?'):
            f=LLMContextFrame(LLMContext([{'role':'user','content':text}]))
            await p.process_frame(f,FrameDirection.DOWNSTREAM)
            self.assertIsInstance(p.push_frame.call_args.args[0], TTSSpeakFrame)

    async def test_direct_hearing_question_bypasses_llm_with_labeled_reply(self):
        marks=[]
        p=HearingRepair('Boo',mark=marks.append)
        p.push_frame=AsyncMock()
        f=LLMContextFrame(LLMContext([{'role':'user','content':'Hey, Bo, do you hear me?'}]))
        await p.process_frame(f,FrameDirection.DOWNSTREAM)
        reply=p.push_frame.call_args.args[0]
        self.assertIsInstance(reply,TTSSpeakFrame)
        self.assertEqual(reply.text,'I heard that. Go ahead.')
        self.assertEqual(marks,['prepared_reply'])

    async def test_quoted_question_other_intent_and_event_are_not_repair(self):
        p=HearingRepair('Casper'); p.push_frame=AsyncMock()
        for text in ('My daughter asked do you hear me?', 'Do you hear me or see me?', 'Tell me a joke', 'Hey Boo do you hear me?'):
            frame=LLMContextFrame(LLMContext([{'role':'user','content':text}]))
            await p.process_frame(frame,FrameDirection.DOWNSTREAM)
            self.assertIs(p.push_frame.call_args.args[0],frame)
        frame=LLMContextFrame(LLMContext([{'role':'user','content':'Do you hear me?'}]));frame.scene_event={ 'kind':'stable_visual_arrival' }
        await p.process_frame(frame,FrameDirection.DOWNSTREAM)
        self.assertIs(p.push_frame.call_args.args[0],frame)

    async def test_name_changes_without_reconnecting(self):
        name=['Boo']
        p=HearingRepair(name_provider=lambda:name[0]);p.push_frame=AsyncMock()
        name[0]='Casper'
        frame=LLMContextFrame(LLMContext([{'role':'user','content':'Hey Casper do you hear me?'}]))
        await p.process_frame(frame,FrameDirection.DOWNSTREAM)
        self.assertIsInstance(p.push_frame.call_args.args[0],TTSSpeakFrame)
        frame=LLMContextFrame(LLMContext([{'role':'user','content':'Hey Boo do you hear me?'}]))
        await p.process_frame(frame,FrameDirection.DOWNSTREAM)
        self.assertIs(p.push_frame.call_args.args[0],frame)
