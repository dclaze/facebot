# iOS implementation and remaining acceptance

The native iOS17+ client compiles with Swift6 strict concurrency. It captures
microphone audio continuously with AVAudioEngine voice processing, receives local
Mac PCM replies, flushes stale audio on interruption and reads timed viseme cues
from the player sample clock. These are implementation facts, not physical AEC,
barge-in or acoustic-sync acceptance.

Camera attention uses AVFoundation and Apple Vision locally. Group gaze is not
active-speaker localization. Face-count metadata saturates at32 with overflow;
no complete crowd-headcount guarantee. Observations expire; gaze returns neutral.

Scene labeling uses the same paired Mac `/vision` service as Android. Samples are
JPEGs at most448 pixels on the long edge and256KB, with capture age in a four-byte
big-endian prefix. Capture/encode is separate from audio. Only one image is pending
across capture and transport; no backlog, maximum one submission per1.5seconds.
Stale images are dropped, a missing ACK closes only the vision socket after25s,
and the next eligible image reconnects. Images are transient in memory, with no
camera recording or file export. WSS is required except device-local loopback;
there is no certificate bypass. Physical Wi-Fi pairing remains unverified.

The unpaired simulator does not request camera access or send images. Its
`--mouth-preview wide` argument renders synthetic artwork only. Physical use
requires the private pairing configuration, camera/microphone permissions and a
trusted TLS connection to the Mac. Owner-controlled Guided Access is still a
required physical acceptance step, not an implemented bypass of iOS security.

Verification performed:

- `scripts/build-ios-simulator.sh`: successful Swift6 strict-concurrency build.
- `scripts/test-ios-visemes.sh`: synthetic cue boundaries/stale epochs/invalid cues.
- `scripts/test-ios-attention.sh`: synthetic coordinates/group centroid/33-64 overflow.
- `scripts/test-ios-scene-images.sh`: transport destination, age/size limits and wire envelope.
- An isolated staged-source compile verifies published code does not depend on
  another owner's uncommitted presentation-settings changes.

Still missing: signed physical deployment, actual camera orientation/mirroring,
image-to-spoken scene reaction, voice/AEC/interruption at family distance, meaningful
audible latency, mouth sync, active-speaker attention, owner exit/kiosk validation,
thermal/crowd/Wi-Fi reliability and12-hour actual-device soak. No iOS product-delivery
claim is supported by these builds or synthetic tests.
