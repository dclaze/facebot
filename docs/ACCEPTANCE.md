# Delivery acceptance

This is the working delivery contract, not a record of passing results. The
canonical progress and dependency record is [STATUS.md](../STATUS.md).
Implementation is authorized; ordinary reversible choices do not require another
planning approval. Both physical platforms are required before product delivery.

## Defaults and ownership

- One active ghost per Mac server. Android and iOS are validated separately.
- Thin native clients, local Mac inference, no paid/cloud inference fallback.
- Configurable name and voice; short, highly sassy, family-safe replies.
- Attention follows people without identifying them. No saved face profiles,
  visitor recordings or conversation transcripts by default.
- One software implementation owner, one enclosure owner, and a requirements
  coordinator. Keep changes in their assigned files; use the software owner to
  integrate acceptance results into STATUS.md.
- Reuse maintained components after checking code and model licenses. Keep private
  deployment details and device identifiers out of public artifacts.

## Required evidence

| Requirement | Acceptance evidence |
| --- | --- |
| Android and iOS apps | Install and launch on each owner's authorized physical device; record build revision, OS and device model without public serial numbers. Simulator builds are a separate milestone. |
| Immersive ghost | Full display face, name, gaze, blinking, speaking expression and visible listening/muted state. No visitor-facing browser chrome or configuration controls. Test in intended orientation and costume. |
| Touch lock and recovery | On each physical platform, ordinary taps and navigation gestures cannot dismiss the character; owner can authenticate and exit. Test system UI, notifications, screen sleep and recovery. Record the actual OS kiosk mechanism and its limits. |
| Continuous conversation | Microphone remains active during ghost speech; a visitor can interrupt, speak, and receive a relevant reply without a button. Reject acoustic echo and stale audio from cancelled turns. Test quiet and noisy conditions, including multiple speakers. |
| Responsive speech | Measure actual visitor utterance end to first meaningful generated audible word. Include endpointing, transcription, generation, guardrails, synthesis, transport, playback queue and device output. Report cached lines separately; filler does not satisfy this measurement. |
| Fast interruption | Measure visitor speech onset to audible ghost playback stopping, not merely a server cancellation event. Verify that cancelled output never returns after reconnect. |
| Camera attention | Approach, leave, move sideways and re-enter under representative lighting. Face reacts locally while the server is busy. Check camera clearance, mirrored coordinates, crowd behavior and empty-scene stability. |
| Public character | Exercise child-friendly prompts, attempts to override persona, abusive prompts and sensitive requests. Replies remain brief and family-safe; jokes target situations or the ghost rather than identity or appearance. Safe fallback and operator mute work. |
| Local lore | Maintain a small sourced lore pack. Identify fictional haunting stories as fiction. Keep private installation information in ignored local configuration. |
| Candy reminders | With the real bowl view, demonstrate reach/withdrawal detection and measure misses and false reminders. Uncertain or occluded scenes must not trigger factual accusations. Hidden-piece counting and physical enforcement are not promised. |
| Offline/local operation | After model preparation, run without internet; verify runtime inference has no external service dependency. Account for any digital spending against the $20 cap. No automatic paid fallback. |
| Twelve-hour event | Each required platform completes an actual 12-hour run with intended power, Wi-Fi, audio, camera and enclosure arrangement. Exercise repeated encounters, empty periods, mute, disconnect/reconnect and server restart. Record crashes, thermal issues, memory growth, battery/power behavior and recovery. |
| Reproducible open source | Publish setup, pinned dependencies, code/model attribution and licenses, sanitized benchmarks and known limits. A clean setup can run the documented path without private developer state. |

## Performance measurement

The binding thresholds are presence-to-visible-reaction p95 <=200 ms,
speech-onset-to-playback-stop p95 <=250 ms, and complete spoken reply
p50 <=200 ms / p95 <=500 ms. The earlier 1 s / 1.5 s speech proposal is
superseded. See [the conversation timing specification](CONVERSATION_TIMING.md)
for research, measurement boundaries and the engineering rationale for the tail
limit. These are requirements, not validated performance claims. Do not silently
relax them to fit a slow model. Prepared responses must be invalidated when a
visitor changes or extends an utterance; premature speech cannot improve scores.

Use monotonic timing within each device. If endpoints cross clocks, document the
clock synchronization or use a common external measurement. Separate host-only
component timings, protocol replay, simulator results and physical observations.
Record sample count, cold/warm state, failures, p50/p95 calculation, model/voice
versions, network conditions and competing host load. A five-sample component
benchmark is a useful screening result, not sufficient end-to-end acceptance.

For physical latency acceptance, aim for at least 100 turns per platform across
short/long phrases, interruptions and representative noise; report difficult
conditions separately so averages cannot hide them. Use consenting operator
test sessions. Keep any opt-in diagnostic media local and delete it after
measurement; public reports use timing summaries and synthetic examples.

## Device-dependent boundaries

Android USB debugging and the Mac authorization prompt require owner interaction
if not already enabled. iOS installation may require device trust, Developer Mode
and a signing identity. Inspect existing supported access before requesting any
action. Do not reset or enroll personal devices to obtain kiosk privileges.

Android screen pinning is weaker than managed lock task; do not report it as
equivalent. iOS Guided Access with Touch disabled is a candidate to validate.
Neither app can promise prevention of forced hardware shutdown. If a device
cannot meet ordinary navigation lock requirements without new provisioning,
record the precise unmet requirement and discuss that consequential choice.

Physical dependencies block only their dependent tests. Continue local server,
native client, simulator, replay and documentation work independently. Product
delivery requires explicit passing evidence in STATUS.md, including both devices
and the endurance runs; a compiled shell or working server alone is insufficient.
