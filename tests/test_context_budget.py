import unittest
from unittest.mock import AsyncMock
from server.context_budget import ContextBudget, BudgetedContext
from server.persona import instructions
from server.timing import StageTiming
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection


class BudgetTests(unittest.TestCase):
    def setUp(self): self.budget = ContextBudget()

    def test_final_scene_event_and_rules_are_counted(self):
        messages = [{'role':'system','content':instructions()}]
        messages += [{'role':'user','content':'Tell me about candy. '*80},
                     {'role':'assistant','content':'Old answer. '*60}]*5
        messages += [{'role':'user','content':'My name is Mia, not Maya.'},
                     {'role':'system','content':'SCENE: Two visible faces. Actions unknown.'},
                     {'role':'system','content':'EVENT: an arrival; no costume evidence.'}]
        result, receipt = self.budget.assemble(messages)
        self.assertLessEqual(receipt['budgeted_input_tokens'], 1536)
        self.assertEqual(result[-1]['content'], 'My name is Mia, not Maya.')
        self.assertIn('Actions unknown', str(result))
        self.assertIn('no costume evidence', str(result))
        self.assertEqual(result[0]['content'], instructions())
        self.assertGreater(receipt['removed_messages'], 0)

    def test_no_partial_utterance_or_safety_truncation(self):
        for text in ('Do not give me peanuts. '*500, '你好👻'*1000):
            with self.assertRaises(ValueError):
                self.budget.assemble([{'role':'system','content':instructions()},
                                      {'role':'user','content':text}])

    def test_recent_correction_kept_as_complete_turn(self):
        messages = [{'role':'system','content':instructions()},
                    {'role':'user','content':'My name is Mia, not Maya.'},
                    {'role':'assistant','content':'Mia, got it.'},
                    {'role':'user','content':'What did I just tell you?'}]
        result, _ = self.budget.assemble(messages)
        self.assertEqual(result, messages)


class BudgetRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversized_event_is_quiet(self):
        timing = StageTiming()
        processor = BudgetedContext(ContextBudget(), timing)
        processor.push_frame = AsyncMock()
        frame = LLMContextFrame(LLMContext([{'role':'system','content':'Event '*3000}]))
        frame.scene_event = {'kind':'arrival'}
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)
        processor.push_frame.assert_not_called()
        self.assertEqual(timing.report()['context_budget_samples'], [{'event_skipped':True}])

    async def test_oversized_turn_gets_prepared_clarification_not_partial_llm(self):
        timing = StageTiming()
        timing.mark('vad_start')
        processor = BudgetedContext(ContextBudget(), timing)
        processor.push_frame = AsyncMock()
        context = LLMContext([{'role':'user','content':'Do not do that. '*2000}])
        await processor.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM)
        self.assertIsInstance(processor.push_frame.call_args.args[0], TTSSpeakFrame)
        self.assertTrue(timing.prepared)
        self.assertEqual(timing.report()['context_budget_samples'], [{'clarification':True}])
