# Development setup

Prototype only: native clients currently render the face, while the Mac voice server is a separate integration under test. No physical-device or spoken-latency acceptance has passed.

## Mac speech experiments

Requires Apple Silicon and Python 3.12. Use an isolated environment:

```sh
uv venv --python 3.12 .venv
uv pip sync requirements.lock
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/benchmark_ollama.py
.venv/bin/python scripts/benchmark_speech.py
```

Ollama must already run locally on port 11434 with the requested model. Model downloads are setup-time internet use; inference has no cloud fallback. The current Ollama 0.19.0 host rejected the latest qwen3.5:0.8b manifest; do not upgrade a shared service without assessing its other workloads. Qwen2.5:1.5b is being evaluated as a compatible smaller candidate. Kokoro model/voice assets and Whisper weights download into the local Hugging Face cache on first use; production offline startup must be verified after setup.

`benchmark_speech.py` is synthetic text → generated PCM, not physical spoken latency. The server adds STT, endpointing, checks, transport and buffering, so its timing will differ. Record initial and warm samples separately. The target is in [CONVERSATION_TIMING.md](CONVERSATION_TIMING.md).

The spaCy tokenizer fails a blank-tokenizer serialization roundtrip with preshed 3.0.14 on the observed host. Pinning preshed 3.0.10 fixes that reproduction and trained model loading with spaCy 3.8.16. The English model is installed explicitly to avoid runtime package-manager discovery.

## Voice server prototype

Set a random `FACEBOT_TOKEN` of at least 24 characters in your local environment, then run:

```sh
.venv/bin/python -m server.app
```

Defaults to loopback port 8765. `/health` reports readiness; `/voice` requires an `Authorization: Bearer ...` header and permits one client. LAN binding requires `--cert` and `--key`. Do not commit pairing tokens, certificates, keys or addresses. Configure trusted TLS in clients; never bypass certificate validation. The server disables transcript debug logging, and keeps dialogue in RAM only. Encounter reset and memory limits are still implementation work.

Input audio is raw 16 kHz mono signed 16-bit little-endian PCM, at most 100 ms/message. Output binary messages contain an 8-byte big-endian epoch then 24 kHz mono PCM. `{"type":"interrupt","epoch":N}` flushes client playback and advances the accepted epoch. A client may request interruption with `{"type":"interrupt"}`. Discard old epochs and cap the playback queue; continuous mic input is required while output plays. Acoustic echo cancellation belongs in the native clients and must be proven on speakers.

The prototype uses Pipecat transport/VAD/turn management, local Whisper, Ollama, output checks and a small MLX Audio synthesis adapter. Output checks are incomplete protection; adversarial family-event tests remain required. No arbitrary tools or web access are attached to the character.

## Native display shells

Android: Android SDK 36, JDK 17, Gradle 8.11.1 and Android Gradle Plugin 8.10.1. `scripts/build-android.sh` accepts JAVA_HOME, ANDROID_HOME and GRADLE overrides; default toolchain location is ignored `.local/toolchains/`. Output: `android/app/build/outputs/apk/debug/app-debug.apk`. Install only on an owner-authorized device. Ignoring view touches and immersive flags alone do not prevent system exit.

iOS simulator: Xcode with an arm64 iOS simulator SDK; `scripts/build-ios-simulator.sh`. Output: `build/ios-simulator/Facebot.app`. The shell uses UIKit/AVFoundation-ready native architecture; real-device signing/project integration remains pending. Simulator signing is not physical provisioning. Owner-configured Guided Access with Touch disabled remains the intended kiosk mechanism.
