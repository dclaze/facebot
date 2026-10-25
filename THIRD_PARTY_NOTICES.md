# Third-party components

Facebot source is MIT. Dependencies and downloaded weights retain their own licenses; they are not relicensed or bundled into this repository.

| Component | Pinned/current evaluation | License / provenance |
| --- | --- | --- |
| Pipecat | 1.14.0 | BSD-2-Clause; installed distribution metadata; https://github.com/pipecat-ai/pipecat |
| MLX Audio | 0.6.1 | MIT; installed distribution metadata; https://github.com/Blaizzy/mlx-audio |
| Misaki | 0.9.4 | Apache-2.0; installed distribution metadata; https://github.com/hexgrad/misaki |
| Kokoro | mlx-community/Kokoro-82M-bf16, af_heart evaluation voice | Conversion and original cards declare Apache-2.0: https://huggingface.co/mlx-community/Kokoro-82M-bf16 and https://huggingface.co/hexgrad/Kokoro-82M. Voice quality/choice is not yet accepted. |
| Whisper | mlx-community/whisper-tiny.en-mlx | Conversion card names upstream tiny.en but omits its own license declaration. Upstream Whisper is MIT: https://github.com/openai/whisper. No weights redistributed; conversion provenance/license inventory remains to complete before distribution. |
| Qwen2.5 | Ollama qwen2.5:1.5b | Apache-2.0, https://ollama.com/library/qwen2.5:1.5b |
| Qwen3.5 | Existing Ollama qwen3.5:9b baseline | Exact deployed model digest and license receipt must be retained before release. |

`requirements.lock` records resolved Python dependencies, including their own transitive components. This table is the selected-component inventory, not a completed distribution audit. No code from the unlicensed locat reference was copied.
