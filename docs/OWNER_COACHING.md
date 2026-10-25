# Live owner coaching

This tunes the night prompt, not model weights. Tell the implementation owner the
correction; distill it into a short behavioral rule rather than saving a visitor
transcript. Only the Mac owner CLI writes the coaching file. The visitor audio
pipeline has no write path and does not identify an owner by voice.

```sh
.venv/bin/python scripts/coach.py show
.venv/bin/python scripts/coach.py set 'Answer first; use one specific clean reversal.'
.venv/bin/python scripts/coach.py rollback 1
.venv/bin/python scripts/coach.py clear
```

`set` replaces the complete set. Up to six rules, 200 characters each and 600 total
are loaded on the next generated turn. An already-running reply is unchanged.
No app or server restart is needed after installing this feature. The last 20
revisions are kept in ignored `.local/night-coaching.json`, mode 0600; there are
no automatic audio, video or transcript examples. `clear` disables the added
coaching while retaining revision history. An invalid file disables coaching
without stopping speech. The core privacy, silence and child-safety instructions
remain; coaching is not a safety guarantee or a substitute for generated-reply
and actual-device evaluation.
