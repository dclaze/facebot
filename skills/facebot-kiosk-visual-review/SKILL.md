---
name: facebot-kiosk-visual-review
description: Review the actual Facebot candy-tray kiosk face, captions, transitions and recovery screens from observed frames. Use before declaring a changed tablet experience ready for mounting.
---

# Facebot kiosk visual review

Read the current runtime owner in the canonical STATUS.md. Only that owner installs, reloads or drives the physical tablet. Other reviewers use captured frames or isolated local previews; worktree ownership alone does not grant runtime control.

Review frames from the app being delivered. Record device or emulator, viewport, build/commit, scenario and capture path. A drawing of the intended design, source inspection, or generated mockup is not an observed app frame. Label synthetic previews and replays; do not present them as physical microphone or Wi-Fi evidence.

Inspect idle, speaking, longest captions, special-performance onset/end, disconnect, reconnect, and owner setup when affected by the change. Examine eye and mouth silhouette at room distance, black background continuity with the enclosure, legibility, clipping, distracting debug overlays, and clean return to the resting face. Check transient frames rather than only a flattering still. For expressions tied to speech, compare with the native playback clock and audio evidence.

Write a concrete critique: visible issue, impact, fix, and a newly observed frame after the fix. If no issue is found, state the bounded scenes actually reviewed. Never self-certify “perfect,” infer sound from an image, infer successful Wi-Fi from USB connectivity, or mark an unobserved scene verified.

Only capture what the task needs. Keep visitor imagery, pairing tokens, device identifiers and recordings in ignored private evidence. Public skill packs and APKs must not contain those assets. Report remaining physical acceptance separately from passing build or replay checks, without inventing additional user approval gates.
