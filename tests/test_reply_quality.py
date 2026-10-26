import unittest
from unittest.mock import AsyncMock

from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame, LLMTextFrame, LLMFullResponseEndFrame, OutputTransportMessageFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from server.guard import checked_reply, FALLBACK, ReplyGuard
from server.reply_quality import REPAIR
from server.prepared_conversation import PreparedConversation, candy_quantity_question
from server.scene import SceneState
from server.interaction import InteractionState


class ReplyQualityTests(unittest.IsolatedAsyncioTestCase):
    async def test_guard_records_reason_without_retaining_raw_reply(self):
        events = []
        guard = ReplyGuard(record=lambda kind, **fields: events.append((kind, fields)))
        guard.push_frame = AsyncMock()
        await guard.process_frame(LLMTextFrame("Huh, that's"), FrameDirection.DOWNSTREAM)
        await guard.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
        self.assertEqual(events[0][1]['reason'], 'unfinished_reply')
        self.assertNotIn('text', events[0][1])
        self.assertEqual(guard.push_frame.call_args_list[0].args[0].text, REPAIR)

    def test_observed_instruction_leaks_and_fragments_never_reach_speech(self):
        for text in ["Huh, that's", "Got it. Keep it by your bed. I'll be back for",
                     'ONE PIECE OF CANDY PER PERSON is welcome; mention the rule only when relevant, not repeatedly. Back up!',
                     'Sound capabilities: you can play 20 kinds of short real sound effects.']:
            self.assertEqual(checked_reply(text), REPAIR)

    def test_complete_short_answers_and_existing_safety_checks_survive(self):
        for text in ['One each', 'I can.', "That's why.", 'One candy per person, please!',
                     'Ask the host about ingredients before choosing candy.']:
            self.assertEqual(checked_reply(text), text)
        self.assertEqual(checked_reply('You are stupid.'), FALLBACK)

    def test_candy_rule_intent_excludes_health_and_unrelated_questions(self):
        for text in ['Can I take two candies?', 'How many pieces can I have?', 'May we have candy?', 'Can I get another treat?']:
            self.assertTrue(candy_quantity_question(text))
        for text in ['How many calories are in this candy?', 'Can I have candy with my peanut allergy?',
                     'How many treats are in the bowl?', 'I bought two pieces.', 'Can I take a picture?',
                     'How much does candy cost?', 'Tell me a joke.']:
            self.assertFalse(candy_quantity_question(text))

    async def test_prepared_rule_bypasses_model_but_conversation_keeps_working(self):
        state = InteractionState(SceneState())
        processor = PreparedConversation(state)
        processor.push_frame = AsyncMock()
        question = LLMContextFrame(LLMContext([{'role':'user', 'content':'Can I take two candies?'}]))
        await processor.process_frame(question, FrameDirection.DOWNSTREAM)
        reply = processor.push_frame.call_args.args[0]
        self.assertIsInstance(reply, TTSSpeakFrame)
        self.assertEqual(reply.text, 'ONE ONLY, PLEASE!')
        expression = processor.push_frame.call_args_list[0].args[0]
        self.assertIsInstance(expression, OutputTransportMessageFrame)
        self.assertEqual(expression.message, {'type':'expression', 'name':'scared', 'duration_ms':1200})
        processor.push_frame.reset_mock()
        ordinary = LLMContextFrame(LLMContext([{'role':'user', 'content':'How many pieces can I have?'}]))
        await processor.process_frame(ordinary, FrameDirection.DOWNSTREAM)
        processor.push_frame.assert_awaited_once()
        self.assertEqual(processor.push_frame.call_args.args[0].text, 'One piece per person, please.')
        other = LLMContextFrame(LLMContext([{'role':'user', 'content':'Tell me a joke.'}]))
        await processor.process_frame(other, FrameDirection.DOWNSTREAM)
        self.assertIs(processor.push_frame.call_args.args[0], other)
        state.scene.encounter.silenced = True
        processor.push_frame.reset_mock()
        await processor.process_frame(question, FrameDirection.DOWNSTREAM)
        processor.push_frame.assert_not_called()
