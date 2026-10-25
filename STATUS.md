# Facebot status

Updated: 2026-10-25 (America/Los_Angeles)

## Current milestone

Repository-foundation milestone **delivered**: public repository at https://github.com/dclaze/facebot, with initial commit `961389e`. Device reconnaissance has begun; product is **not delivered**. Implementation started: Android display shell builds successfully; iOS simulator shell compiles. Voice, camera, kiosk and physical validation remain incomplete.

## Agreed direction

- Open-source Halloween face with a highly sassy, funny character.
- Tablet on a stand, optionally dressed in a costume. Both Android and iOS are now required; the owner plans to connect both physical devices.
- Local Mac inference, realistic speech, camera-based attention, continuous listening and interruption support.
- Responsiveness is critical; proposed targets are in README.md and docs/ROADMAP.md.
- Optional candy monitoring to encourage one piece each, with accuracy to be established.
- Noon-to-midnight operating window; $20 digital budget, with a design goal of no recurring inference charges.
- Finish planning, get the physical installation working, then discuss pricing.
- Full-screen character presentation with no visible app/browser controls, ignored visitor touches, and owner-only exit is required.
- Reuse suitable existing projects. Carry implementation through working versions on both physical platforms after remaining requirements are aligned.

## Completed

- Initial requirements and candidate approaches recorded.
- Public README, roadmap, references, contribution guidance and MIT license prepared.
- Private installation context preserved outside tracked files in ignored .local/.
- Public repository created and initial documentation pushed to main.
- USB registry identifies the attached Android device as Lenovo Tab P11. ADB lists no devices; wireless-debug discovery also lists none. USB hardware detection succeeded via ioreg after system_profiler returned no USB entries.
- Host has Xcode 26.6 and Android SDK platform 36 / build tools 35.0.0 and 36.0.0. Java runtime is not installed/detected; build setup can proceed independently.
- Existing local Ollama service exposes qwen3.5:9b. Reuse is a candidate, not a measured speech-latency result; do not disrupt unrelated running workloads.

## Open decisions

1. Android tablet identified from the owner's rear-label photo as Lenovo Tab P11 TB-J606F; installed OS, second device, and camera view of visitors/candy bowl remain unverified.
2. Implement the required immersive/touch-locked experience. Proposed approach: shared face interface with thin native clients and platform kiosk controls; exact stack pending device inspection. Browser-only deployment is no longer the preferred baseline.
3. Voice, character name, and calibrated sass level.
4. Candy-reminder acceptance criteria; exact hidden-piece counting is not assumed feasible.
5. Final latency thresholds and full-duplex behavior beyond interruption handling.

## Immediate next step

Connect native Android/iOS continuous audio capture and bounded playback to the local speech prototype, with platform echo cancellation and interruption flush. Add local camera attention. In parallel, pursue incremental/predictive speech to meet the binding 200 ms median / 500 ms p95 target (docs/CONVERSATION_TIMING.md). One active ghost. Both physical devices and 12-hour soaks remain required; product is not delivered.

## Device access dependency

Physical Android install/audio/camera verification requires an authorized ADB connection. Evidence: USB registry sees Lenovo Tab P11, ADB device list is empty, wireless-debug discovery is empty. Owner action: enable USB debugging and accept the connected Mac's authorization prompt on the tablet. Resume trigger: the device appears in ADB as `device`. This blocks physical-device verification, not independent build/server work. iOS physical-device verification also awaits an attached authorized device. Do not reset or enroll either device as a workaround.

Face-holder direction has advanced to a minimal two-piece contoured bezel cover. See the enclosure CAD milestone below and `hardware/README.md`; earlier bulky-head concept is superseded.

## Foundation verification (historical)

At the documentation-only milestone, no runtime tests or latency claims existed. Seven-file publication allowlist, staged private-data scan, relative-link checks, private-file exclusion and git diff whitespace checks passed before the first push. No private planning notes were committed. Remote creation and first push succeeded. Public visibility, MIT license, main branch and remote/local commit equality verified at commit 57d9421. Subsequent documentation updates require the same push verification.

## Implementation checkpoint — 2026-10-25 21:04 UTC

- Native display-only shells added in `android/` and `ios/`; no audio/camera or strong kiosk claims. Android `assembleDebug` passed (31 tasks); iOS arm64 simulator binary compiled and ad-hoc signed. Simulator installation result still to be checked after session move.
- Isolated Temurin 17.0.21+9 and Gradle 8.11.1 archives checksum-verified under ignored `.local/toolchains/`. Python 3.12 environment has MLX Audio 0.6.1, Pipecat 1.14.0 and Misaki 0.9.4; dependency locking and speech validation next.
- Synthetic host-only Qwen3.5:9b benchmark: 5 warm samples, zero failures; first-token p50/p95 891/1068 ms, first-sentence 1875/1915 ms. These exclude STT, endpointing, TTS and speaker output and do NOT meet or prove spoken latency targets. Three benchmark parsing tests passed.
- Highest priority: measure generated PCM, then evaluate a smaller local Qwen configuration. Physical spoken latency still requires authorized devices. Owner is handling Lenovo USB-debug/RSA authorization; do not bypass.
- Compact implementation plan: `docs/IMPLEMENTATION.md`. Preserve unrelated face-holder/hardware working files.
- Session confirmed GPT-6 Astra Medium. Latest inspected quota at 20:57 UTC: 83% remaining; historical reading only.

## Implementation checkpoint — 2026-10-25 14:00 PDT

- Primary implementation continues in the new fork; prior implementation session is superseded. Design and execution order: docs/IMPLEMENTATION.md.
- Android display shell assembled successfully using Temurin 17.0.21 and Gradle 8.11.1 (download checksums verified); APK is local under android/app/build/outputs/apk/debug/. No physical install yet.
- iOS display shell compiled and signed for the simulator; Mach-O reports IOSSIMULATOR, minimum iOS 17. Simulator boot/install verification was in progress at handoff. This is not physical-device evidence.
- Synthetic host-only Qwen3.5:9b baseline: five warm samples, zero failures; first text token p50/p95 891/1068 ms; first sentence 1875/1915 ms. These are not generated audio latency. Three benchmark validation tests passed. Raw results remain ignored in .local/.
- Local speech dependency setup was still running at handoff; inspect completion before restarting. Next: finish simulator launch, pin/review speech dependencies, benchmark synthesis and transcription, then integrate continuous audio and cancellation.
- Android and iOS physical authorization dependencies above remain unchanged. Native shells do not yet satisfy kiosk exit prevention, speech, camera or soak acceptance.
- Session review: benchmark evidence is component-only; no delivery claim. Existing face-holder/hardware work is preserved separately.

## Session ownership

- Android and iOS implementation: one primary session; original benchmark/shell session archived as superseded on 2026-10-25.
- Physical ghost head/tablet enclosure design: separate task, preserve its hardware work.
- Requirements/architecture/repository setup: historical planning context, no second implementation owner.
- Native delivery goal is active in the primary implementation session. Global ~/.codex/AGENTS.md now directs task sessions to use native goals and distinct ownership without spawning duplicate runs.
- Goal backfill for older sessions was rejected by Codex because those sessions have active writer locks. Owner: the next run of each owning session; trigger: resume that session and apply the global goal rule. No direct database edits or extra model turns were used. This does not block Facebot implementation.


## Session naming — 2026-10-25

Session-title cleanup and naming skill **delivered**; this is not product delivery.

- Four visible Facebot chats on colaizzo-mini renamed and read back through supported Codex APIs: `Android & iOS apps`, `Ghost head enclosure`, `Requirements & architecture`, and `Session naming`.
- Installed `~/.codex/skills/session-naming/SKILL.md` and `agents/openai.yaml` on colaizzo-mini. Implicit invocation is enabled, and `~/.codex/AGENTS.md` invokes the skill at substantive task start and material scope changes.
- Rule: 2–5 distinctive words; omit the redundant project prefix, preserve explicit user titles, and keep stable titles through ordinary progress. Runs within normal assistant turns; no background job or other-host installation was created.
- Verification: skill-creator validator passed; invocation metadata and steering checks passed; all four live title read-backs matched. Coverage: app list of 50 recent chats plus pinned chats, filtered by Facebot path/project on colaizzo-mini; archived history was not renamed.
- Session-coe review: Doug's clarification that the project supplies the Facebot label is encoded in the skill and verified on the four live titles. Distinct-task examples preserve subject differences; explicit user-chosen titles remain exempt. Corrected the initial list limit to the supported maximum of 50 and documented it in the skill. No implementation ownership or delivery requirements changed.
- Usage policy followed: `/Users/mv_server/Development/colaizzo-family/data/.openclaw/workspace/USAGE_BUDGET.md`; bounded direct work, no delegated model runs or reset credits.

## Human conversation timing — 2026-10-25

Owner explicitly requested typical human response timing as the target. README and docs/CONVERSATION_TIMING.md now require generated audible reply median <=200 ms and p95 <=500 ms, measured from actual visitor utterance end. Research benchmark: Stivers et al. mean 208 ms / median 100 ms across ten languages. The 500 ms tail requirement is an engineering choice, not a claimed scientific threshold. Prior 1 s/1.5 s proposal is superseded. Current segmented pipeline cannot meet this; incremental/predictive speech work is necessary. No target attained yet. Acceptance-document owner should use these updated timing requirements.

Latest implementation evidence: iPad simulator app installed, launched and face screenshot visually checked; Android APK build passed. Kokoro generated PCM after isolating a preshed tokenizer regression (3.0.14 fails minimal tokenizer roundtrip; 3.0.10 passes with spaCy 3.8.16). Five warm Qwen9b+Kokoro synthetic text-to-PCM samples: median 2286 ms, p95 5988 ms, excluding acoustic input/output. Pipecat server prototype added; eight focused parsing/protocol/output-check tests pass. Full synthetic voice replay timed out without returning PCM; stage-only tracing is now isolating the stall. Authentication rejection and server startup were observed, but these do not prove voice delivery. Qwen3.5:0.8b rejected by current Ollama version; shared service left unchanged, Qwen2.5:1.5b download succeeded for next benchmark.


## Enclosure CAD iteration — 2026-10-25

Editable CAD iteration **delivered**; physical holder and Facebot product are **not delivered**. Owner clarified that the screen itself is the face, with minimal extra border, no hair, slight contour, and two top/bottom pieces. Largest printer: Bambu A1, 256 mm cubic volume.

- Main model: `hardware/lenovo_contoured_bezel.scad`; assembled 182 × 276 × approximately 20 mm, upper print 182 × 147.97 × 20 mm, lower 182 × 138 × 20 mm. Slides over opposite device ends; keyed side tongues, provisional M2 × 6 mm side screws, padded pocket, open back and bottom cable exit. No stand mount is included.
- STL exports and front/exploded renders: `hardware/exports/contoured-*`. Current guide: `hardware/README.md`; decisions: `docs/FACE_HOLDER.md`.
- User explicitly requested a parallel alternatives agent. Its independently modeled thin sleeve + small cap is `hardware/alternatives/lenovo_thin_sleeve.scad`: only 4 mm beyond the tablet each side, sleeve 171 × 241.2 × 14.4 mm, cap 171 × 35.2 × 17.6 mm. Notes and mesh verification are alongside it. This alternative has no insertion-sweep validation yet.
- Main checks: OpenSCAD 2026.10.13 native CLI renders; each half is a connected watertight mesh; A1 bounds including nominal 8 mm brim allowance; full nominal tablet insertion sweep has no plastic collision; intentionally oversize configuration rejected. Receipt: `hardware/exports/contoured-verification.json`; rerun `python3 hardware/verify_geometry.py /path/to/OpenSCAD split`.
- Native OpenSCAD located at `/Users/mv_server/Applications/OpenSCAD-2026.app`; main file launched successfully as a live GUI process. Desktop automation repeatedly returned `cgWindowNotFound`, including after explicit file launch and duplicate-process cleanup; native window visibility is not verified. CLI PNGs were visually inspected. This limits UI assurance, not CAD availability.
- Remaining physical-fit evidence: actual lit-screen boundary/corners, front camera and edge features, USB plug, pad thickness and screw fit; supports/bridging and slicer exclusions also need checking. Owner: enclosure task, with actual hardware measurements as resumption input. The 140 × 234 mm aperture is a conservative placeholder, not an exact bezel fit. Camera cutout remains disabled pending location. No physical print, strength, optical or thermal claim.
- Immediate next step: compare minimal split contour versus sleeve/cap, then calibrate aperture/ports and print a fit coupon before full pieces. Earlier one-piece angled model remains separate for comparison.
- Session review: adapted CAD to the user's evolving minimal-surround intent, preserved previous study, verified actual meshes instead of claiming print success. Intel OpenSCAD release was incompatible with host; native mounted 2026.10.13 build provided working render/export route. Shared quota snapshot read from current session before delegation: 17% used / 83% remaining. No reset credit consumed; policy remains `/Users/mv_server/Development/colaizzo-family/data/.openclaw/workspace/USAGE_BUDGET.md`.

Latest smaller-model baseline: Qwen2.5:1.5b + Kokoro, five warm synthetic text-to-PCM samples: p50 523 ms, p95 4334 ms. Faster than 9B but still fails the new target; samples were during development workloads, not controlled physical acceptance. Nine focused tests now pass, including the tokenizer regression. User authorizes macOS TTS announcements when a specific device test is ready; no ready announcement sent yet.

## Voice transport checkpoint — 2026-10-25 14:12 PDT

Synthetic real-time replay now passes through Pipecat VAD → local Whisper → Qwen2.5:1.5b → output checks → Kokoro → authenticated WebSocket PCM. Unauthorized socket rejected (403); generated audio received; explicit interrupt acknowledged and framework emitted BotStoppedSpeaking. Exact timing is in ignored .local/voice-smoke.jsonl. This verifies a synthetic transport path, not acoustic echo cancellation, real-device latency, continuous visitor interaction or delivery. Earlier replay timeouts remain failures; the passing replay used the smaller model and initialized TTS settings. Nine unit/regression tests pass.

Next implementation: connect native capture/playback with platform echo cancellation and bounded cancellation-aware queues; add camera attention. In parallel, replace segmented response generation with incremental/predictive processing to pursue the binding 200/500 ms end-to-end target.

## Requirements integration — 2026-10-25 21:16 UTC

- docs/ACCEPTANCE.md now matches docs/CONVERSATION_TIMING.md: generated audible reply p50 <=200 ms / p95 <=500 ms; earlier 1 s / 1.5 s proposal is superseded. No attained-latency claim.
- docs/LOCAL_LORE.md adds six sourced Mill Valley facts, original family-safe dialogue and concrete character checks. Content is ready for the software owner to integrate; runtime use and behavior remain unverified.
- Requirements owner verified local documentation links, private-data exclusions, timing consistency and source support. These two edits await integration/publication with the software owner’s new timing specification to avoid a dangling published link.
- Official CameraX and ANR skills installed at android/skills revision 4ebabf2b0fd6c04b7150023c8b612f80592a6226. Main instructions read and installed files verified.
- Next action: sole software owner integrates relevant lore and continues actual voice/client implementation. Physical-device dependencies remain as above. Latest inspected usage event at 21:11 UTC: 81% remaining; historical snapshot, no reset credit consumed.

Passing synthetic voice replay receipt: 1778 ms input-end to first received PCM, 3.24 ms explicit interrupt acknowledgement. Neither is an audible physical-device measurement. Local speech setup has 144 compatible pinned Python packages; `uv pip check` passed.
