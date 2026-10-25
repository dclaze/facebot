# Implementation plan

Implementation authorized 2026-10-25. Product remains undelivered until both physical platforms pass acceptance.

## Architecture decision

Use thin native Android and iOS clients for audio capture/playback, platform echo cancellation, camera attention and kiosk integration. Share the face design and event protocol; native rendering remains an option where it reduces audio/visual latency. A browser-only client complicates secure microphone access and kiosk behavior. Keep animation and visitor attention independent of server generation.

A local Mac service owns one active session and reuses mature speech components: evaluate Pipecat turn handling, MLX Audio transcription/synthesis and existing Ollama generation. No cloud fallback. Benchmark before selecting final models. Each turn has a generation ID; interruption immediately clears client playback and invalidates pending server output. Bound every audio queue. Microphone stays active during playback; acoustic echo rejection must be tested on actual speakers.

Use short family-safe character responses, no tools or runtime web access, and memory limited to the active encounter. Do not persist media or conversation text by default. Candy commentary is optional and confidence-aware, never an assertion about concealed pieces.

## Execution order

1. Add repeatable synthetic local benchmarks and report cold/warm timing separately. Inspect model/dependency licenses. Prepare isolated Android toolchain and build a display shell.
2. Prove local STT → generation → TTS with actual generated audio and cancellation; record component timing separately from physical end-to-end measurements.
3. Connect native clients, continuous voice processing, immediate playback flush, local camera attention, reconnect and operator mute. Add configurable name/voice and animated face.
4. Verify physical Android and iOS installation, audio echo/barge-in, gestures, owner recovery, camera and latency. Android screen pinning is not strong managed lock task. Do not enroll/reset devices. iOS uses owner-configured Guided Access with Touch disabled.
5. Run the required 12-hour actual-device soak and publish sanitized measurement summaries. Never publish private installation context or device identifiers.

## Acceptance evidence

Use monotonic clocks and label evidence: host component benchmark, synthetic replay, simulator, or physical observation. Record sample count/failures and p50/p95. Generated reply timing includes endpointing, safety checks, synthesis and actual output; filler is excluded. Existing targets remain in README. Physical-device authorization is a dependency for step 4, not steps 1–3.
