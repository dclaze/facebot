# Facebot status

Updated: 2026-10-25 (America/Los_Angeles)

## Current milestone

Repository-foundation milestone **delivered**: public repository at https://github.com/dclaze/facebot, with initial commit `961389e`. Device reconnaissance has begun; product is **not delivered**. No runnable application or performance measurements exist yet.

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

Prepare the benchmark-first implementation around existing local components. Default assumption: one active character at a time; validate Android and iOS separately unless simultaneous operation is requested. Treat remaining voice/name choices as reversible implementation defaults.

## Device access dependency

Physical Android install/audio/camera verification requires an authorized ADB connection. Evidence: USB registry sees Lenovo Tab P11, ADB device list is empty, wireless-debug discovery is empty. Owner action: enable USB debugging and accept the connected Mac's authorization prompt on the tablet. Resume trigger: the device appears in ADB as `device`. This blocks physical-device verification, not independent build/server work. iOS physical-device verification also awaits an attached authorized device. Do not reset or enroll either device as a workaround.

Face-holder concept added on 2026-10-25: see [design notes](docs/FACE_HOLDER.md). Owner wants a full head, possibly hooded. Proposed hollow rounded shell around a separately supported padded cradle, removable back, black oval surround and optional smoked visor; visor requires an optical sample test. Approximate concept envelope 240 × 340 × 200 mm, not fabrication dimensions. Next physical-design step: establish front/edge geometry and stand attachment before a cut template or CAD model. Concept only; physical installation is not delivered. Closeout review: no material issue; exact cut geometry and bezel disappearance are explicitly unverified. Shared quota policy: `/Users/mv_server/Development/colaizzo-family/data/.openclaw/workspace/USAGE_BUDGET.md` (historical readings are not current quota).

## Verification

Documentation-only milestone. No runtime tests or latency claims. Seven-file publication allowlist, staged private-data scan, relative-link checks, private-file exclusion and git diff whitespace checks passed before the first push. No private planning notes were committed. Remote creation and first push succeeded. Public visibility, MIT license, main branch and remote/local commit equality verified at commit 57d9421. Subsequent documentation updates require the same push verification.
