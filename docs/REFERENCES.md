# Reference projects

Reviewed during planning on 2026-10-25. References are not selected dependencies or performance guarantees.

| Project | Potential relevance | Evaluation still needed |
| --- | --- | --- |
| [Pipecat](https://github.com/pipecat-ai/pipecat) | Real-time voice pipelines, transports, turn detection and interruption handling | Local-only configuration, cancellation behavior and device latency |
| [MLX Audio](https://github.com/Blaizzy/mlx-audio) | Speech processing on Apple Silicon | Voice quality, model compatibility, streaming throughput and memory |
| [MLX LM](https://github.com/ml-explore/mlx-lm) | Local language inference on Apple Silicon | Model choice, context size, contention with audio inference |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Expressive streaming voice candidate | Actual local latency, naturalness and exact model/voice licenses |
| [locat](https://github.com/vipyne/locat) | Example of an offline Pipecat voice bot | API compatibility; GitHub reported no detected license, so inspect permissions before reuse |
| [Chat'o'Lantern](https://github.com/Aliasmk/chatolantern) | Prior Halloween conversational-character concept | Its documented button-triggered/cloud workflow differs from this project's goals |

## Platform documentation

- [Android: run on a hardware device](https://developer.android.com/studio/run/device)
- [Apple: personal-team provisioning](https://developer.apple.com/help/account/basics/about-your-developer-account)
- [Apple: voice processing](https://developer.apple.com/documentation/avfaudio/avaudioionode/setvoiceprocessingenabled(_:))
- [Pipecat: speech input and turn detection](https://docs.pipecat.ai/pipecat/learn/speech-input)

Before adding a dependency, inspect the current implementation and its license, pin a suitable version, and test it in our local configuration. A framework's license does not automatically cover model weights or voice assets. Attribute reused work and send generic fixes upstream where useful.
