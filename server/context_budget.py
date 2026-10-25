"""Final text-only Qwen input assembly, after scene/event insertion."""
from pathlib import Path
from tokenizers import Tokenizer
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameProcessor

TOKENIZER = Path(__file__).resolve().parents[1] / '.local/tokenizers/qwen2.5-1.5b/tokenizer.json'
CLARIFY = 'Give me one question at a time so I can follow you.'


class ContextBudget:
    def __init__(self, path=TOKENIZER, target=1000, hard=1536):
        self.encoder = Tokenizer.from_file(str(path))
        self.target, self.hard = target, hard

    def count(self, messages):
        # Ollama collates system messages. Also count their unmerged form and
        # reserve 32 tokens, so minor wrapper differences cannot exhaust KV.
        def render(items):
            return ''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n'
                           for m in items)+'<|im_start|>assistant\n'
        systems = [m['content'] for m in messages if m['role'] == 'system']
        merged = ([{'role':'system','content':'\n\n'.join(systems)}] if systems else [])
        merged += [m for m in messages if m['role'] != 'system']
        return max(len(self.encoder.encode(render(items), add_special_tokens=False).ids)
                   for items in (messages, merged)) + 32

    def assemble(self, messages):
        if any(not isinstance(m.get('content'), str) for m in messages):
            raise ValueError('Only bounded text context is supported')
        systems = [m for m in messages if m['role'] == 'system']
        optional = [m for m in systems if m['content'].startswith(('Owner style coaching,', 'Reference facts ('))]
        required = [m for m in systems if m not in optional]
        dialogue = [m for m in messages if m['role'] in ('user', 'assistant')]
        # Never slice the current utterance: a removed negation changes intent.
        latest = [dialogue[-1]] if dialogue and dialogue[-1]['role'] == 'user' else []
        chosen = required + latest
        if self.count(chosen) > self.hard:
            raise ValueError('Current utterance and required rules exceed input budget')
        history = dialogue[:-1] if latest else dialogue
        # Whole, contiguous recent turns only; no orphaned assistant reply.
        for start in reversed([i for i,m in enumerate(history) if m['role'] == 'user']):
            candidate = required + history[start:] + latest
            if self.count(candidate) > self.target: break
            chosen = candidate
        for item in optional:
            candidate = [*chosen[:len(required)], item, *chosen[len(required):]]
            if self.count(candidate) <= self.target: chosen = candidate
        return chosen, {'budgeted_input_tokens': self.count(chosen),
                        'removed_messages': len(messages)-len(chosen),
                        'target': self.target, 'hard_limit': self.hard}


class BudgetedContext(FrameProcessor):
    def __init__(self, budget, timing):
        super().__init__()
        self.budget, self.timing = budget, timing

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame):
            try:
                messages, receipt = self.budget.assemble(frame.context.get_messages())
            except ValueError:
                if getattr(frame, 'scene_event', None):
                    self.timing.record_context({'event_skipped': True})
                    return
                self.timing.record_context({'clarification': True})
                self.timing.mark('prepared_reply')
                await self.push_frame(TTSSpeakFrame(CLARIFY), direction)
                return
            frame.context.set_messages(messages)
            self.timing.record_context(receipt)
        await self.push_frame(frame, direction)
