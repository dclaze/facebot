# Roadmap

The project remains in planning. These milestones describe intended work, not implemented features.

## 0. Agree on the installation

Choose the tablet, client approach, camera/bowl geometry, character, voice criteria, and expected crowd behavior. Keep development and runtime within the budget. Treat the Mac and tablet as existing hardware; electrical and hardware costs are separate from the digital budget.

## 1. Prove responsive local speech

Benchmark local transcription, language generation, speech synthesis, echo cancellation, and interruptions on the actual devices. Compare streaming pipelines with suitable local speech-to-speech options. Do not assume any model's advertised latency transfers to the full installation.

Measure p50/p95 for complete response latency and interruption latency, report failures, and record hardware, versions, background load, and network conditions. Test while audio is playing through the real speaker. Guardrail processing and audio buffering count toward latency.

Proposed boundaries: visible presence to rendered reaction <=200 ms p95; visitor speech onset to audible playback stopping <=250 ms p95; actual visitor utterance end to first meaningful generated audio <=1 s median and <=1.5 s p95. Confirm these targets during planning. Cached speech is measured separately.

## 2. Bring the face to life

Local animation and camera tracking should respond independently of language generation. Add gaze, blinking, expression, speaking motion, name, listening indication, and operator controls. Validate lighting, viewing angle, costume clearance, and smooth animation during concurrent audio/video activity.

## 3. Build the character

Use concise, funny responses, a curated local-lore pack, session boundaries, and family-safe public behavior. Separate fictional haunting stories from documented history. Target jokes at situations and the ghost itself. Avoid identity/appearance-based insults and repeated public scolding.

Prototype output checks and safe fallback lines; measure their latency. The character needs no arbitrary shell, account, or device-control tools. No filter is assumed infallible.

## 4. Test candy-bowl commentary

Detect reaches and withdrawals, then investigate visible piece counting. Measure false positives and missed events across representative lighting, occlusion, candy types, and multiple visitors. Confidence-aware reminders are the proposed baseline; physical enforcement would require different hardware and scope.

## 5. Validate a complete event

Run a 12-hour soak on the physical installation. Test Wi-Fi interruptions, server restarts, playback cancellation, repeated visitors, empty scenes, noisy groups, memory growth, thermal behavior, and operator mute. Record exact versions and honest results. Replays and simulations must be labeled separately from device observations.

## 6. Make it reproducible

Publish setup instructions, example configuration, license/attribution inventory, measured benchmarks, and a synthetic demonstration. Keep private deployment details, credentials, raw visitor media and transcripts out of Git history. Consider upstream contributions for reusable fixes. Discuss pricing after the installation works.
