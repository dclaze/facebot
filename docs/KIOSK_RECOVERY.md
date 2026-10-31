# Local kiosk recovery

`scripts/kiosk-service.py` runs Facebot as a macOS user LaunchAgent. It uses no model calls or paid services. A small foreground supervisor starts voice and owner controls, observes voice `/health` and owner `/api/settings`, and replaces only its own failed child. The children recover independently: an owner-controls crash does not interrupt voice, and voice recovery leaves the shop available. Launchd restarts the supervisor and removes its process group if the supervisor dies.

This is process and HTTP recovery. It does not establish microphone recognition, audible speech, a healthy inference pipeline, Wi-Fi coverage, tablet reconnection, or 12-hour endurance. The model engine, network and tablet have their own lifecycle. The service uses `caffeinate -i -w SUPERVISOR_PID` to prevent idle system sleep only while it runs. This does not override a closed lid, explicit sleep/shutdown or lost power. The Mac must remain powered and awake; this user agent starts **after login**, not at the pre-login screen. FileVault/reboot still requires the owner to log in.

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

New installs also run the owner settings and free skill shop at `http://YOUR_BIND_HOST:8766/` and `/store`. Access defaults to the host Mac only; to allow one owner phone/tablet, explicitly add `--owner-client 192.168.1.60` at installation (repeat for additional owner devices). An arbitrary visitor on the same LAN is not allowed. Bind host follows the voice host; do not broaden it to a wildcard. `--admin-port` changes the owner UI port; the integrated proxy currently requires voice port 8765. `--no-admin` disables this child for a voice-only setup/custom voice port, and `--no-sleep-protection` disables the idle-sleep inhibitor.

The owner child requires the release's `.local/pairing-token` path (a shared private `.local` symlink is supported), because its voice proxy uses that file. The token is not passed to the admin child's environment. Existing saved service configurations retain their previous behavior; to adopt owner controls and sleep protection, uninstall and reinstall with the same release/profile/model/TTS/host/owner choices. Stop a separately launched admin listener through its owner first; installation refuses an occupied admin port.

The token is read from its existing private file on every child launch. It never enters the plist, command arguments, status or logs. Server stdout/stderr are discarded deliberately; lifecycle-only logs avoid capturing tokens, speech or visitor content. Debug startup errors separately in an owner-controlled foreground session after stopping the service.

The generated plist lives at `~/Library/LaunchAgents/org.facebot.kiosk.plist`; state is `~/Library/Application Support/Facebot/kiosk/`. A custom `--state-dir /absolute/private/path` can precede every command. The shared lock always stays at `~/Library/Application Support/Facebot/kiosk-owner.lock`, so differing release trees/state directories cannot launch competing kiosk supervisors. Never delete this lock to force a takeover.

## Optional USB tablet crash recovery

`--tablet-watchdog` opts into a narrow additional child: it monitors an already-installed Facebot app on exactly one already-authorized, USB-attached Android tablet. The installer uses read-only ADB inventory and rejects missing, unauthorized, multiple or wireless-only devices. It recognizes existing `adb` on PATH/the standard Android SDK path, or accepts `--adb /absolute/path/to/adb`. It does not install platform tools or change USB authorization.

The selected identifier is stored only in private `tablet-watchdog.json`, never in command arguments, the LaunchAgent, general status or logs. The child's only recovery action is to launch `org.facebot/.FaceActivity` when `pidof org.facebot` unambiguously reports no process and the same device is available. A running process means no action—even if the owner exited to another app—so it does not steal foreground focus. It does not install, change settings, unlock/wake the tablet or establish USB reverse tunnels. Voice/vision can continue using Wi-Fi; USB is the explicit recovery control path.

The watchdog persists a maximum of 3 restart attempts per 10 minutes with a 30-second minimum gap. Invalid/unwritable budget state fails closed; replacing the watchdog process does not reset this allowance. Create the private `tablet-watchdog.paused` file in the service state directory to suspend recovery; remove it to resume. For intentional force-stop/app termination, pause the watchdog or stop the service first. Stop/uninstall terminates the helper without stopping the Android app. `tablet_watchdog_active` means the monitoring process is alive, not that the tablet is connected or a recovery was observed.

A USB cable and existing authorization must remain available for this optional recovery path. Without it, Android process-crash recovery still needs separate platform-level observation; a default-home selection alone is not proof. Physical Wi-Fi verification should still include a USB-disconnected observation to exclude an accidental reverse tunnel, then reconnect USB if this watchdog is desired.

## Observe, stop and remove

```sh
python3 scripts/kiosk-service.py status
python3 scripts/kiosk-service.py stop
python3 scripts/kiosk-service.py start
python3 scripts/kiosk-service.py restart
python3 scripts/kiosk-service.py uninstall
```

`restart` waits for launchd to finish removing the old job before registering its replacement. Each stop/start phase has a 30-second deadline; transient bootstrap failures retry after 0.25 seconds, doubling to a maximum 2-second delay. Repeated `start` or `stop` commands are idempotent. A failed deadline returns an error instead of starting a competing job or retrying forever.

`status` shows the last phase, its age, current health and whether launchd has the job loaded. A stale `ready` observation is historical; require `healthy_now: true`, a fresh observation and `launchd_loaded: true`. `child_pid` identifies the voice child. Nested `admin` status identifies the owner child and its watchdog, `admin_healthy_now` checks the current owner endpoint, and `idle_sleep_protected` reports whether the owned inhibitor is alive. `stop` unloads the job so launchd does not immediately replace it; it remains installed for the next login or explicit `start`. `uninstall` unloads and removes the plist, while retaining private configuration and bounded logs for rollback. To change release/configuration, uninstall and install again with the desired arguments.

A child has 180 seconds to become ready (including model/audio prewarming). Then the watchdog checks every 5 seconds, with a 2-second HTTP timeout and three consecutive failures before replacement. Child shutdown allows 10 seconds, then kills/reaps a stuck child. Retry delay doubles from 2 to a maximum of 60 seconds; two continuous healthy minutes reset it. Thus an indefinitely broken installation retries at most once per minute after the initial attempts, rather than thrashing. Launchd separately throttles supervisor respawns to 30 seconds. A `port_conflict` checks again after 0.25 seconds, doubling up to 5 seconds while occupied. This separate schedule lets voice and owner controls recover promptly after launchd releases an old listener; it never adopts or terminates another process.

Each child watchdog has `recovery.log` plus two rotations, under 768 KiB per child (voice in the state directory, sidecars in their named subdirectories); status/configuration files are private, fixed-size records. No server output is captured. `backoff` includes a bounded classification (`child_exit`, `health_timeout`, `startup_timeout`, `tts_unresponsive`, `start_error`), not an exception, environment or response body.

## Optional isolated vision Ollama

When the existing Ollama cannot load the intended vision model, provision a separately verified compatible binary and its model files under owner control. Add `--vision-ollama /absolute/path/to/ollama` at service installation to supervise that binary's `serve` process on fixed loopback `127.0.0.1:11435`. The default dedicated model directory is `ROOT/.local/ollama-vision/models`; `--vision-models /absolute/dedicated/models` overrides it. The service does not download models, update Ollama, stop another daemon, or adopt the provisioning listener. Its owner must stop that listener before installation. Keep the shared daemon on port 11434 running for its existing clients.

The owned child receives `OLLAMA_HOST=127.0.0.1:11435`, `OLLAMA_MODELS` pointing to that directory, `OLLAMA_NUM_PARALLEL=1`, and `OLLAMA_MAX_LOADED_MODELS=1`. The voice child receives `FACEBOT_VISION_URL=http://127.0.0.1:11435/api/chat`; its text model and token configuration stay preserved, and the sidecar does not receive the pairing token. The vision child has an independent watchdog, stop/reap cycle and bounded retry schedule, so its failure does not restart voice or owner controls. It remains in launchd's managed process group for supervisor-death cleanup.

Nested `vision_ollama` status and `vision_ollama_healthy_now` report availability of `/api/tags` with HTTP 200. That check does **not** establish that a model is installed, warmed, schema-compatible or producing timely camera observations: verify the actual vision smoke test and tablet frames separately. Ordinary public setup uses the existing compatible Ollama on port 11434 and needs no sidecar flag.

## Verification and recovery drill

The deterministic suite uses temporary listeners and actual child processes; it never contacts the live kiosk or installs a LaunchAgent:

```sh
python3 -m unittest discover -s tests -p test_kiosk_service.py -v
```

It covers independent voice/admin SIGKILL recovery, hung admin without interrupting voice, scoped sleep-helper cleanup, hung HTTP with ignored SIGTERM, profile mismatch, foreign listener refusal, two competing supervisors, exponential retry limits, clean reap/lease release, log retention, token exclusion, RFC1918 validation and generated plist configuration. Plist generation tests mock launchctl; they are not evidence of OS-level restart behavior.

After authorized activation, the runtime owner records the actual release commit, fresh health and tablet connection, then performs a brief idle recovery drill:

1. Read `status`; verify the child PID belongs to this release and the tablet is idle. Kill **only that verified child PID**. Observe a new PID and fresh ready health, then a restored tablet voice/vision connection. A health response alone does not prove tablet recovery.
2. Stop and start using the service commands; verify the old child is absent, only one replacement listens, and profile/model/TTS/kiosk mode stayed unchanged.
3. At an owner-approved idle boundary, terminate only the verified supervisor PID to test launchd replacement. Verify its old child was cleaned up, one replacement is ready and the tablet reconnects. Do not use a broad `pkill` or kill an unverified saved PID.
4. Verify a real tablet response and owner mute after reconnection. Record observed timings as local production evidence. Keep synthetic hang/crash fixtures separately labeled.

A reboot/login drill and long-duration mounted run remain separate acceptance observations. The speech-worker check below covers only one class of stalled work. If speech is stuck without that evidence, preserve diagnostics for the runtime owner and use one coordinated `restart`; do not claim an automatic repair of every inference or transport failure. If a foreign process occupies the port, identify its owner and release it through that owner's controls instead of deleting the lock or repeatedly installing.


## Unresponsive speech-worker recovery

After readiness, the voice supervisor also reads authenticated, content-free `/recovery` evidence. It replaces its own voice child when a connected, unmuted session continuously demands synthesis, the same native TTS execution makes no observable progress, and both conditions persist for 90 seconds of supervisor observation. `--tts-stall-timeout SECONDS` at installation accepts 30–600 seconds; saved configurations without the field use 90. Invalid saved deadlines fail validation. The worker has its own monotonic progress age, and both that age and the supervisor observation deadline must expire. Polling adds up to roughly one health-check interval; shutdown then uses the existing 10-second terminate/kill/reap path and bounded restart backoff. Admin and vision children remain independently supervised.

Cancellation of an asyncio waiter cannot stop native inference. Therefore a cancelled old call remains visible while it executes; a new demanded request waiting behind it can trigger recovery. Execution identity, progress and demand generation reset the observation deadline. A whole-render call records each completed segment as progress; streamed calls record each actual generator advancement. Time spent playing or buffering already-produced audio is not native execution. Idle, Quiet, disconnected sessions, cancelled work with no remaining demand, and queued work without a tracked executing worker do not trigger this policy. Missing, unauthorized or malformed telemetry clears the observation rather than claiming a stall. The check does not run during initial model prewarming or for sidecars.

A native call with no observable output for longer than the configured bound is **unresponsive work**, not a proven deadlock. A legitimately slow single segment can exceed this policy; choose the conservative default unless measured local needs justify another value. This does not diagnose STT, LLM, playback, network, or general pipeline stalls, and HTTP readiness still does not prove an audible response. `/recovery` includes only counters, elapsed time and eligibility, never text, audio, model output or token values. Recovery logs use the fixed reason `tts_unresponsive`.

Focused isolated checks (no live fault injection):

```sh
.venv/bin/python -m unittest discover -s tests -p test_worker_recovery.py -v
.venv/bin/python -m unittest discover -s tests -p test_kiosk_service.py -v
```

The first reproduces a real blocked executor call plus cancelled/new demand while the app health route remains ready; other cases exercise progress and suppression. The supervisor test uses a disposable HTTP child with synthetic worker telemetry, ignored SIGTERM and capped repeated recovery, verifying that the admin child survives and no token reaches logs. These tests are not a physical kiosk recovery receipt. The runtime owner must record a separate controlled drill before claiming deployed worker recovery.
