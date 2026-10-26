# Skill: Sound effects and automatic reactions

Implemented in `server/sound_effects.py`, with routing before language generation
and PCM playback after speech synthesis. Requires a server reload to activate a
new source revision; check STATUS.md for the actual deployment receipt.

Play one short effect when a visitor explicitly asks, for example:

- “Boo, make a ghost sound.”
- “Can you fart?” / “Make a boing sound.”
- “Play a drumroll.” / “Do a rimshot.”
- “Make a cat sound.” / “Play a bell.”
- “Give me a laser sound effect.”
- “What sounds can you make?”

Direct bare names such as “Boo”, “Bo”, “Hey Boo”, “Boo please”, “Meow” and “Pew pew” also work. Match complete requests
against the local allowlist; never interpret a filename, shell command, URL,
negation, quotation or incidental mention as a playback command. Unsupported or
compound requests continue through ordinary dialogue. Withheld draft effects get
a brief honest spoken response; they never pretend to play. No LLM tool call,
corpus prompt injection or online search is
needed. The full corpus is never placed in the conversation prompt. A compact capability
summary in `contexts/capabilities/SOUND_EFFECTS.md` is loaded by `server/persona.py`
so the bot can describe its sounds.

Use one clip per request, alternate its two variants, and use the existing stop,
silence and interruption path. A sound request does not unmute the character.
No automatic jump scares, looping, volume boosts or sounds over visitor speech.
Existing audio transport owns pacing, speaking-state notifications and native
epoch-based queue flushing. Effects are prepared audio, never evidence of
generated-reply latency. Clip peak limits are digital limits, not calibrated
speaker loudness guarantees.

## Automatic reactions

The Halloween profile enables a local performance director after the reply guard.
It chooses matching cackles, bells, comic stings and arcade effects from
`contexts/sounds/halloween.json`, and a rimshot after a requested joke. Effects
queue after the complete spoken reply, with a 30-second cooldown, at least three
reply positions between effects and no same-effect repeat within two minutes.
Direct requests take priority. Interrupted, muted, stale, serious or distressed
turns receive no automatic embellishment. No extra inference or prompt tokens.

Say “stop sound effects” to disable automatic reactions for this connection, or
“turn on sound effects” to resume. Explicit sound requests still work. Profiles
without a sound policy remain disabled. Diagnostics count server-emitted clips,
not confirmed acoustic playback.

## Corpus

`content/sounds/manifest.json` contains 20 effect types and 40 WAV files, all
derived from downloaded creator assets with per-entry provenance and licenses.
The active builder rejects any effect without a credited source; procedural drafts
are not a fallback. Mono 24 kHz, signed 16-bit PCM, -9 dBFS peak ceiling and a
six-second maximum preserve complete drum/cymbal and trombone endings. Current
longest clip is about 4.51 seconds.

Comedy stings use eggsandwichent’s sampled drum performance; recorded snare rolls
by bigjoedrummer, trombone by Benboncan, jaw harp by James.Keeble and desk bell by
ChrisGrundlingh replace the in-house imitations. Kenney supplies designed
electronic arcade/sci-fi effects. Other credited recordings remain in use.
Freesound public HQ MP3 previews are labeled honestly; they are not lossless
originals. Sources, licenses, trims and speed changes are in selection.json,
CREDITS.md and source-receipts/. The owner catalog shows creator/license links.

Clean up silence and rumble, preserve attacks and decay, and level-match with
headroom. Do not count automated recognition scores as audience acceptance.
The original CLAP screen passed a rimshot that Doug explicitly rejected; those
results are historical, not validation of this replacement corpus.

Rebuild deterministically from the repository root:

```sh
.venv/bin/python scripts/build-sound-corpus.py
.venv/bin/python -m unittest discover -s tests -p 'test_sound_effects.py'
```

`content/sounds/sampler.wav` auditions the first variant of all 20 types in
manifest order, separated by half-second gaps. Preview individual WAVs for
editorial sound quality. Mechanical audio validation does not establish acoustic
quality or sound recognition on the tablet.

`content/sounds/showcase.wav` is a short preview in this order: cackle, creaky
door, fart, slide whistle, boing, rimshot, sad trombone, laser.
