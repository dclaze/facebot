# Facebot Android alpha setup

Facebot 0.2 alpha is a native Android face connected to a separate Facebot host. It is not a standalone offline assistant. The current host setup targets Apple Silicon macOS, local speech recognition/synthesis and Ollama; install the repository's host dependencies and start the server before pairing. Android 8 or newer, a front camera and microphone are recommended. Keep the tablet powered beside the candy tray.

## Public install and pairing

1. Download the public release APK and verify the published SHA-256. Allow installation from your browser/file manager when Android asks. The alpha is sideloaded, not distributed through Google Play.
2. Launch Facebot and allow microphone/camera access. Put tablet and host on the same trusted Wi-Fi, preferably a strong nearby access point without guest-client isolation. The host must listen on the LAN interface and its firewall must permit the selected port. Reserve the host LAN address in your router to keep pairing stable.
3. Hold the upper-left corner of the face for five seconds. On a paired tablet, Android device PIN/password confirmation protects owner setup. Set an Android screen lock before leaving the tablet unattended. The initial unpaired setup is accessible without a PIN.
4. Enter `wss://your-host/voice` and the host's pairing token. For a trusted private network without TLS, explicitly select **Allow unencrypted private LAN** and enter `ws://192.168.1.20:8765/voice` with your actual host address. This sends token, audio and sampled camera images without encryption on that network. Use TLS for any remote/public endpoint. Hostnames and public addresses are rejected for unencrypted LAN mode.
5. Save and connect. The visitor sees the character and **Say hello** when the audio connection is ready. Diagnostics are off by default. Unplug USB and verify real speech and reply over Wi-Fi; USB reverse success is not Wi-Fi acceptance.

The APK contains no pairing token, private endpoint, personal media or developer config. Pairing is stored in Android app-private preferences with backup disabled. Public releases use a dedicated release signing key, retained privately by the publisher. The private debug build uses a different certificate; switching between the two package signatures requires uninstalling the old app, which removes its local pairing. Do not uninstall a working kiosk just to test a public build; verify release independently first.

## Touch resistance and restart

The face consumes ordinary touches and Back, stays awake while foregrounded, and restores immersive display after focus returns. Owner setup offers Android's optional **Pin Facebot to screen** prompt. Configure Android's own screen-pinning and unlock behavior first. Pinning is not managed kiosk enrollment: system gestures, power, permissions, crashes and OEM behavior remain under Android control.

For automatic return after reboot or system relaunch, owner setup can open **Choose default Home app**. Choosing Facebot there is an explicit reversible owner action; the app does not change the default itself. Change the default back in Android Settings → Apps → Default apps → Home app. Android/OEM lock-screen and boot restrictions still apply. In the coordinated Lenovo test, an intentional app crash did not return Facebot within 22 seconds even with Facebot selected as Home; the prior launcher remained visible and the owner relaunched the app. Default Home is therefore not an observed crash-recovery guarantee on this tablet. A regular unpinned foreground app cannot guarantee recovery after force-stop, an OS error dialog, power loss or a locked reboot. No device-owner provisioning, factory reset, alarm-based crash loop or background microphone service is installed.

Voice reconnects with 1, 2, 4 and then at most 5 seconds of retry delay. Failed transport immediately clears queued audio, captions, mouth timing, special face cues and video, so stale speech is not replayed after reconnection. The face displays a brief reconnect status. The host must also be running; host auto-start is a separate setup step.

## Private developer build

Use `sh scripts/build-android.sh` with JDK 17, Android SDK 36 and Gradle 8.11.1. Optional private bootstrap belongs only in ignored `android/app/src/debug/assets/local-config.json` with `url`, `token`, optional `name` and explicit `allowPrivateLan`. `showCamera` is ignored; camera thumbnails never cover the visitor display. Legacy `src/main/assets/local-config.json` is not packaged in either variant. Debug bootstrap is a development convenience, not public pairing.

Build the signed public artifact with `python3 scripts/build-public-apk.py`. It generates/reuses a dedicated local release key in ignored `.local/android-release/`, keeping password and signing key out of Git. Back up that directory privately to issue compatible updates. Losing the key requires a new app identity or uninstall/reinstall. The script verifies signature and rejects packaged local-config assets or debuggable release manifests. Do not upload the key or private debug APK.

## Acceptance record

Run `sh scripts/test-android-kiosk.sh`, `sh scripts/test-android-captions.sh` and `sh scripts/test-playback-queue.sh` before building. Review actual idle, audio/caption, video, special face, disconnect/reconnect and owner-setup frames using the kiosk visual review skill. Record source commit, APK hash, installed build, independently verified Wi-Fi transport and observed return after interruption. USB may remain for power/control when there is no ADB reverse mapping and voice uses the Mac's explicit private LAN address. Native unit tests establish policy/timing bounds; they do not establish physical acoustics, OS recovery or an overnight soak.

A diagnostic playback probe uses a UUID, epoch and PCM offset. The tablet acknowledges once only after the observed AudioTrack playback head passes that offset; interruption, disconnect and a 15-second timeout discard the probe. Dispatch-to-receipt timing includes outbound Wi-Fi, native playback progress, polling and return Wi-Fi. It does not measure acoustic output, VAD or speech recognition. No speech text or media content is returned.

When the host sends its output-mute state, the native face displays **Quiet mode** until an explicit resume. Normal playback-ready updates cannot overwrite that state. Microphone capture remains active to recognize the resume command; Quiet mode is not a microphone privacy switch. Reconnection displays its connection status until the host supplies the current persisted state.

## Owner-invoked device benchmark

`scripts/benchmark-device.py` checks an already attached tablet through its host. It never installs, wakes, unlocks, changes mute, edits pairing, or runs ADB. The default performs only authenticated health/connection reads. Use a new output path on each run; JSONL files are created with owner-only permissions and never overwritten. The script reads the token from a file and records only allowlisted booleans, scenario IDs, probe IDs and numeric timings, never raw diagnostics or visitor text.

```sh
python3 scripts/benchmark-device.py --base-url http://127.0.0.1:8765 \
  --token-file .local/pairing-token --output .local/device-snapshot.jsonl
python3 scripts/benchmark-device.py --base-url http://127.0.0.1:8765 \
  --token-file .local/pairing-token --output .local/device-rehearsal.jsonl \
  --rehearse --scenarios welcome,candy,joke,scare,goodbye --repeats 2
python3 scripts/benchmark-device.py --base-url http://127.0.0.1:8765 \
  --token-file .local/pairing-token --output .local/device-soak.jsonl \
  --soak-seconds 3600 --interval 5
```

`--rehearse` explicitly authorizes synthetic spoken playback of the listed scenarios. The runner waits for an unmuted idle face, submits at most 30 bounded rehearsals, and matches receipts by the returned UUID. Use adjacent `laugh-invite,laugh-turn` for the game; repeated games may hit the deliberate cooldown. Private performances require their separately installed assets. It never resumes a muted face automatically. Failed, cancelled, busy and expired attempts stay visible in the report instead of being excluded from counts.

The last JSONL record and console output contain the summary. Exit 0 means all observed health samples and requested probes passed; exit 1 means an observed gap, failed rehearsal or interrupted run. Timing is host dispatch to actual native playback-head acknowledgement, including return network/polling delay, and excludes recognition and acoustic output. Independently remove the USB transport path and establish tablet Wi-Fi before describing any result as Wi-Fi. Health is point sampling: the report includes actual elapsed/soak durations and maximum sample gap, does not prove continuous uptime, and never turns a short run into a 12-hour acceptance claim. `--soak-seconds` is capped at 43200; request, idle and receipt waits are bounded.

## Optional read-only resource observation

The network benchmark does not collect power, thermal or memory evidence. Run
this separate observer only when the owner has already authorized one tablet in
ADB; it does not connect, pair, install, wake, change settings or restart the app:

```sh
python3 scripts/observe-android-resources.py --observe-adb \
  --output .local/resources-overnight.jsonl --duration-seconds 43200
```

Use `--adb /absolute/path/to/adb` if needed. The explicit `--observe-adb` flag is
required. More than one listed device fails without printing identifiers; a
replacement device ends observation rather than silently switching targets.
The selected identity stays in memory and the child environment, never in command
arguments or receipts. A disconnected or unauthorized device produces unavailable
samples without reconnecting it.

Samples run on a fixed 60-second schedule for at most 12 hours, using five-second
command timeouts also bounded by the remaining duration. Commands read only the
`org.facebot` PID, package memory, battery and thermal service. Receipts contain
process-presence/PID-change counts (not PIDs), PSS in KiB, plugged state, battery
level/temperature and the platform thermal status code. Unsupported or malformed
fields remain null with fixed command-status codes; raw dumps and visitor data
are never saved. Each run requires a new JSONL file created with mode 0600.

The final summary records sample count, observed PID changes/absence/unknowns,
maximum sample gap and resource extrema. Exit 0 means the requested observation
period ended, not that the device passed a health or safety criterion; exit 1
means interrupted or aborted observation. These point samples cannot prove
continuous uptime, absence of memory leaks, thermal safety or uninterrupted voice.
They complement the host network/freshness receipts and physical checks; USB
observation itself does not establish that app traffic uses Wi-Fi.

## Optional USB process watchdog

For a powered tablet that stays physically attached to the host, the owner may explicitly enable the host service's `--tablet-watchdog` option. Voice can continue over Wi-Fi: the watchdog never creates USB reverse ports. This compensates for the observed Lenovo Home/crash limitation only when the app process is absent; it does not guarantee recovery from a hung process, an error dialog, a locked screen or disconnected USB.

The service runs `python3 scripts/tablet-watchdog.py --config /absolute/private/tablet-watchdog.json`. Private configuration selects exactly one owner-authorized USB device and contains `adb` (absolute executable path), `serial`, `pause_file` (absolute), optional `state_file` (absolute), `enabled` (default false), `interval_s` (default 5, minimum 2) and `max_restarts_per_10min` (default 3, maximum 5). Keep this config private; identifiers are passed to ADB only through `ANDROID_SERIAL`, never logged or placed in command arguments.

With `enabled:false` the script only observes. With explicit `enabled:true`, a confirmed connected device and unambiguous absent `org.facebot` process permit starting `org.facebot/.FaceActivity`. A running process is left alone even if the owner has chosen another foreground app. It never installs, changes default Home/settings, unlocks, wakes, manages enrollment or bypasses Android launch restrictions. A successful launch command is recorded as **restart requested**, with recovery only inferred from a later process-present observation; neither proves visible UI or audio.

Create the configured pause file before intentionally force-stopping Facebot; leave it in place to suspend checks and restarts. Removing it resumes observation. Stopping the host service also terminates the watchdog. Attempts have a 30-second minimum gap and a persisted ten-minute budget that survives watchdog restarts; invalid or future-dated state fails closed. An exclusive state-file lock prevents duplicate watchers. Device absence or ambiguous ADB errors never trigger a launch. Logs contain only fixed state names and UTC timestamps.

TalkBack can focus the face to hear its character and current status. Meaningful status/name changes update a polite live region; gaze, animation frames and repeated ready ticks do not re-announce it. The face exposes an **Owner setup** accessibility action that uses the same Android device credential check as the five-second corner gesture, without requiring that gesture. Quiet mode explicitly means speech output is paused while the microphone remains available for resume.

### Lenovo Android 11 audio compatibility

On Lenovo TB-J606F running Android 11, Facebot uses a narrow half-duplex compatibility profile. This tablet's vendor audio service was observed crashing in `AcousticEchoCancelerEffect::command`, followed by audio-server/SystemUI failures; this was not a Facebot ANR. The exact command that triggered the vendor fault is unconfirmed. Its firmware automatically attaches AEC to the voice-communication recording source, so skipping only the explicit AEC API would still request the affected effect.

The profile uses voice-recognition capture, makes no explicit AEC request, leaves communication-mode/speaker routing alone, and plays through the media audio stream. Adjust the tablet's **media volume** for the face. While output is queued or still playing, and for a 600 ms echo/capture-buffer tail, captured PCM is replaced with silence before transmission. Capture and connection timing continue, but speech interruption is unavailable during that interval: wait until the face finishes before saying stop, resume or another request. The affected-profile screen includes accessible **Quiet** and **Resume** buttons above the face, including during video performances. Quiet immediately holds local output and asynchronously asks the authenticated host to persist quiet mode. A failed request displays **Paused here · host not confirmed** and keeps local output held; retry Quiet or tap Resume. Resume releases the local hold only after a successful host response. Spoken stop/resume remains available while idle, and a host quiet-to-resume transition also releases the hold. Local Quiet persists through process restart and reconnection. The main prompt reflects the local hold, and video is fitted below the measured control area so its title remains readable. These visitor controls do not expose owner pairing settings. Other devices retain the existing full-duplex AEC path. The tail is a conservative workaround, not measured acoustic latency or software echo cancellation.

This is an app-scoped mitigation, not a repair or disablement of the vendor audio/Dolby services. A driver or SystemUI crash can still hide the app behind the lock screen, which the optional process watchdog cannot unlock. Repeated actual playback, reconnection, and post-playback speech checks on the affected tablet are required before claiming the mitigation resolved the observed failure. Android's source-specific preprocessing behavior is documented in [Configure preprocessing effects](https://source.android.com/docs/core/audio/implement-pre-processing).

The affected Lenovo profile identifies its raw capture path with
`X-Facebot-Capture-Profile: lenovo-j606f-raw-v1`. The host applies a fixed 4x gain
only to Silero's speech-confidence analysis buffer for that exact profile;
recorded/transmitted microphone PCM, ASR input, volume threshold and onset/stop
durations remain unchanged. Other profiles use 1x. The raw-profile confidence
threshold and its evidence are described below.
Controlled microphone replay recovered short low-amplitude greetings that the
unchanged detector missed, while the tested quiet/noise controls stayed quiet.
This is a bounded replay result, not a general noise-accuracy guarantee. Owner
`/diagnostics` exposes the effective VAD profile and parameters for verification.

The authenticated VAD report also contains content-free activity counters: input
frames/samples, analyzed frames, latest and maximum confidence/volume, qualifying
candidate frames, stable speech starts/stops, and monotonic ages. Compare counters
before and after a controlled phrase: candidates without a start point to detector
state/timing; starts without an ASR utterance point downstream. These counters
retain no PCM or text, reset on voice reconnect, and do not prove acoustic capture
or recognition. A replay that detects a phrase does not establish live acceptance.

The raw Lenovo profile uses confidence 0.5 with the same original-volume 0.6,
100ms onset and 450ms endpoint gates. Generic and processed capture retain 0.7.
This follows a live failed short greeting with valid volume but no qualifying
confidence frames, reproduced under varied preceding PCM histories. The narrow
change detected 39/39 history variants and 144/144 additional controlled speech
replays across eight sample alignments; 72 recorded/synthetic quiet and noise
replays remained quiet. These are local replay results, not a substitute for
live microphone acceptance or a guarantee for other voices and environments.

## Native thermal workload adaptation

On Android 29 and newer, the activity observes `PowerManager` thermal status while
started and unregisters on stop. Severe status 3 limits MLKit attention analysis
to ten frames per second; critical status 4 or higher limits it to five. Valid
incoming frames still reach the independent vision snapshot sampler before the
analysis decision, and skipped proxies close immediately. No camera frames are
held or queued by the policy. Status 0–2 preserves normal analysis cadence.

Severe/critical status requests at least 33/67ms between scheduled face redraws,
respectively, with display-vsync alignment potentially lowering the actual rate.
Gaze interpolation uses elapsed time so slower drawing does not multiply gaze
lag. Static halo shaders and the title typeface are cached. Audio transport,
playback clocks and voice behavior are unchanged. Thermal redraw callbacks are
removed on pause/detach and resume seeds a fresh redraw.

API 26–28 retain baseline behavior because the supported thermal API begins at 29.
If monitoring becomes unavailable, the last known policy is retained; these
controls do not change system thermal overrides or device settings. They reduce
app-requested work, but camera preview/ISP work remains and temperature reduction
has not been established by unit tests. Compare actual rendering, attention,
voice/vision freshness and resource observations before claiming improvement.
Run `sh scripts/test-thermal-workload.sh` for synthetic transition, timing and
frame-ownership checks; physical lifecycle/API availability still needs device
verification.

### Manufacturer floating controls

Some Lenovo tablets expose **Smart Navigation** in Android Settings. Its floating edge handle can remain visible above an immersive app. If present on your tablet, turn that switch off for the kiosk and record its previous state so you can restore it afterward. This is separate from Android system navigation, screen pinning and owner authentication; turning off the handle does not lock the device. The tested tablet resumed voice and fresh vision after returning from Settings. Other manufacturers and Android versions may use different controls.
