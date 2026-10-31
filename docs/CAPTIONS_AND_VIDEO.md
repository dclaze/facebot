# Native captions and performance video

Android captions are on by default. Spoken text appears in bold white in the bottom quarter of the screen, below the mouth. The normal server path creates pages of at most five words and 30 characters. The renderer measures the whole page, wraps within two lines, and fits narrow/landscape layouts without ellipses. Existing name/status text is hidden while captions show.

Caption metadata is an optional `captions: [[start, end, text], ...]` field on existing `visemes` messages. Both offsets and intervals are 24 kHz PCM sample positions. The serializer supplies the playback epoch and audio offset. Older clients ignore the extra field. Timelines discard old epochs, clear on interruption/disconnection, and expire text at its audio end. Android requires actual written audio before showing text.

Kokoro captions use actual synthesized segment graphemes and available word timestamps. Proportional timing is the explicit fallback without alignment. The prepared Robin package accepts a private captions.json sidecar only when audio_sha256 matches the exact WAV. The original 28.830083-second skit sidecar uses its four verified edit boundaries, with proportional phrase timing within each recording. Replacing the WAV requires rebinding/remapping this sidecar.

## Android video

Android advertises `X-Facebot-Capabilities: performance_video_v1` on its authenticated `/voice` WebSocket. The server matches this exact comma-separated capability token and sends video events only to capable clients. iOS video support is paused.

A performance_video event contains id robin-williams, immutable path /media/robin-williams/<sha256>.mp4, epoch, future song-start offset, and duration_ms. The native helper downloads from the paired voice origin with the existing Bearer token, refuses redirects, verifies SHA256, and bounds media to 64 MiB / 180 seconds. MediaPlayer prepares independently of the hidden TextureView, stays muted, and never requests audio focus. Existing native PCM remains the sole audible track.

At the sample offset, the helper shows video, seeks to current PCM position, and corrects drift over 150 ms at most every 200 ms. A PCM stall pauses video. Interruption, disconnection, backgrounding, and the audio endpoint restore the face. A drained tail within 25 ms of the rounded millisecond endpoint also clears video, preventing a final frame from waiting for nonexistent samples. Invalid/download/decoder errors leave audio and face/captions usable. Native captions are suppressed while video shows burned-in lyrics.

## Verification

- `sh scripts/test-android-captions.sh`: portable Java caption lifecycle, protocol/path bounds, and video clock tests, including the actual 80.0135-second audio / 80014-ms metadata rounding case.
- `.venv/bin/python -m unittest tests.test_captions tests.test_protocol tests.test_tts_stream tests.test_settings tests.test_expressive_tts`: captions plus affected speech compatibility.
- `sh scripts/build-android.sh`: builds Android APK.
- Debug APK only: send `--ez renderCaptionPreview true` to FaceActivity via am start. Eight offscreen PNGs are written under app-private files/caption-600x1000-0.png through index 3 and corresponding 1000x600 images. They use the actual renderer, a synthetic open-mouth face, and short, long, Unicode, and wide-character phrases. They do not inject live captions or speech. Pull with `adb exec-out run-as org.facebot cat files/<name>`.
- FacebotVideo logcat messages identify checksum verification, preparation, visible playback sample, and clearing without logging authentication.

Parent verified one physical Android install of APK42e863f6fa028dca33bf5655d7429787c05b03f9ff00d7740e45956717d7cc08 on the authorized Android tablet and reviewed portrait/landscape offscreen images from the actual native renderer. The tablet showed Listening with active vision. The combined live speech-caption and song/video event still requires the server owner's coordinated playback check; actual tablet video is not yet verified. Completed iOS caption source/build evidence is retained; no further iOS work or deployment until testing resumes.
