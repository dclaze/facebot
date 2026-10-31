---
name: facebot-kiosk-certification
description: Review a Facebot kiosk release for a specific use case with software checks, artifact hashes, actual visual inspection and separately labeled physical evidence. Produces internal readiness reports, not external certification or automatic deployment.
---

# Facebot kiosk readiness

Start with the current runtime owner and acceptance scope in `STATUS.md`. Keep worktree changes isolated and do not install apps, run live faults or replace services from a second session. User-authorized reversible implementation and tests need no additional process approval gate.

Use `scripts/certify-kiosk.py` and [the public setup/evidence guide](../../docs/PUBLIC_SETUP.md). The runner aggregates deterministic tests, native Java fixtures, processor replay and hash-bound observation receipts. It does not interpret images/audio or establish physical facts from a passing test. `--check` validates inputs without running suites; `--quick` deliberately leaves extra/native/replay checks incomplete. Do not relabel those omissions as passes or rerun unchanged suites without a new risk.

For each actual use case (for example, a mounted Halloween candy tray):

1. Review the intended invitation, response, stop behavior and fallback. Check enabled/disabled skill persistence against the actual routing, not just the settings screen. Unknown/noisy speech must remain within the chosen mode.
2. Inspect the actual rendered desktop/mobile owner controls and native tablet face using image/browser tools. Check readability, clipping, focus, action feedback, truthful installation/price state and the correct end/rest pose. Do not approve from source or a screenshot file's existence. Capture after animations settle; repeated raster strips can be screenshot artifacts, so obtain a second viewport capture before diagnosing a DOM defect.
3. Run affected deterministic checks. Keep cached response timing, generated synthesis timing, native playback-head acknowledgement and measured audible speech as separate evidence levels.
4. The sole runtime owner performs any authorized idle recovery/Wi-Fi drill and records real outcomes. A connection, health response or native playback-head receipt is not by itself acoustic evidence. Full acceptance still requires the documented 12-hour run and measured generated speech latency; the candy-tray trial can have a narrower, explicit handoff.
5. Fix evidenced issues, recheck only affected behavior, then bind the report to the exact source commit and release artifacts. Preserve raw observations privately; never put pairing tokens, device identifiers or visitor media in public source packages.

Use one receipt per physical category, with actual timestamps and artifact hashes; see the guide for schema. Do not fabricate receipts to satisfy a checker. Report missing evidence and its owner once in `STATUS.md`, distinguish internal readiness from external certification, and name the next concrete verification step.
