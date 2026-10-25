# Facebot status

Updated: 2026-10-25 (America/Los_Angeles)

## Current milestone

Repository-foundation milestone **delivered**: public repository at https://github.com/dclaze/facebot, with initial commit `961389e`. Product remains in requirements planning and is **not delivered**. No runnable application, selected model stack, or performance measurements exist yet.

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

## Open decisions

1. Exact tablet model and OS; camera view of visitors and candy bowl.
2. Implement the required immersive/touch-locked experience. Proposed approach: shared face interface with thin native clients and platform kiosk controls; exact stack pending device inspection. Browser-only deployment is no longer the preferred baseline.
3. Voice, character name, and calibrated sass level.
4. Candy-reminder acceptance criteria; exact hidden-piece counting is not assumed feasible.
5. Final latency thresholds and full-duplex behavior beyond interruption handling.

## Immediate next step

Inspect both devices when connected; establish placement and whether two characters must run simultaneously, then finalize the benchmark-first implementation plan. The owner requested remaining requirements discussion before full implementation.

## Verification

Documentation-only milestone. No runtime tests or latency claims. Seven-file publication allowlist, staged private-data scan, relative-link checks, private-file exclusion and git diff whitespace checks passed before the first push. No private planning notes were committed. Remote creation and first push succeeded. Public visibility, MIT license, main branch and remote/local commit equality verified at commit 57d9421. Subsequent documentation updates require the same push verification.
