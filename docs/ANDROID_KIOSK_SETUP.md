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

Run `sh scripts/test-android-kiosk.sh`, `sh scripts/test-android-captions.sh` and `sh scripts/test-playback-queue.sh` before building. Review actual idle, audio/caption, video, special face, disconnect/reconnect and owner-setup frames using the kiosk visual review skill. Record source commit, APK hash, installed build, USB-free connectivity evidence and observed return after interruption. Native unit tests establish policy/timing bounds; they do not establish physical acoustics, OS recovery or an overnight soak.

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
