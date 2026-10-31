---
name: facebot-kiosk-recovery
description: Install, diagnose and verify the local Facebot macOS kiosk supervisor, including child crashes, HTTP hangs and tablet reconnection after a coordinated restart. Use for Facebot runtime recovery, not Android app installation or general Mac cleanup.
---

# Facebot kiosk recovery

Read the repo's canonical `STATUS.md` current ownership entry before runtime operations. Use the dedicated implementation tree for changes; only the named runtime owner installs, stops or reloads the live service. Existing user authorization controls a coordinated recovery; do not introduce a separate approval gate for reversible work already requested.

Use [the recovery runbook](../../docs/KIOSK_RECOVERY.md) for install options, timing, trusted-LAN configuration and the physical recovery drill. Run `scripts/kiosk-service.py status` first. Distinguish a fresh supervisor observation, current HTTP health and actual tablet/audio recovery. A `ready` health result does not prove the speech pipeline or tablet is working.

- For `backoff`, inspect only lifecycle classification and the configured release/profile/model/TTS. Never print token files or dump process environments. Reproduce crashes/hangs with `tests/test_kiosk_service.py` before changing recovery policy.
- For `port_conflict`, identify the existing runtime owner. The service must not kill/adopt a foreign listener; removing its lock is not recovery.
- Once supervised, use `stop`, `start`, `restart` and `uninstall`; do not use the legacy `restart-server.py`, which competes with the watchdog.
- Preserve the explicitly selected model/profile/TTS and kiosk mode. Trusted LAN requires the owner's explicit opt-in and an RFC1918 address; never substitute wildcard/public binding to make a connection work.
- For an authorized fault drill, verify current PID ownership before killing that one child. Observe new PID, fresh readiness, tablet reconnection and an actual response; record simulation and production results separately.

At handoff, record exact release commit, service state, ownership, verified recovery timings and remaining physical acceptance in `STATUS.md`. This service starts after macOS login and cannot substitute for a powered, awake Mac or healthy inference/network dependencies.
