# Facebot task list

Updated 2026-10-25. Software owner: Android & iOS implementation session.
[STATUS](../STATUS.md) records evidence; [acceptance](ACCEPTANCE.md) defines delivery.
Unchecked items are not accepted, even where prototype code exists.

## P0 — make the live prototype compelling and reliable

- [ ] Improve unnatural voice and delivery at $0 runtime cost: compare installed voices on identical synthetic lines after the live trial; measure genuine synthesis first-audio time. Segment emission is implemented, but Kokoro still generates each segment in full. Evaluate expressive Qwen3-TTS/Chatterbox only outside the trial, with exact local latency and license evidence.

- [ ] **Crowd mode (launch requirement):** support many visible faces with stable group attention, bounded temporary tracks, graceful overflow and overlapping-speech repair. Preserve conversation through background count changes without leaking personal memory across visitors. Current largest-face gaze and0–32 count transport are not crowd acceptance. See [crowd requirements](CROWD_MODE.md).

- [ ] Polish the mouth: distinct phoneme shapes, sealed M/B/P, natural teeth/tongue and smooth transitions. Review native renders and moving speech; verify playback alignment and interruption reset. New Android renderer builds; visual and acoustic acceptance pending.
- [ ] Improve actual generated dialogue: extremely sassy, specific, Mill Valley-aware, zero profanity and kid-safe. Evaluate varied replies, factual accuracy and repetition; a corpus or prompt edit alone is insufficient.
- [ ] React to the audience rapidly: fresh face/presence/count signals, uncertainty-aware scene context and measured reaction delay. Face count is not a complete people count; couch, costumes and candy actions remain unsupported.
- [ ] Initiate conversation on stable arrivals and supported scene changes. Debounce events, avoid repeated greetings and empty-scene chatter, yield to visitors, honor silence/mute. Arrival dispatch and deterministic visitor stop/resume are implemented and synthetically tested; deployment and physical acceptance are pending.
- [ ] Verify continuous listening without a wake word, acoustic barge-in, echo rejection, retained interrupted utterances and stale-audio suppression on the tablet.
- [ ] Measure and improve end-to-end meaningful audible reply latency against 200 ms median / 500 ms p95. Current model screens do not meet the requirement.
- [ ] Close semantic safety gaps and verify immediate operator mute / visitor stop in the running app.

## P1 — expressive behavior and complete device experience

- [ ] **Costume dad-joke skill (queued):** integrate [the behavior contract](../contexts/skills/COSTUME_DAD_JOKE.md) under a selectable [Halloween context](../contexts/HALLOWEEN.md). Require a spoken costume statement or supported fresh vision evidence; respect corrections, floor, cooldown, recent repetition, silence and distress. Current face detection does not recognize costumes.
- [ ] Separate selectable event/night rules from core behavior, with occasional clear one-piece-per-person reminders. Use bounded [public neighborhood facts](NEIGHBORHOOD_CONTEXT.md); never ingest the private property report.

- [ ] **Wink:** add an independently controlled single-eye close, brief hold and smooth reopen. Keep the other eye expressive; distinguish a deliberate wink from a blink. Use sparingly at an earned comic beat, with cooldown and neutral recovery; never block mouth, gaze or audio. Provide a deterministic synthetic preview and validate on Android and iOS. Requested by Doug; queued, not deployed.
- [ ] Active-speaker gaze: establish hardware feasibility, then subtle smooth attention with neutral fallback. Validate two speakers and ambiguous/off-camera speech; largest face alone is not speaker evidence.
- [ ] Evidence-backed richer scene understanding, with occasional deeper analysis off the speech path and strict freshness limits. No fabricated actions or exact occluded candy counts.
- [ ] Complete iOS camera/face/audio parity and physical-device testing. Owner dependency: attached authorized iOS device; continue independent implementation meanwhile.
- [ ] Implement supported owner-controlled kiosk/touch lock and recovery without reset, enrollment or security bypass.
- [ ] Validate theatrical scare response with capped volume, cooldown and immediate cancellation; do not startle on every turn.

## Delivery gates and later work

- [ ] Twelve-hour actual-device soak on each platform; measure thermal, memory, reconnect, interruption and empty-scene behavior.
- [ ] Candy-bowl monitoring after core reliability: supported actions, uncertainty and occlusion tests; no guaranteed enforcement.
- [ ] Publish reproducible local setup and verified checkpoints, excluding private installation assets, credentials and visitor media.

## Evidence already obtained

- [x] Android installed and owner reported an audible end-to-end response.
- [x] Local speech transport, native continuous capture and bounded playback implemented.
- [x] Local Android face detection and ephemeral scene metadata implemented; reliability/latency acceptance remains open.
- [x] Text-derived synthesis viseme cues and Android playback-clock routing implemented; physical lip-sync acceptance remains open.

Runtime remains entirely local with $0 paid services. Product is not delivered.
