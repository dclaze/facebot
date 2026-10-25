# Crowd mode

Owner requirement, 2026-10-25: MANY faces and mobs of children in front of the app, with about3,000passersby over Halloween. This is required for launch, not an optional visual polish item. Android & iOS apps remains the sole runtime owner. This document does not change the active family trial.

## Initial source review (superseded in part below)

- Android Attention receives a list of ML Kit faces, reports its size and chooses the widest bounding box for gaze. No persistent face tracks or active-speaker association are implemented here.
- Android VoiceClient drops scene updates when faces>32. Server protocol accepts only0–32. This is a transport validation bound, not demonstrated detector capacity. Above-bound detections can leave the server with stale observations.
- SceneState accepts only face count/age and expires stale evidence; it explicitly does not identify the speaker, clothing or actions.
- EncounterState increments its generation after a stable count change. Its consumer clears previous dialogue on generation change. Crowds, occlusions and movement can therefore interrupt continuity even when the person speaking has not changed. Same-count replacement also does not establish continuity.
- Physical multi-person accuracy, masked visitors, overlapping speech and crowded low-light operation remain unaccepted. iOS camera parity remains incomplete. No tested maximum crowd size has been established.

## Required behavior

1. Detect multiple visible faces without blocking audio. Keep only fresh frames, bound processing and metadata, and discard obsolete analysis under load. Never treat visible faces as a complete crowd headcount: masks, backs of heads, distance and occlusion matter.
2. Maintain a bounded set of temporary local tracks with position, freshness and uncertainty, without saved images, recognition embeddings or permanent identities. Prefer the near interaction area while keeping a coarse group-presence state. Do not invent precise far-background counts.
3. Keep attention stable through small movements and temporary occlusion. Use evidence of the active speaker when available; otherwise hold a calm group-facing gaze or a stable conversational target. Largest face is a fallback position, not proof of who is speaking. Do not snap between children every frame.
4. Address the group naturally and initiate only once per stable encounter. Avoid a greeting, candy warning or costume joke for every detected arrival. Preserve extreme clean sass, e.g. “A committee. Wonderful. My performance review has arrived.” Example only, not a repeated greeting.
5. Manage one conversational floor. Yield to a clear interruption; if overlapping voices are unintelligible, use a brief playful repair such as “One at a time—my ears are decorative.” Do not pretend a single mixed microphone stream identifies every speaker or binds their words to faces. Do not mock a child's voice or speech.
6. Preserve the running group topic when a background person enters/leaves. Do not clear all dialogue solely because the count changes. Keep personal/volunteered-name memory separately gated by actual encounter evidence; uncertain replacement must never expose a previous person's details. Anonymous group context is not individual identity.
7. Gracefully represent crowded/overflow observations with bounded metadata. Consider a saturated count plus explicit overflow/uncertainty rather than silently dropping every update above32; finalize the schema in implementation. Overflow must not make a crowd appear empty, trigger repeated greetings or overwhelm the WebSocket queue.
8. Crowd load must not degrade stop/mute, acoustic interruption or the binding meaningful-reply latency targets. No paid cloud overflow or new per-visitor model session. Keep expensive visual reasoning off the speech path and use a bounded queue.
9. Coordinate group jokes with the Halloween context. Costume-specific jokes need supported costume evidence and correct attribution; face presence alone is insufficient. Keep reminder/joke cooldowns global as well as per encounter.

## Verification

- Controlled physical scenes at1,2,5,10 and20+visible people where space and camera framing allow. Those are test tiers, not an already supported capacity claim. Record observed detection coverage and uncertainty without retaining visitor images. Use adults/consented controlled tests rather than requesting a crowd of children for routine verification.
- Synthetic metadata replay at0,1,5,10,20,32,33,64 and rapid churn. Test overflow, schema compatibility, bounded memory, staleness, transitions and recovery. Replay proves state handling, not camera accuracy.
- Masks, partial faces, short/tall participants, low light, occlusion, backs to camera, empty scene and rapid departures. Return to neutral when evidence is stale or ambiguous.
- Two simultaneous speakers, off-camera speaker, background TV, laughter and sustained crowd noise. Measure actual audible interruption, false interruptions and repair behavior; don't report transport acknowledgments as acoustic performance.
- A child telling a story while background face count changes must not lose the topic. A same-count audience replacement must not inherit personal callbacks or names. No automatic assumption that a returning face is the same person.
- Long crowded run followed by empty scene: no queued joke burst, no repeated greetings, no stale scene claims and no leaked memory. Integrate these cases into both platform twelve-hour soaks.

Acceptance includes measured performance at documented distance, lighting and device configuration. A total of3,000passersby is an event-load estimate, not a promise to identify or individually serve everyone simultaneously.

## Implementation checkpoint — 2026-10-25

Staged Android source maintains up to 16 temporary position tracks with nearest-position association, smoothed coordinates and 750 ms expiry. Gaze uses the retained group centroid rather than the largest box. These IDs never leave the attention helper, are not used for memory, and do not establish identity or the active speaker. Synthetic crossing/occlusion accuracy and physical crowded attention remain to be evaluated; finite matching can lose or swap spatial tracks.

Android now sends a saturated count of 32 plus an explicit overflow flag instead of dropping larger detections. Server accepts bounded legacy counts through 4096 and normalizes them to the same representation; the limit is protocol validation, not supported camera capacity. Scene context says “at least 32” when saturated. Strict types, freshness and audio-backlog dropping remain in force.

Synthetic tests cover 33/64 detections, 600 count-churn updates without repeated greetings, bounded track storage, small-motion continuity, expiry and group-centroid gaze. No family media or inference workload used. Count-change history resets remain a known issue: safely retaining a group story requires separating personal memory from anonymous group context before removing the conservative reset. Overlapping-speech perception, masks/noise, iOS parity and measured physical crowd tiers remain open. Changes are not deployed during the child trial.
