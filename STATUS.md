# Facebot status

Updated: 2026-10-25 (America/Los_Angeles)

## Current milestone

Active prioritized work: [task list](docs/TASKS.md). Winking is **P1**, queued for deliberate, sparing single-eye expression with smooth recovery and both-platform validation.

Android conversation prototype reached first owner-observed end-to-end response. The Lenovo is authorized in ADB, and the implementation session confirms physical installation and launch. Owner reports the screen works and produces a response. This proves an initial physical conversation, not measured latency, echo rejection, interruption quality, public-space safety, kiosk, iOS parity or endurance. Product is **not delivered**. Public repository: https://github.com/dclaze/facebot.

Public-space safety is **not accepted**: the lexical output guard passes four synthetic semantic requirement violations unchanged. Persona instructions are currently the only layer addressing those boundaries; passing unit tests do not establish family-safe production behavior. See the guard acceptance checkpoint below.

## Delivery contract and ownership

[Delivery acceptance](docs/ACCEPTANCE.md) was established in commit `7969b2e`. The implementation owner owns runtime validation and results; requirements coordination owns that acceptance document, and the enclosure owner owns hardware design. No duplicate software implementation sessions. The primary native delivery goal remains active.

Implementation checkpoint `f0ddb9a` is pushed and remote/local equality was verified. The acceptance working copy already reflects the researched **200 ms median / 500 ms p95** generated audible reply requirement, superseding earlier provisional timing. Product remains **not delivered**.

Official Google Android skills installed at source SHA `4ebabf2b0fd6c04b7150023c8b612f80592a6226`: CameraX guidance is available for upcoming local attention implementation; ANR guidance is reserved for concrete Android blocking risks. CameraX main instructions have been read; no remote helper scripts executed.

## Agreed direction

- Prototype runtime budget is now **$0 for paid services**, explicitly confirmed by the owner. Keep speech, reply generation and vision local; no paid API, cloud compute or paid fallback. Codex development usage is separate from application runtime, and the earlier $20 digital budget does not authorize paid prototype runtime.
- Open-source Halloween face with a highly sassy, funny character.
- Tablet on a stand, optionally dressed in a costume. Both Android and iOS are now required; the owner plans to connect both physical devices.
- Local Mac inference, realistic speech, camera-based attention, continuous listening and interruption support.
- Responsiveness is critical; binding targets and measurement rules are in README.md, docs/CONVERSATION_TIMING.md and docs/ACCEPTANCE.md.
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

Preserve the active child trial: no server restart, deployment or raw recording until a safe boundary. Finish proactive event dispatch and stop/mute enforcement, verify the staged mouth contour fixes, and evaluate actual generated dialogue quality. [Task list](docs/TASKS.md) tracks priorities. Scene detection currently counts visible faces only; returning-person recognition, couch/costume/action perception, acoustic barge-in, binding reply latency, physical iOS and twelve-hour soaks remain unaccepted.

## Device access dependency

Android USB authorization is resolved; the physical tablet has produced owner-observed audible responses. Do not repeat the former USB-debug request. Physical iOS verification still needs an attached authorized device (owner: Doug; trigger: supported tooling lists the authorized device). Continue independent iOS implementation and simulator/build checks meanwhile. Never reset or enroll devices to work around access.

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

## Speech reuse review — 2026-10-25T21:16:32+00:00

- Published feasibility findings in docs/REFERENCES.md, commit c7eef9a. Moshi has official MLX q4 support, but the inspected example client lacks echo cancellation and has finite step capacity; no Mac latency, persona, safety or endurance claim. PersonaPlex official setup does not establish a working Mac deployment. No new model installed or paid service used.
- Apps owner is active and has integrated bounded lore selection, six-message context, configurable name/voice. Next reported work is native Android capture, echo cancellation and cancellation-aware playback. This is an implementation report, not physical validation.
- Owner requested one macOS spoken readiness announcement for the family test. Apps owner alone emits it after checking the native conversation path; requirements chat does not emit duplicate alerts.

Read-only Android review (2026-10-25T21:17:56+00:00): accepted maximum output frame splits into eight chunks against six queue slots when consumer is delayed. Normal server output is smaller and paced; this is a protocol-boundary finding, not an observed device failure. Sent to software owner for resolution and a focused delayed-consumer test. Requirements chat made no implementation edits.

Guard acceptance review (2026-10-25 21:19 UTC): direct-function synthetic probes show checked_reply passes requests for a home address, an appearance insult, an identity-memory claim, and an unsupported exact candy accusation. This is not evidence the model or device produced those lines. The lexical guard does not enforce these semantic requirements; prompt behavior and public-space regression evidence remain to be validated. Receipt remains private in .local/guard-review.json; software owner received the cases. No live family media used.

Enclosure review preference (2026-10-25): Doug is on a different machine from the CAD host and requested inline previews. Present CAD renders in chat; a local OpenSCAD launch alone does not satisfy visual review. Added `hardware/exports/thin-sleeve-front.png` with a nominal screen reference; main contour front/exploded previews already exist. Session review: corrected preview delivery to match the user’s actual review surface.

## Guard acceptance integration — 2026-10-25 21:23 UTC

- Reproduced the requirements review against the same guard source hash using `scripts/evaluate_guard.py`. Four prohibited synthetic candidate replies pass unchanged (private-information solicitation, appearance insult, identity-memory claim, unsupported exact candy accusation); the safe character control passes. The evaluation exits 1 intentionally for unmet acceptance. Private receipt: `.local/guard-acceptance.json`. No inference/GPU, visitor media or device observation was used.
- This is a real missing enforcement layer, not evidence the model spoke these lines. No lexical patch or four-entry blacklist was applied. The evaluation is a minimum regression set, not a safety certification; even replacement output needs semantic review.
- Next focused integration evaluation, owned by the software session: exercise each category through persona → local model → guard with paraphrases, multi-turn persuasion, prompt injection and benign controls; review both raw synthetic model candidates and guarded outputs for meaning, including fallback suitability. Keep model-produced results distinct from direct-function probes and physical observations. Public-space acceptance remains open.
- Operator mute and visitor stop remain unverified runtime requirements. Check during generated speech and queued speech: authenticated operator mute immediately flushes playback, suppresses subsequent generation/playback until explicit owner resume, and visibly indicates mute; a visitor request for silence interrupts and prevents a follow-up spoken reply. Exercise delayed audio, reconnect and stale-turn completion so they cannot undo mute. Use synthetic transport tests first, then authorized physical acoustic checks on both platforms; an interrupt acknowledgement alone does not establish audible silence.
- Review correction: unit-test success and prompt wording cannot substantiate semantic safety. Preserve this unmet requirement in the current milestone until integration and physical acceptance evidence exists.

## Native audio queue checkpoint — 2026-10-25 21:24 UTC

- Fixed Android maximum-frame/queue mismatch: whole messages admitted atomically into a byte-bounded FIFO; protocol maximum 7680 PCM bytes (160 ms), queue budget 11520 bytes (240 ms). Server serializer now rejects oversized, empty or odd-length output PCM. Normal Pipecat 40 ms pacing remains unchanged. Overflow reconnect policy remains explicit. Queue budget excludes one active packet (up to 160 ms) and device audio buffers; it is not an achieved latency claim.
- `sh scripts/test-playback-queue.sh` tests a delayed consumer, maximum-size frame, six consecutive 40 ms messages, overflow without partial admission, FIFO epochs, clearing, malformed sizes and caller-buffer isolation. Host JVM tests passed; four Python protocol tests passed; Android assembleDebug passed (`.local/android-queue-build.log`). These are deterministic host/build results, not physical playback evidence.
- iOS audio source compiles but conversion callback emits Swift concurrency warnings and the client is not yet connected to the face controller. Next: fix converter callback ownership, wire permission/lifecycle/reconnect and visible speech state, then simulator transport verification. Do not treat a successful compile as working iOS voice.
- Latest ADB check still lists no authorized device. Existing owner USB-debug authorization prerequisite remains; no readiness announcement sent. Camera/kiosk, public-space safety, latency and both physical soaks remain incomplete.
- Usage telemetry at 21:23 UTC: 80% remaining; no reset credits used. Previous guard turn was progress (reproducible unmet acceptance and canonical status update). Queue review improvement is verified by executable boundary cases; no broad pass claim.

Enclosure shape clarification (2026-10-25): owner wants a rounded head-shaped outer edge with a rectangular inner screen opening. New editable iteration delivered at `hardware/lenovo_round_face.scad`; inline render `hardware/exports/round-face-front.png`, separate top/bottom STLs alongside. Continuous rounded silhouette (superellipse exponent 2.8), 230 × 332 × ~20 mm assembled, upper 230 × 175.97 × ~20 mm and lower 230 × 166 × ~20 mm. Wider cheeks are needed to conceal rectangular tablet corners; previous minimal rectangles remain alternatives. Main geometry checks pass for this variant (connected closed meshes, A1 bounds with brim allowance, nominal swept insertion, oversize rejection), receipt `hardware/exports/round-face-verification.json`. Physical fit and optical claims remain unverified. Next: owner reviews rounded silhouette inline, then refine proportions/aperture using measurements. Review correction: prior design rounded the rectangle corners but did not deliver the requested head-shaped outline; corrected the actual CAD silhouette and inspected its render.

## Feedback prototype priority — 2026-10-25 21:25 UTC

Doug prioritized a working feedback prototype. Immediate path is the attached Android tablet over authorized USB, retaining all final acceptance requirements. Private pairing asset prepared and confirmed Git-ignored; paired APK assembleDebug passed. Never publish the paired APK or configuration. Current server restarted with persona integration and protocol bound, loopback health ready; synthetic replay is in progress, not yet a passing result.

`python3 scripts/android-preview.py start` installs and launches only when exactly one authorized device is available, setting USB reverse for the local server. Current attempt reports no authorized device; no installation occurred. Owner step already communicated: enable USB debugging and accept this Mac on the tablet. The command never grants runtime permissions or changes kiosk enrollment. `python3 scripts/android-preview.py stop` provides an operator force-stop route; it is implemented but not device-verified. No family-ready announcement has been made.

Prototype replay results: current persona-integrated server returned generated PCM and explicit interrupt acknowledgement in both synthetic runs. First after restart: 8547 ms to received PCM, 2.73 ms interrupt ACK; second: 1749 ms and 2.70 ms. These two runs suggest a startup cost but do not isolate its cause, establish a distribution, or meet binding speech targets. No family audio retained. Server remains running on loopback for the authorized tablet trial; private receipts `.local/voice-preview-smoke.jsonl` and `.local/voice-preview-warm.jsonl`. Deployment/stop commands and limits documented in docs/DEVELOPMENT.md. Next physical action is installation once USB authorization becomes available.

Enclosure appearance accepted (2026-10-25): Doug approved rounded outer silhouette with rectangular screen opening; rear can be flat because a wig will probably cover it. Existing round-face model already has coplanar rear supports with an open center, so no geometry change was needed. Retain two-piece construction and bottom cable exit; printed hair/full skull unnecessary. Source comments and design notes updated. Previous geometry verification remains applicable. Appearance approval does not resolve screen/port measurements, physical fit or slicer checks. Session review: no material issue; avoided adding an unnecessary solid back.

Requirements review follow-up (2026-10-25T21:27:05+00:00): inspected PlaybackQueue and host test coverage. Original partial-admission mismatch is corrected by whole-frame admission with explicit byte limits; physical interruption latency remains unverified. Direct ADB check still returned an empty device list. Software owner continues independent iOS/guard work; physical Android installation resumes when an authorized device is visible. Future spare-tablet bot concept is noted only in docs/ROADMAP.md and does not change current scope.

## Face / camera / chat prototype — 2026-10-25 21:29 UTC

Owner narrowed immediate feedback priority to seeing a basic app face, camera and chat end to end. Android development configuration now enables a small live camera preview above the face (`showCamera`, defaults false); no media is saved. Native voice, front-camera attention and visible speaking state are wired. Paired Android preview rebuild passed (`.local/android-preview-camera-build.log`); latest install attempt still found no authorized tablet, so no screen/device delivery claim. The owner USB-debugging approval step was communicated once with exact navigation; no device enrollment/reset or security bypass attempted.

iOS face now connects the native voice actor through microphone permission, foreground/background stop, reconnect and speaking/status display. Converter callback owns its immutable input through a lock-protected one-shot bridge; playback generations reject stale completion callbacks after flush/stop. Swift 6 strict-concurrency build passed without warnings (`.local/ios-connected-build.log`), and updated unpaired iPad simulator app installed/launched. Simulator voice/audio, physical iOS provisioning and camera remain unverified. Private iOS config copying is supported and ignored. Next focus remains installing and observing the Android face/camera/voice prototype once device authorization is present.

## Requirements coordinator handoff — 2026-10-25T21:28:35+00:00

The Requirements & architecture coordination goal is blocked on physical-device access after three consecutive goal turns confirming the dependency. This does not stop the separate Android & iOS apps implementation goal and is not product delivery. Independent requirements, sourced lore, reuse research and concrete queue/guard reviews are handed over. No duplicate implementation owner is created.

Unmet acceptance comes from the owner’s explicit both-platform, real conversation, touch-lock and twelve-hour requirements: authorized physical installation and acoustic/endurance evidence are missing. USB registry sees the Lenovo, direct ADB inventory is empty, and ADB wireless discovery is empty. Existing build/replay/simulator evidence cannot substitute for physical acceptance. The already documented device-owner action and resumption trigger above remain authoritative. Resume this coordination goal when device access is available or the software owner requests an acceptance review. Software owner retains the family-test macOS announcement; do not announce ready before the native conversation path is checked.

## Preview diagnostics and verification — 2026-10-25 21:32 UTC

Android preview now logs only first native microphone PCM arrival, platform AEC enabled state and first playback-head advancement under the FacebotAudio tag. No samples, transcript, identity or images are logged. Playback-head progress proves the device consumed PCM, not measured acoustic loudness or echo rejection. Android diagnostic build passed; 13 Python tests and host JVM queue checks passed. The separate semantic guard acceptance still has four failures. At the earlier pre-install check, developer mode was enabled but USB-debug authorization was still missing. That prerequisite has since been resolved, as recorded below. Last connection-only turn was no progress; this turn added native validation instrumentation and passing focused verification instead of repeating unchanged polls.

## First physical conversation — 2026-10-25 14:31 PDT

Doug reports the screen is working end to end and he is getting a response. Direct ADB check now lists the Lenovo TB-J606F as authorized; the apps session confirms installed/launched. The previous Android authorization blocker is resolved. Owner report establishes a basic audible exchange, not quantitative acoustic acceptance. Next priority: validate interruption/echo and measure complete reply delay, tune voice and character, then finish safety/mute/kiosk, physical iOS parity and twelve-hour runs. Candy commentary follows a reliable core conversation. Sole software ownership remains Android & iOS apps; no duplicate coordination run started.

## Native path observed and trial preserved — 2026-10-25 21:32 UTC

Installed Android preview on Lenovo TB-J606F / Android 11. Both runtime permissions are granted; camera service references Facebot; native capture diagnostic observed; server reports one occupied voice session. AudioFlinger showed the app's 24 kHz playback track with nonzero consumed frames and queued PCM alongside the active 16 kHz capture track. Owner independently reports an audible response. A later metadata sample captured input progress while output was idle; private receipt `.local/android-native-path.json` includes the paired APK SHA-256, not media. No transcript/image/audio retained.

The requested macOS readiness phrase was spoken exactly once after those checks; ignored `.local/readiness-announced` prevents duplicates. The live family feedback trial remains running. No disruptive restart or competing inference benchmark will be performed during the trial without indicating it. Immediate next evidence: interruption behavior, self-echo and perceived reply delay, followed by consented quantitative acoustic checks. Operator force-stop is available through the authorized USB CLI but remains unexercised during this trial. Full acceptance stays open.

## First feedback revision — 2026-10-25T21:36:44.531968+00:00

Owner rejected the placeholder face, reported no visible image processing and insufficient sass. Android face replaced with brows, moving pupils, asymmetric grin, depth shading and speaking mouth motion. Development camera overlay now marks the selected face center; on-screen vision status distinguishes scanning, detection and unavailable results. This makes analysis behavior observable; it does not itself prove detection reliability. CameraX/ML Kit remains the actual local image-processing path, with no identity or retained media.

Persona strengthened with dry sarcasm, mock grandeur and short situational punchlines; remains configurable and family-boundary constrained. Three persona unit tests passed, but perceived sass and semantic safety require live evaluation. Android expressive build passed and installed/launched on the physical tablet; refreshed server shows occupied voice session. Operator force-stop was exercised before the announced update: app process absent and server occupancy released. Audible stop time and visitor stop behavior are not established by that check. No repeated readiness announcement.

Prior implementation checkpoint `02a247d15427239106523a20a26faa1bfa586c6c` pushed and remote equality verified. Latest feedback revision remains a separate working change until evaluated. No paired APK, token, media or device identifier published.

## Queued active-speaker gaze — 2026-10-25T21:37:10.421895+00:00

Added Doug's request to docs/ROADMAP.md under Bring the face to life. Subtle, smoothed gaze should follow evidence of the active speaker, with stable target selection and calm neutral fallback for uncertainty/off-camera speech. Current largest-face tracking does not establish who is speaking. Hardware feasibility and two-person/ambiguous-speech physical validation are required before reliability claims; reuse existing signals, no identity or saved profiles, and no blocking speech/barge-in work. Sole software owner retains the item; current prototype feedback and audio reliability priorities are unchanged. No runtime change or restart for this queued request.

## Proactive interaction requirement — 2026-10-25

Doug explicitly requires proactive behavior: the ghost should initiate greetings and contextual interaction based on fresh observed events instead of waiting for a question. Added a priority section to docs/ROADMAP.md with encounter state, quiet/mute behavior, cooldowns, no fabricated visual claims, and physical acceptance cases. Requirement only; not yet implemented/validated by this update. Runtime remains local with $0 paid services. Software owner receives this as a queued priority request; this coordination chat does not start a duplicate implementation goal.

## Character correction: extreme clean sass — 2026-10-25

Doug says the current character is still too basic. Explicit direction: no cursing; extremely sassy, witty, satirical and edgy while kid-safe. The edge should come from sharp comic reversals, dry delivery, mock grandeur and situational satire, not profanity, sexual innuendo, threats or humiliating visitors. Preserve direct useful answers and respectful silence when needed. Increase specificity and improvisation instead of generic ghost puns, bland greetings or repetitive candy slogans. This is new owner feedback for the existing character/software owners; no runtime improvement is claimed by this note.

## Mill Valley roast corpus — 2026-10-25

Ownership: this chat owns the authored roast corpus only; the Android & iOS apps chat remains the sole runtime implementation owner. Doug requested a hyperlocal, extremely funny, edgy-but-kid-safe roast library with swarm review of every interaction, then clarified that jokes must make sense without niche local knowledge.

- Draft: `content/mill_valley/corpus.json`, 72 synthetic two-turn interactions (64 comic, 8 care/boundary); 11 public source anchors. No real visitor transcripts used.
- Three independent reviews are in progress: comedy, family boundaries, and local grounding/accessibility. Every reviewer covers every interaction. Initial review found achievement-targeting, a correction ignored by a callback, an ambiguous visitor-directed comeback, and stop-state/privacy wording to repair before delivery.
- Readable edition: `docs/MILL_VALLEY_ROAST_LIBRARY.md`; selection/performance contract: `content/mill_valley/README.md`. Local place names must come with enough context for children and visitors; adult references may add a second layer but cannot be the only joke.
- Runtime is unchanged; no live prototype restart, inference benchmark, new implementation owner or deployed-safety claim. Next: reconcile findings, re-review final bytes, validate full coverage and hand off the corpus.
- Usage policy read at `/Users/mv_server/Development/colaizzo-family/data/.openclaw/workspace/USAGE_BUDGET.md`; latest pre-swarm account telemetry was 23% used / 77% remaining at 2026-10-25 21:52 UTC. No reset credit used.

## Mouth and task-list checkpoint — 2026-10-25

Added docs/TASKS.md with explicit P0/P1 work and acceptance gates; Doug’s wink request is P1 and not yet deployed. Mouth specialist supplied nine continuous-contour visemes, true closed consonants and finite transitions; integration Android build passed in 5 seconds. New native renders and moving-speech review remain required before a quality claim. Synthesis-derived cue timing and fresh scene metadata are implemented, but physical lip-sync, scene latency and richer action understanding remain unaccepted. Local model dialogue screens still showed factual/style failures; no prompt-only improvement claim. The native delivery goal stays active.

## Encounter foundation and live-trial preservation — 2026-10-25

Previous acknowledgment-only turn was no progress; this turn added tested code without restarting the live app/server. New bounded in-memory encounter policy debounces arrivals, rejects stale observation streams, suppresses events during supplied speaking/silence states, prevents repeated introductions and invalidates conversational history after stable audience-count changes or sustained zero detection. FrameTrace now drops prior dialogue on a changed encounter generation, retaining the triggering utterance. This is conservative privacy isolation, not identity recognition; same-count visitor replacement remains unresolved. Event policy is not yet wired to initiate speech or runtime silence state, so proactive behavior is not claimed deployed.

Volunteered-name/correction guidance added to persona without mandatory onboarding; generated compliance is not yet evaluated. No names or visitor media are written to disk. Thirteen focused encounter/scene/persona tests pass (synthetic, no inference). New mouth still review found detached highlight, pinched corners and gray teeth; specialist fixed source, pending native re-render and moving-speech verification. No restart or recording during child trial. Latest quota telemetry 2026-10-25T22:00:47.441Z: 76% remaining; no credits used. Delivery goal stays active.

Closeout correction: projected handoff now replaces obsolete Android authorization and audio-integration blockers with current evidence; historical checkpoints remain labeled by date. No global process change needed.


## Context, realism and owner additions — 2026-10-25T22:04:27.363654+00:00

Research deliverables: docs/REALISM_RESEARCH.md (source-led social timing, face/listening/voice priorities, $0 runtime reuse candidates and acceptance); docs/NEIGHBORHOOD_CONTEXT.md (cited public fact cards); ignored private .local/site-context-research.md (exact-property evidence and unresolved build chronology, mode0600). City2021HCS, HRI,2026neighbor planning sheet and city2026Halloween notice reviewed. A neighbor's history is not the installation's history; original build year/architect remain unverified. No historical haunting claim established. Public docs omit the private installation address.

Owner requests now recorded: about3,000passersby, automatic Halloween interaction memories with ZERO visitor setup or retrieval workflow; natural volunteered-name introductions/corrections; volume-capped theatrical scared-face/yelp reaction; a contextual costume dad-joke skill; and separate night-specific rules with occasional ONE PIECE OF CANDY PER PERSON. Added contexts/HALLOWEEN.md and contexts/skills/COSTUME_DAD_JOKE.md. These are behavior contracts awaiting runtime integration, not enabled features. Current face detection does not identify costumes or reliably associate a returning visitor. Previous nickname/secret-word proposal was explicitly rejected and removed from the active specification.

Live trial remains undisturbed by this chat. Source inspection and live health showed an occupied local voice session, disabled transcript debug logging, no audio/video/transcript persistence path in the inspected app, and generated face-preview images rather than camera captures. The child's current conversation was not collected by this work. New night-memory authorization does not retroactively enable collection or model training. Runtime owner must implement bounded local memory, deletion/expiry and association uncertainty; no face/voice biometric enrollment inferred.

Owner reports unnatural voice. Current adapter defaults Kokoro82M/af_heart/speed1.05 and collects synthesis before sending20ms frames. Whole-response generation and transport streaming must be distinguished. Next owner action: controlled synthetic voice/delivery comparisons outside active family use, then compare expressive local alternatives without paid runtime or unsupported latency claims.

User-requested new Codex chats created and renamed: Boo conversation lab (01a17512-3d66-79a3-9083-589fceba2e8a); Boo local dad-joke timing (01a17512-3d66-7c71-a89c-e3c581326806); Boo interaction coverage research (01a17516-346e-75f2-812b-fefd1d38d7ad). Separate CLI workers received bounded file ownership and no-runtime-change instructions. Initial turn-start receipts verified; app wait metadata reported notLoaded/interrupted for a CLI worker while its OS process/event stream continued, so do not treat that metadata alone as completion. The third chat is instructed to use authenticated chatgpt.com with fictional content only and to report an access gap rather than fabricate service use. Results pending, not accepted yet.

Coordination correction: local CLI0.163 and managed server0.153.4 differ. Generated schema exposes turn/steer, but proxy initialization attempts did not return. No immediate steering receipt; CLI queue message01a17512-e7c3-7c20-9913-b07f5ddccd4a delivered as queued to the sole apps owner. Do not claim queued means immediately read. No server/daemon restart or authentication change attempted. Requirements also live in shared files. Usage last checked77%remaining at21:51UTC; reserve policy at /Users/mv_server/Development/colaizzo-family/data/.openclaw/workspace/USAGE_BUDGET.md remains binding; no reset credits or paid runtime services used.

Session review: applied corrections to visitor-memory friction, neighboring-property attribution and synthesis-vs-transport claims; verified private-file exclusion and git diff whitespace check. No overall delivery claim. Immediate integration priorities remain acoustic timing/interruption, expressive local voice, scene-grounded character and the event-specific behavior/memory tasks under Android & iOS apps ownership.

### Roast corpus editorial delivery — 2026-10-25

The 72-interaction **editorial corpus is delivered**; runtime integration and the Facebot product remain not delivered. All 72 entries have final keep decisions from each of three independent reviewers (216 entry-level final reviews, both turns covered). Revised 48 entries; all reviewers independently caught an orphaned follow-up in MV056, which was repaired and rechecked. Final corpus SHA-256: `26ea94930bb712d584276f44e5389b6b10796a53be986b67d533082777f3c359`.

Validation: `python3 scripts/check-roast-corpus.py --require-reviews --render` passes 72 entries, 142 spoken turns, 11 source anchors, exact-hash complete review coverage. Negative structural checks reject duplicate IDs, unknown sources, spoken content in silence actions and overlong lines. Git whitespace check passed. Comedy ratings remain honest: 22 usable, 36 strong, 6 standout, 8 care cases unscored; this is editorial judgment, not measured audience laughter or runtime safety.

User added a follow-on request: show the top 20 dad jokes and have actual ChatGPT.com sessions swarm-review quality, retaining only high-confidence picks. Authenticated browser route opened; three independent review sessions are being prepared. This follow-on shortlist is distinct from the complete corpus and does not discard its usable training/reference entries.

## Proactive dispatch and visitor silence — 2026-10-25

Arrival event dispatch is now wired into the local Pipecat pipeline in source, with explicit system EVENT metadata rather than fabricated user speech. Stable presence triggers at most one greeting per encounter, subject to freshness, speaking/pending-response exclusion, cooldown and a quiet gap. Visitor speech cancels a pending introduction. Supported direct stop phrases latch silence before user aggregation, broadcast interruption and suppress generated output; explicit resume phrases release the latch. This is deterministic phrase handling, not proof that every paraphrase or acoustic situation works.

Synthetic tests cover arrival dispatch, no fictional user turns, stop/resume, speaking exclusion, prior-context removal, one-shot event context, and actual Pipecat timer start/EndFrame cleanup. No local model, microphone or family media was used in these tests. Current live server/tablet were not restarted; these changes and the latest mouth contour fixes remain undeployed to preserve the child trial. Next safe deployment must verify spontaneous greeting, speech-triggered interruption and physical stop/resume. Same-count audience replacement and automatic returning-person memory remain unresolved; no identity claim.


## Crowd handling requirement — 2026-10-25T22:06:24.622141+00:00

Doug explicitly requires MANY simultaneous faces / mobs of children. Source review confirms Android receives multiple detections and reports a count, but gaze selects the largest face; no active-speaker association or temporary track set. VoiceClient drops counts above32 and protocol accepts0–32; this is not a measured capacity guarantee. Encounter generation changes with stable count changes, risking dialogue resets in moving crowds. iOS camera parity and physical crowd performance remain unaccepted.

Added docs/CROWD_MODE.md and P0 launch task in docs/TASKS.md: group attention/floor management, bounded ephemeral tracks, graceful overflow, no greeting storms, conversation continuity under background churn, safe personal-memory isolation and controlled physical/synthetic test tiers. Runtime unchanged; no restart, visitor recording or inference workload from this review. Sole apps owner receives concrete findings as a queued message. Verification: inspected current source paths and checked document diff whitespace; no camera/voice capacity claim. Session review: distinguished multi-face detection, transport limits and actual crowded interaction; no material implementation change or new user dependency.

Checkpoint verification: 33 Python tests passed in 4.488 seconds; Android debug build succeeded in 5 seconds. These include synthetic pipeline lifecycle coverage, not physical acceptance. Source publication does not deploy to the running server/tablet.
