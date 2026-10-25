# Final prompt budget

Run `.venv/bin/python scripts/setup-tokenizer.py` once during setup. This downloads
only official Qwen2.5 tokenizer files at pinned revision
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, into ignored local storage.
The current budget supports the deployed `qwen2.5:1.5b`; switching models requires
verifying that model's tokenizer and template first.

`BudgetedContext` runs after all persona, scene, vision and event insertion and
before the LLM. Target is at most1000 input tokens; hard budget1536. Counts include
chat markers, assistant prefix and a32-token margin. It takes the larger of merged
and separate system-message renderings; diagnostics label this conservative count
`budgeted_input_tokens`, not the provider's measured token usage.

Core rules, fresh scene/event constraints and the complete current utterance stay.
Recent complete turns are admitted newest first. Optional owner coaching and local
facts fit only within the target. No synchronous summarizer, sentence slicing or
negation truncation is used. If mandatory content cannot fit, a spoken turn receives
a prepared request for one question; an oversized proactive event is skipped.
Prepared clarifications are excluded from generated-latency measurements.

Authenticated diagnostics retain numeric budget receipts only, not prompt text.
One synthetic check counted410 budgeted tokens versus373 reported by Ollama;
this checks a representative template margin, not every possible input.

This input bound does not configure the model's allocated KV cache. Ollama's
OpenAI-compatible endpoint requires a model with `PARAMETER num_ctx 2048` to set
that separately; this runtime allocation change is still pending verification.
See [official compatibility guidance](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx).
There is no measured latency improvement from this change yet.
