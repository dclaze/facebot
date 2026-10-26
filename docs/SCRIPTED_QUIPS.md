# Halloween quips and dialogue triage

Halloween now has a prepared 66-line pack in `contexts/quips/halloween.json`:
six welcomes, twelve general ghost jokes, eight candy reminders, and forty
remarks across seventeen camera labels. Other event profiles retain their own
existing behavior. Conversation, direct sounds, and Robin requests remain available.

Examples:

- “Hey YOU! One candy per person, PLEASE!”
- “One candy per person. Extra arms do not count.”
- “One treat apiece. This is a haunting, not a buffet.”
- “A cape! Finally, someone dressed for an entrance.”
- “My last selfie was just the background.”

`QuipDirector` selects complete, authored lines without a dialogue-model call.
Each group rotates in order; the rotation and cooldown survive socket reconnects
within the same server process. A restart resets them. The pack is visible in the
Skills & personalities catalog after its catalog changes are integrated.

The director requires a fresh positive face observation, respects mute and busy
states, waits eight seconds after speech, and spaces spontaneous remarks by at
least 30 seconds. Candy reminders start no sooner than 45 seconds after the first
eligible audience observation, then at least 150 seconds apart. No empty-room
backlog is replayed. Specific costume remarks require the vision service's
confirmed, fresh labels. Furniture does not trigger this pack. Candy-taking,
identities, and exact crowd counts are never inferred. Prepared text still uses
the selected local TTS engine; these are scripts, not prerecorded voice clips.

The two conversation paths can still compete in a noisy crowd: continuous VAD or
open conversation can delay proactive quips. Quiet gaps take priority over speaking
over an active exchange. Field performance under Halloween noise is not established.

## Evidence from the dialogue audit

The retained host log snapshot covering October 25, 2026, 4:04–6:02 PM PDT has
1,708 events, 225 recognized utterances, and 290 planned replies. These are server
receipts, not proof that the tablet audibly played each line.

- 141/290 planned replies (48.6%) were the identical output-guard fallback.
  A previously documented 12-word guard turned ordinary longer answers into
  refusals. Another implementation owner has already changed that bound to
  32 words/240 characters with a separate length repair. The old receipts contain
  no raw pre-guard reply or rejection reason, so individual causes cannot be assigned.
- 49/290 planned replies (16.9%) repeated the sofa line. Existing repetition
  cooldown work mitigated that path; the Halloween director now replaces it with
  rotating audience/costume material and excludes furniture entirely.
- Accepted replies also included fragments, incoherent combinations and literal
  sound-command examples. The voice-quips owner owns the command-leak fix; the
  noise-clarity owner owns concise, complete character delivery. This change does
  not claim their fixes or upgrade the conversation model.
- The transcript includes a phrase repeated fourteen times. Tiny.en output was
  being filtered mainly by no-speech probability; segment confidence and audio
  quality were not retained. A 250ms speech-end pause may also split natural pauses;
  this is a source-level risk, not a measured cause of each fragment.

Private evidence is in `.local/dialogue-audit/observed-summary.json`, with exact
log line locators, and `.local/dialogue-audit/asr-comparison.json`. On one retained
20-second microphone excerpt, cached tiny.en and small.en yielded substantially
different transcripts in 0.939s and 1.009s respectively. Both passed basic quality
thresholds. Without a human reference this is neither a word-error-rate benchmark
nor proof that small.en is better. No model swap was made.

## Transcription changes and limits

`LocalSTT` keeps the local tiny.en model and raw PCM input contract. It disables
within-utterance previous-text conditioning, rejects long repeated phrases,
high compression ratios, likely silence, and low-confidence segments. If any
segment is unreliable, it rejects the whole utterance rather than deleting words
and accidentally changing its meaning. Speech-end VAD now waits 450ms. This
deliberately adds 200ms to that stage; the previous latency target remains unmet.

Opt-in recording now includes bounded numeric quality receipts: audio duration,
RMS, clipping, inference time and recognizer confidence/repetition metrics.
Rejected text is not separately retained. Existing recording consent and retention
remain in force. `/diagnostics` exposes acceptance/rejection counters.

These checks catch obvious failures; they do not determine whether speech was
addressed to the bot, detect every bad transcript, or make confidence a calibrated
accuracy score. Microphone placement, echo/background pickup, and real outdoor
noise still need measured audio evidence. A larger ASR model should be selected
only after a labeled comparison, not from plausible-looking output alone.

## Validation and integration

Run focused checks with the repository environment:

```sh
.venv/bin/python -m unittest tests.test_scripted_quips tests.test_transcription tests.test_interaction tests.test_visual_runtime tests.test_visual_repetition tests.test_catalog
```

Fake-clock simulation checks ten minutes of rotation, reminder spacing, fresh
observations, mute/busy behavior, and reconnect continuity. Frame tests prove
prepared quips bypass the LLM, and stale queued quips are dropped. Mocked ASR
tests exercise actual service handling and ensure rejected loops yield no user
turn. These are deterministic tests, not noisy-room or acoustic acceptance.

The runtime has one deployment owner. Use the canonical shared `STATUS.md` to
integrate this branch's focused commit; do not restart over an active performance.
Verify `/health.scripted_quips` and `/diagnostics.transcription` after integration.
As of the audit's live check at 6:14 PM PDT, those fields were absent: source
implementation was verified, but this feature was not yet active on that server.


## Follow-up: incoherent live replies (October 25, 6:17 PM PDT)

Latest retained receipts include an internal instruction spoken verbatim (log line2372), unfinished replies (2330,2341), and a literal sound command (2318). The live server still lacked the earlier quip/transcript changes at the follow-up check. One isolated synthetic local-model replay of “Can I take two candies?” returned “Sure, you can have two!” despite event instructions. Remaining replay requests were stopped; this is one example, not a quality benchmark.

A narrow reply-quality check now replaces the observed instruction leaks and dangling fragments with a short clarification. It does not claim to identify every incoherent sentence. Candy-quantity requests receive an authored one-piece answer before the model, while health/ingredient/price questions and ordinary conversation remain on their existing paths. The guard emits numeric reason/length receipts through existing opt-in recording; raw rejected output is not retained separately.22focused tests pass, including the recorded failures, valid terse answers, original safety checks, model bypass, mute, and reason logging.
