# Local kiosk recovery

`scripts/kiosk-service.py` runs Facebot as a macOS user LaunchAgent. It uses no model calls or paid services. A small foreground supervisor starts the server, observes `/health`, and replaces only its own child after exit or sustained HTTP failure. Launchd restarts the supervisor and removes its process group if the supervisor dies.

This is process and HTTP recovery. It does not establish microphone recognition, audible speech, a healthy inference pipeline, Wi-Fi coverage, tablet reconnection, or 12-hour endurance. The model engine, network and tablet have their own lifecycle. The Mac must remain powered and awake; this user agent starts **after login**, not at the pre-login screen. FileVault/reboot still requires the owner to log in.

## Install a tested release

The runtime owner performs the handover at an idle boundary. Read the canonical `STATUS.md` ownership entry first. Other implementation worktrees must not install or stop this service. Do not run the old `restart-server.py` after service adoption: the supervisor owns the server PID and will replace a manually killed child.

1. Prepare a persistent release checkout with its working `.venv`, existing local assets and pairing token. Do not remove or move this checkout while the service is installed. Ollama and required models must already be installed/running; the installer does not provision them.
2. Record the current profile, model, TTS and speech rate. Use explicit values below; no backend or model change is implied. Verify the tested release supports `FACEBOT_KIOSK_MODE=1` (the service always preserves it).
3. Stop the previous server through its existing owner. The installer deliberately refuses an occupied service port and never kills or adopts an unknown listener.
4. Run from the release checkout, substituting its absolute paths:

```sh
python3 scripts/kiosk-service.py install \
  --root /absolute/path/to/release \
  --python /absolute/path/to/release/.venv/bin/python \
  --token-file /absolute/path/to/private/pairing-token \
  --profile halloween --model qwen2.5:1.5b --tts kokoro --speech-rate 1.12
python3 scripts/kiosk-service.py status
```

Loopback is the default. For the native app's explicit trusted-LAN connection, add `--host 192.168.1.50 --trusted-lan`, replacing the address with this Mac's current RFC1918 IPv4 address. This produces server arguments `--host PRIVATE_IP --allow-private-lan`; it requires the integrated server release with that flag. Wildcards, public addresses, link-local addresses and hostnames are rejected. Trusted LAN is unencrypted: use an owner-controlled private network, never forward the port to the internet. A DHCP reservation keeps the tablet's saved server address usable. Changing the Mac's address requires updating both installation and tablet connection.

The token is read from its existing private file on every child launch. It never enters the plist, command arguments, status or logs. Server stdout/stderr are discarded deliberately; lifecycle-only logs avoid capturing tokens, speech or visitor content. Debug startup errors separately in an owner-controlled foreground session after stopping the service.

The generated plist lives at `~/Library/LaunchAgents/org.facebot.kiosk.plist`; state is `~/Library/Application Support/Facebot/kiosk/`. A custom `--state-dir /absolute/private/path` can precede every command. The shared lock always stays at `~/Library/Application Support/Facebot/kiosk-owner.lock`, so differing release trees/state directories cannot launch competing kiosk supervisors. Never delete this lock to force a takeover.

## Observe, stop and remove

```sh
python3 scripts/kiosk-service.py status
python3 scripts/kiosk-service.py stop
python3 scripts/kiosk-service.py start
python3 scripts/kiosk-service.py restart
python3 scripts/kiosk-service.py uninstall
```

`restart` waits for launchd to finish removing the old job before registering its replacement. Each stop/start phase has a 30-second deadline; transient bootstrap failures retry after 0.25 seconds, doubling to a maximum 2-second delay. Repeated `start` or `stop` commands are idempotent. A failed deadline returns an error instead of starting a competing job or retrying forever.

`status` shows the last phase, its age, current health and whether launchd has the job loaded. A stale `ready` observation is historical; require `healthy_now: true`, a fresh observation and `launchd_loaded: true`. `child_pid` identifies only the currently supervised child. `stop` unloads the job so launchd does not immediately replace it; it remains installed for the next login or explicit `start`. `uninstall` unloads and removes the plist, while retaining private configuration and bounded logs for rollback. To change release/configuration, uninstall and install again with the desired arguments.

A child has 180 seconds to become ready (including model/audio prewarming). Then the watchdog checks every 5 seconds, with a 2-second HTTP timeout and three consecutive failures before replacement. Child shutdown allows 10 seconds, then kills/reaps a stuck child. Retry delay doubles from 2 to a maximum of 60 seconds; two continuous healthy minutes reset it. Thus an indefinitely broken installation retries at most once per minute after the initial attempts, rather than thrashing. Launchd separately throttles supervisor respawns to 30 seconds. `port_conflict` waits 60 seconds without touching the other process.

`recovery.log` plus two rotations occupy less than 768 KiB; status/configuration files are private, fixed-size records. No server output is captured. `backoff` includes a bounded classification (`child_exit`, `health_timeout`, `startup_timeout`, `start_error`), not an exception, environment or response body.

## Verification and recovery drill

The deterministic suite uses temporary listeners and actual child processes; it never contacts the live kiosk or installs a LaunchAgent:

```sh
python3 -m unittest discover -s tests -p test_kiosk_service.py -v
```

It covers child SIGKILL, hung HTTP with ignored SIGTERM, profile mismatch, foreign listener refusal, two competing supervisors, exponential retry limits, clean reap/lease release, log retention, token exclusion, RFC1918 validation and generated plist configuration. Plist generation tests mock launchctl; they are not evidence of OS-level restart behavior.

After authorized activation, the runtime owner records the actual release commit, fresh health and tablet connection, then performs a brief idle recovery drill:

1. Read `status`; verify the child PID belongs to this release and the tablet is idle. Kill **only that verified child PID**. Observe a new PID and fresh ready health, then a restored tablet voice/vision connection. A health response alone does not prove tablet recovery.
2. Stop and start using the service commands; verify the old child is absent, only one replacement listens, and profile/model/TTS/kiosk mode stayed unchanged.
3. At an owner-approved idle boundary, terminate only the verified supervisor PID to test launchd replacement. Verify its old child was cleaned up, one replacement is ready and the tablet reconnects. Do not use a broad `pkill` or kill an unverified saved PID.
4. Verify a real tablet response and owner mute after reconnection. Record observed timings as local production evidence. Keep synthetic hang/crash fixtures separately labeled.

A reboot/login drill and long-duration mounted run remain separate acceptance observations. If health is fresh but speech is stuck, the current HTTP watchdog cannot diagnose it: preserve diagnostics for the runtime owner and use one coordinated `restart`; do not claim an automatic inference-pipeline repair. If a foreign process occupies the port, identify its owner and release it through that owner's controls instead of deleting the lock or repeatedly installing.
