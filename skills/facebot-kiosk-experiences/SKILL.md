---
name: facebot-kiosk-experiences
description: Author, rehearse and verify Facebot candy-tray interactions and their prepared speech cache.
---

# Candy-tray experience lane

Read canonical STATUS ownership before runtime work. Use an isolated worktree;
only the named runtime owner installs APKs, restarts servers or triggers devices.

Keep ordinary visitor requests in `server/kiosk_experiences.py` and authored
lines in `contexts/kiosk/halloween.json`. PreparedConversation is already in the
voice pipeline. KioskPlayback belongs after LocalTTS; emit wolf-eye cues before
its PCM, enriching epoch and offset at the serializer. Actual cue timing and
cancellation belong to the native audio playhead, never wall-clock timers.

Stable pack IDs: candy-host (required), quick-jokes, playful-scares,
laugh-challenge. Inject the skill-store `enabled` predicate. The laugh challenge
requires an explicit request and explicit “your turn” within 20 seconds. Silence,
background laughter and room chatter are not assent. No taking/stealing claims
from faces, proximity or a candy question. Stop/mute wins over every pack.

Use the immutable accepted V2 cackle in content/kiosk, with its source receipt,
license and digest. Do not replace it with spoken “ha ha” or silently change the
approved full-duration eyes. The live explicit-turn adaptation is different
from automatic laugh detection; label that limitation. Preserve private Robin
performance routing; never put private character audio in public starter packs.

For new lines: keep at most10 words, pass the actual reply guard, make the payoff
understandable without hidden context, and give visitors space. Exact request
matching must reject negations, quotes, compound commands and noisy fragments.
In public kiosk mode unsupported speech gets a short authored hint, never an
unbounded model response. During the laugh participant's turn, unmatched speech
gets no reply. Game cancellation is silent.

Run:

```sh
.venv/bin/python -m unittest tests.test_kiosk_experiences tests.test_reply_quality tests.test_tts_stream
.venv/bin/python scripts/benchmark-kiosk.py --output .local/kiosk-evidence/benchmark.json --prewarm
.venv/bin/python scripts/render-kiosk-preview.py .local/kiosk-evidence/previews/NEW_VERSION
```

Prewarm reads the current settings speech rate and profile voice; explicit
`--speech-rate` and `--voice` overrides let an isolated tree prepare the exact
deployment configuration without copying private settings.

Renderer needs the existing Pillow/NumPy/SciPy/imageio-ffmpeg development tools.
If they live outside the venv, supply their existing directory through PYTHONPATH.
Render only to a new owned folder. Extract and visually inspect encoded frames
(including final cackle tail and normal-face restoration), not source posters.
Use source-verified real audio and synthetic visitor voices; never visitor media.

PreparedAudioCache stores only authored allowlisted speech. Its key includes
model, voice, speed and text. Cache misses synthesize normally. Never describe
cached reads as generated latency or route latency as end-of-speech latency.

## Acceptance rubric

1. Actual PreparedConversation replay: explicit requests bypass LLM; malformed,
   missing, noisy, negated, quoted, privacy and prompt-injection cases remain
   bounded; no invented observation; enabled/disabled packs honored.
2. Stateful replay: participant gets floor; explicit turn,20s deadline,60s game
   cooldown, repeated transcript, silent stop/mute, reconnect and stale-frame
   cases pass. Replay is not microphone-recognition evidence.
3. Audio: all PCM bytes decode, digest matches, level unboosted; prepared cache
   preserves full PCM/captions/visemes and invalidates on voice/rate/text changes.
4. Visual rehearsal: encoded eyes throughout cackle, readable short dialogue,
   friendly restoration, no clipping. Critique humor, pacing and appearance;
   a decode/hash pass alone does not establish quality.
5. Integration owner: exercise each skill through authenticated route and actual
   tablet, test interruption/reconnect, record exact build/commit and any physical
   observation. Keep USB/synthetic playback distinct from microphone/acoustic proof.

A missing physical observation is an explicit evidence gap for the runtime owner,
not permission to claim delivery from a rehearsal. Record completed checks and
next concrete acceptance in STATUS.
