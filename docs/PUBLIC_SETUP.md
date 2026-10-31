# Public Android kiosk setup

This release uses an **Android tablet plus an Apple Silicon Mac host**. The APK is the face, microphone, camera and speaker client; it does not contain the local speech/vision models or replace the Mac. Keep both devices powered and the Mac awake throughout an event. This is an experimental self-hosted release, not a claim that every device has passed 12-hour or acoustic-latency acceptance.

On the tested Lenovo TB-J606F with Android 11, the compatibility profile avoids a vendor echo-cancellation path associated with observed audio-service crashes. Speak after the face finishes, or use **Quiet** to stop output and **Resume** to allow it again. Quiet persists through app restart; controls stay above video without covering its title. This profile does not support spoken interruption during playback. See [Android kiosk setup](ANDROID_KIOSK_SETUP.md) for the precise scope and limits. Experimental software echo cancellation is not included in the public APK.

The bundled packs are free. There is no checkout, subscription or paid inference service in this setup. The personal guest performance is separately supplied local media and is not included. Project code, model weights, voices and sound recordings retain their own licenses; see the repository license and each content package's credits before redistribution.

## Prepare the Mac

Use a persistent source checkout on an Apple Silicon Mac with Python 3.12 available, or install `uv` through your chosen method from its [official installation guide](https://docs.astral.sh/uv/getting-started/installation/). Install and open local Ollama yourself; its [macOS instructions](https://docs.ollama.com/macos) require macOS 14 or newer. Ensure `uv` (or `python3.12`) and `ollama` are on your terminal PATH; the script also recognizes Ollama in the standard Applications app bundle. Setup does not install Homebrew, change login settings, upgrade system tools or launch a shared inference service.

Use a current Ollama release that supports `qwen3-vl:2b-instruct`; older releases can reject this model. The setup's actual model pull and synthetic request check compatibility. Do not substitute `qwen3-vl:2b`: that tag can select a thinking model which exhausts the bounded label response before producing content. The runtime requires nonempty JSON content and no thinking output. Setup does not upgrade an existing Ollama installation.

Vision defaults to `http://127.0.0.1:11434/api/chat`. An independently managed local daemon can use `FACEBOT_VISION_URL=http://127.0.0.1:11435/api/chat`; set the same value for setup and the kiosk service. Only literal `127.0.0.1` or `[::1]`, a valid explicit port, and the `/api/chat` path are accepted. The selected daemon must already have the instruction model available. A successful blank-image smoke check establishes protocol and freshness only; live scene recognition still needs separate verification.

A network connection is needed for the first dependency/model downloads. Allow sufficient disk space for the Python environment and text, vision, Whisper and Kokoro models. No cloud API key is needed. Model downloads and local computation are not subscription charges.

From the source directory:

```sh
python3 scripts/setup-kiosk.py --check
python3 scripts/setup-kiosk.py
```

`--check` writes nothing and lists missing prerequisites. Setup creates a local `.venv` using Python 3.12, installs `requirements.lock`, downloads the official Qwen tokenizer pinned by `scripts/setup-tokenizer.py`, pulls `qwen2.5:1.5b` and `qwen3-vl:2b-instruct` through local Ollama, and checks a synthetic blank JPEG through the selected local vision endpoint (default `127.0.0.1:11434`) before preparing Kokoro/Whisper. The vision check permits two attempts because a cold model load can exceed the six-second frame freshness limit; both attempts are recorded in `.local/setup/vision-smoke.json`. A timely schema-valid reply verifies connectivity and runtime acceptance, not recognition quality. It synthesizes only authored setup text and transcribes silence; no microphone/camera capture occurs. Prepared speech uses the effective owner speech rate and active character voice, with cache files under `.local/prepared-audio`. The synthetic prewarm receipt is `.local/setup/kiosk-prewarm.json`.

The Python lock and tokenizer revision are pinned. Ollama model tags and the upstream Kokoro/Whisper repositories can change, so this setup is reproducible as a procedure, **not a promise of byte-identical upstream weights forever**. Retain the setup logs/model versions when investigating differences. Existing model caches are reused. `--skip-models` installs Python dependencies and the tokenizer but does not establish offline readiness.

A new private `.local/pairing-token` is generated only when absent, with owner-only permissions. An existing valid token is preserved; an invalid token causes setup to stop rather than silently unpair devices. Never publish `.local`, a token, a preconfigured development APK, or your private recordings. Setup does not start Facebot, install a LaunchAgent, install an APK or change the router.


Speech recognition uses `mlx-community/whisper-small.en-mlx` for both setup and live visitor turns. It costs more memory and inference time than `tiny.en`; isolated excerpts captured by the actual tablet microphone recognized greeting, joke and scare requests correctly with `small.en`, where smaller models misheard some phrases. Those samples do not establish general accuracy or end-to-end latency. No keyword prompt or relaxed scare trigger is used. Setup downloads the same model and records a synthetic silence warmup in `.local/setup/stt-warmup.json`. Each service process warms it again before accepting visitors, with a 60-second readiness deadline; errors or timeout fail startup. Native inference already running in a worker cannot be cancelled by that deadline. `/health` reports the model and synthetic warmup timing, not microphone accuracy.

## Connect the tablet

Obtain the signed public release APK and compare its SHA256 against the release's separately supplied checksum. Install it using Android's owner-approved package installer. The public APK must have no `assets/local-config.json`; it prompts the owner for connection information. Its `org.facebot` application/signing key may differ from a development installation, so preserve needed settings before an owner-managed replacement.

For a trusted private Wi-Fi network, find the Mac's current RFC1918 IPv4 address (for example 192.168.1.50). Reserve that address in the router if available. The Android tablet and Mac must be reachable on the same network; guest-network client isolation can prevent this. Do not forward the service port to the internet.

After setup, use [the recovery service runbook](KIOSK_RECOVERY.md) to install the optional automatic restart service. Substitute your actual release paths and address:

```sh
python3 scripts/kiosk-service.py install \
  --root /absolute/path/to/facebot \
  --python /absolute/path/to/facebot/.venv/bin/python \
  --token-file /absolute/path/to/facebot/.local/pairing-token \
  --profile halloween --model qwen2.5:1.5b --tts kokoro \
  --host 192.168.1.50 --trusted-lan
python3 scripts/kiosk-service.py status
```

The service also opens owner settings at `http://192.168.1.50:8766/` and the free skill shop at `http://192.168.1.50:8766/store`. By default only the Mac itself may access them. Add `--owner-client YOUR_OWNER_DEVICE_PRIVATE_IP` during installation to authorize a specific owner phone/tablet; this does not enable arbitrary LAN visitors. Owner controls and voice recover independently. `--no-admin` opts out; a separate manually running owner server must be stopped by its owner before adopting supervision.

Public setup normally uses an existing compatible Ollama on port 11434. If another application's older shared daemon must stay untouched, an owner can separately provision a compatible binary and vision models, then add `--vision-ollama /absolute/path/to/ollama` to installation. This opt-in child uses loopback port 11435 and dedicated `ROOT/.local/ollama-vision/models` storage (`--vision-models` overrides the directory). Stop the owner-run provisioning listener first. The service handles subsequent process recovery but does not install or warm its model. See [isolated vision operation and evidence limits](KIOSK_RECOVERY.md#optional-isolated-vision-ollama).

While the service runs it prevents idle Mac sleep with a scoped `caffeinate` child. It cannot prevent lid closure, explicit sleep, shutdown or power loss. `--no-sleep-protection` opts out; stopping/uninstalling the service removes the sleep assertion. Existing configurations require reinstalling to add these new defaults.

This service persists kiosk mode across restarts. A user LaunchAgent starts **after macOS login**, not before FileVault/login. First startup/prewarm can take time. Require fresh `healthy_now: true` before pairing; then verify the tablet separately. Stop any previous server through its owner before installing: the service refuses to kill an existing listener.

After readiness, the service also checks demanded native TTS work for 90 seconds without observable progress. Quiet, disconnected and idle sessions are excluded. This bounded policy covers an unresponsive speech worker, including a cancelled call blocking a later request; it does not detect every inference or audio failure. See [the evidence and configurable deadline](KIOSK_RECOVERY.md#unresponsive-speech-worker-recovery).

If you want the Mac to recover an actual Android process crash, `--tablet-watchdog` is an additional opt-in install flag. It requires an already-authorized USB debugging connection to exactly one tablet and an existing Android SDK `adb`; it neither installs an APK nor changes the device's settings. Its recovery action is limited to launching a missing Facebot process, with a persistent rate limit. A running app is left alone when the owner switches away. See [the watchdog controls and pause procedure](KIOSK_RECOVERY.md#optional-usb-tablet-crash-recovery). Basic Wi-Fi operation does not require this optional USB control path.

In the tablet's owner connection screen, use `ws://192.168.1.50:8765/voice` with the Mac's private pairing token and explicitly enable the trusted-LAN option. Trusted LAN is unencrypted and appropriate only on an owner-controlled private network. For other networks use a properly trusted TLS setup rather than weakening hostname/certificate validation. Do not send tokens through public chat, pastebins or release issues.

Allow microphone and camera access when Android requests them, then check a real spoken request and owner mute/exit. Establish Wi-Fi transport independently: either disconnect USB, or verify no ADB reverse mapping exists and the tablet's configured voice endpoint is the Mac's explicit RFC1918 IPv4 address. USB can remain connected for power and the optional recovery watchdog. A loopback endpoint or an unplugged cable alone does not establish successful Wi-Fi operation. Confirm the tablet reconnects after an authorized server restart and that both voice and vision connect. Do not assume an HTTP health response proves audible speech.

The service is optional: `scripts/kiosk-service.py run` is its foreground supervisor command **after** an installation has created private configuration. For a first-time manual run without installing a service, use the following from the source checkout; the token is read in-process and never placed in command arguments:

```sh
.venv/bin/python - <<'PY'
import os, runpy, sys
from pathlib import Path
os.environ.update(FACEBOT_TOKEN=Path('.local/pairing-token').read_text().strip(),
                  FACEBOT_PROFILE='halloween', FACEBOT_LLM='qwen2.5:1.5b',
                  FACEBOT_TTS='kokoro', FACEBOT_KIOSK_MODE='1')
sys.argv=['server.app', '--host', '192.168.1.50', '--allow-private-lan']
runpy.run_module('server.app', run_name='__main__')
PY
```

For the manual foreground voice command above, owner controls are a separate optional foreground process:

```sh
FACEBOT_PROFILE=halloween .venv/bin/python -m server.admin --host 192.168.1.50
```

Add `--allow-client OWNER_DEVICE_PRIVATE_IP` only for an explicitly authorized owner device. Prefer the supervised installation for automatic recovery and scoped sleep protection.

## Generate an honest readiness report

For a read-only endurance observation of both voice connectivity and camera freshness:

```sh
.venv/bin/python scripts/benchmark-device.py \
  --base-url http://192.168.1.50:8765 --token-file .local/pairing-token \
  --output .local/kiosk-readiness/voice-vision-soak.jsonl \
  --vision --soak-seconds 43200 --interval 10
```

Use a new output filename for each run. This does not play speech or restart anything. `--vision` adds only numeric counters and freshness; it never stores camera labels, images, or visitor text. Stale/missing vision or a nonzero reported error counter prevents the combined benchmark from passing. Error counters can include failures before the observation. Ten-second samples cannot prove uninterrupted uptime between samples, scene recognition quality, or audible response timing. Without `--vision`, the benchmark covers voice health only. A full duration must actually elapse; requesting twelve hours is not evidence that twelve hours passed.

The component benchmark `scripts/benchmark-kiosk.py` exercises prepared processors and can prewarm authored audio. Its cached/replay timings are not generated audible latency.

The aggregate runner is `scripts/certify-kiosk.py`:

```sh
python3 scripts/certify-kiosk.py --check --output .local/kiosk-readiness/plan.json
python3 scripts/certify-kiosk.py --quick --artifact /path/to/public.apk
python3 scripts/certify-kiosk.py --artifact /path/to/public.apk \
  --expected-sha256 /path/to/public.apk=LOWERCASE_SHA256_FROM_RELEASE \
  --receipt /private/evidence/device.json --receipt /private/evidence/wifi.json \
  --receipt /private/evidence/recovery.json --receipt /private/evidence/visual.json
```

The runner does not install apps, start servers, exercise the live device, pull models or kill live processes. Full mode runs focused Python suites, isolated native Java tests (JDK 17 required) and deterministic processor replay. Native builds use a temporary directory, not the live asset directory. It writes JSON and a matching Markdown report; `--check` writes a plan/report but executes no suites, while `--quick` intentionally leaves extra/replay/native checks `not_run`. Failed commands are listed for focused local reruns; command output is not copied into a public report.

Exit 0 means every listed internal criterion passed; exit 1 means a check failed; exit 2 means evidence is incomplete/unverified. Missing tests, missing APKs, dirty/unknown source, malformed receipts and missing physical observations never silently pass. The report is **internal readiness**, not external certification. The full report remains `not_fully_verified` until 12 hours of actual endurance and measured generated audible latency are supplied, even when a narrower supervised candy-tray trial has passed.

Physical evidence receipts are deliberately separate from test/replay files. Supply one authoritative receipt per kind, bound to the exact source commit. The runner verifies the receipt schema, source, timestamp and artifact hashes; a human must inspect the actual screenshots/audio/observations before asserting their results. Never make a fixture or simulation into a physical receipt.

```json
{
  "schema_version": 1,
  "kind": "wifi",
  "evidence_level": "physical_observation",
  "source_commit": "EXACT_40_CHARACTER_TESTED_COMMIT",
  "measured_at": "2026-10-31T02:30:00+00:00",
  "scope": "Actual mounted Android and Mac on the intended private Wi-Fi",
  "artifacts": [{"path": "wifi-observation.json", "sha256": "ACTUAL_64_CHARACTER_SHA256"}],
  "metrics": {"usb_reverse_absent": true, "voice_endpoint_host": "192.168.1.50", "tablet_reconnected": true, "voice_and_vision_connected": true}
}
```

Relative artifact paths resolve against the receipt directory. Do not copy the example's timestamp/placeholders as observed evidence. Required metrics:

| Receipt kind | Required observations |
| --- | --- |
| `device` | `voice_and_vision_connected`, `audible_response_verified`, `owner_mute_verified`, `owner_exit_verified`, all true |
| `wifi` | `tablet_reconnected` and `voice_and_vision_connected`, both true; additionally either `usb_disconnected` true, or `usb_reverse_absent` true plus `voice_endpoint_host` containing the actual plain RFC1918 IPv4 address. Any supplied endpoint must be RFC1918, even for an unplugged test. |
| `recovery` | `child_restart_verified`, `supervisor_restart_verified`, `tablet_reconnected`, `settings_preserved`, all true |
| `visual` | `desktop_reviewed`, `mobile_reviewed`, `tablet_reviewed`, `readable`, `no_clipping`, `controls_verified`, all true |
| `endurance` | `duration_hours` at least 12 and integer `unexpected_failures` zero |
| `generated_latency` | `timing_basis` exactly `utterance_end_to_audible_generated_speech`; `cached_responses` false; integer `samples` at least 20; measured `median_ms` ≤200 and `p95_ms` ≤500 |

The 20-sample minimum is the runner's reporting protocol; it is not a claim of statistical certification. Native AudioTrack playback-head acknowledgement, synthesized PCM timing and cached responses do not satisfy the generated acoustic measurement. A public source ZIP may include a `SOURCE_COMMIT` file containing the exact lowercase 40-character release commit. The runner labels this `archive_declaration`, binds supplied receipts to that declared commit and records its hash, while leaving source integrity unverified: the metadata is not a signature or proof that all extracted files match. Compare the complete source archive against the independently published release SHA256, retain that artifact provenance, and do not substitute an enclosing unrelated Git repository. A clean actual checkout is the verified Git path. See [conversation timing](CONVERSATION_TIMING.md) and [recovery verification](KIOSK_RECOVERY.md) for measurement boundaries.

### Voice priority while vision is running

New camera inference is deferred during visitor speech, active transcription,
response generation and playback, with a 300 ms quiet grace. Each deferred frame
is acknowledged and discarded rather than queued. Continuous deferral is capped
at three seconds (half the six-second vision freshness window). When an observation
already exists, refresh is admitted earlier if waiting for the next native capture
(1.5 seconds), the last measured inference duration, and 200 ms of headroom would
reach its expiry. This accounts for time already spent observing and processing
the scene; a fresh deferral timer does not grant an old observation more lifetime.
A refresh can overlap a long voice turn. An already submitted Ollama request
cannot be preempted, and slower inference or capture delays can still produce a
stale interval. Camera timestamps and the six-second expiry remain unchanged;
stale labels stay excluded even when the scheduling estimate is exceeded.
Owner vision diagnostics expose deferred-frame and priority-refresh counts.
These are scheduling receipts, not evidence of lower acoustic or recognition latency.
