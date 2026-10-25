# Reference projects

Reviewed during planning on 2026-10-25. References are not selected dependencies or performance guarantees.

| Project | Potential relevance | Evaluation still needed |
| --- | --- | --- |
| [Pipecat](https://github.com/pipecat-ai/pipecat) | Real-time voice pipelines, transports, turn detection and interruption handling | Local-only configuration, cancellation behavior and device latency |
| [MLX Audio](https://github.com/Blaizzy/mlx-audio) | Speech processing on Apple Silicon | Voice quality, model compatibility, streaming throughput and memory |
| [MLX LM](https://github.com/ml-explore/mlx-lm) | Local language inference on Apple Silicon | Model choice, context size, contention with audio inference |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Expressive streaming voice candidate | Actual local latency, naturalness and exact model/voice licenses |
| [Moshi](https://github.com/kyutai-labs/moshi) | Native full-duplex speech and official Mac MLX implementation | Local timing, character control, safe audio release, echo cancellation and long-session reset |
| [PersonaPlex](https://github.com/NVIDIA/personaplex) | Full-duplex speech with role and voice conditioning | Mac feasibility, model access/license, safety checks and sustained local speed |
| [locat](https://github.com/vipyne/locat) | Example of an offline Pipecat voice bot | API compatibility; GitHub reported no detected license, so inspect permissions before reuse |
| [Chat'o'Lantern](https://github.com/Aliasmk/chatolantern) | Prior Halloween conversational-character concept | Its documented button-triggered/cloud workflow differs from this project's goals |

## Platform documentation

- [Apple: Guided Access and disabling touch](https://support.apple.com/en-au/111795)
- [Android: lock task mode](https://developer.android.com/work/dpc/dedicated-devices/lock-task-mode)
- [Android: run on a hardware device](https://developer.android.com/studio/run/device)
- [Apple: personal-team provisioning](https://developer.apple.com/help/account/basics/about-your-developer-account)
- [Apple: voice processing](https://developer.apple.com/documentation/avfaudio/avaudioionode/setvoiceprocessingenabled(_:))
- [Pipecat: speech input and turn detection](https://docs.pipecat.ai/pipecat/learn/speech-input)

Before adding a dependency, inspect the current implementation and its license, pin a suitable version, and test it in our local configuration. A framework's license does not automatically cover model weights or voice assets. Attribute reused work and send generic fixes upstream where useful.

## Speech-to-speech feasibility screen

Reviewed 2026-10-25; no new model installed or benchmarked by this review.

**Moshi:** The upstream project supplies Mac MLX inference and 4-bit checkpoints.
Its reported practical latency near 200 ms is on an L4 GPU, not evidence for this
Mac or our physical end-to-end metric. The MLX guide explicitly says its command
line client lacks echo cancellation and compensation for accumulating lag.
Sources: [project](https://github.com/kyutai-labs/moshi),
[MLX guide](https://github.com/kyutai-labs/moshi/blob/main/moshi_mlx/README.md).

At inspected revision `e6a55d2722a65870ef52a6c9f6ecfc0e90f38362`, both
`moshi_mlx/moshi_mlx/local.py` and `local_web.py` default to 4,000 steps and
allocate generation capacity from that limit. At 12.5 frames/s, that is about
320 seconds, not an overnight session. The
[FAQ](https://github.com/kyutai-labs/moshi/blob/main/FAQ.md) also describes a
finite-context limit and personality/voice customization difficulties; parts
of that FAQ lag newer capabilities, so verify behavior in the pinned code.
MLX code is MIT; the
[Moshika q4 model card](https://huggingface.co/kyutai/moshika-mlx-q4)
declares CC-BY-4.0 and describes limited safeguards. A promising latency
experiment, but not a drop-in solution for the sassy, guarded, twelve-hour ghost.

**PersonaPlex:** NVIDIA's official implementation supports text role prompts and
audio voice conditioning, which better matches character control. Its documented
setup uses PyTorch/GPU serving, requires Hugging Face model-license acceptance,
and describes CPU offload. That does not establish a responsive Apple Silicon
deployment. Code is MIT; inspect model terms separately. No cloud rental or
account change is justified by this reference alone.
Source: [official repository](https://github.com/NVIDIA/personaplex).

**Decision:** Keep the existing native audio integration moving. The software
owner can compare a bounded isolated Moshi benchmark with incremental preparation
in the current pipeline when hardware resources are available. Any candidate
must retain safe character behavior, interruptibility, natural voice, and session
recovery while meeting physical latency. Pre-audio safety checks consume latency;
post-playback filtering cannot retract already spoken words.
