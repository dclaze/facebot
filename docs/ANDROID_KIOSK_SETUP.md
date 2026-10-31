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

For automatic return after reboot or system relaunch, owner setup can open **Choose default Home app**. Choosing Facebot there is an explicit reversible owner action; the app does not change the default itself. Change the default back in Android Settings → Apps → Default apps → Home app. Android/OEM lock-screen and boot restrictions still apply. A regular unpinned foreground app cannot guarantee recovery after force-stop, an OS error dialog, power loss or a locked reboot. No device-owner provisioning, factory reset, alarm-based crash loop or background microphone service is installed.

Voice reconnects with 1, 2, 4, 8 and then at most 15 seconds of retry delay. Failed transport immediately clears queued audio, captions, mouth timing, special face cues and video, so stale speech is not replayed after reconnection. The face displays a brief reconnect status. The host must also be running; host auto-start is a separate setup step.

## Private developer build

Use `sh scripts/build-android.sh` with JDK 17, Android SDK 36 and Gradle 8.11.1. Optional private bootstrap belongs only in ignored `android/app/src/debug/assets/local-config.json` with `url`, `token`, optional `name` and explicit `allowPrivateLan`. `showCamera` is ignored; camera thumbnails never cover the visitor display. Legacy `src/main/assets/local-config.json` is not packaged in either variant. Debug bootstrap is a development convenience, not public pairing.

Build the signed public artifact with `python3 scripts/build-public-apk.py`. It generates/reuses a dedicated local release key in ignored `.local/android-release/`, keeping password and signing key out of Git. Back up that directory privately to issue compatible updates. Losing the key requires a new app identity or uninstall/reinstall. The script verifies signature and rejects packaged local-config assets or debuggable release manifests. Do not upload the key or private debug APK.

## Acceptance record

Run `sh scripts/test-android-kiosk.sh`, `sh scripts/test-android-captions.sh` and `sh scripts/test-playback-queue.sh` before building. Review actual idle, audio/caption, video, special face, disconnect/reconnect and owner-setup frames using the kiosk visual review skill. Record source commit, APK hash, installed build, USB-free connectivity evidence and observed return after interruption. Native unit tests establish policy/timing bounds; they do not establish physical acoustics, OS recovery or an overnight soak.
