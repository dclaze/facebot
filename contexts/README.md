# Reusable app, characters and event profiles

Facebot loads a selected event and character from JSON at process startup.
The default remains `halloween`; `neutral` is a second use case requiring no
Python or native-client edits.

| Layer | Files | Responsibility |
| --- | --- | --- |
| Shared app | server/ and native clients | Audio, rendering, vision evidence, turn-taking, cancellation, stop/mute, privacy, bounded prompts and output checks. |
| Character | characters/ghost.json and characters/host.json | Personality, visitor-address preference, default name/colors/speed and installed local voice. Both current profiles prohibit speaking visitors' personal names. |
| Event | events/halloween.json and events/neutral.json | Character selection, event rules, relevant facts, arrival and supported visual-reaction content. |
| Private deployment | .local/ paths below | Owner overrides, coaching revisions, explicit recording consent and recordings. |

`HALLOWEEN.md` and `skills/` remain full behavior contracts, not automatically
executable instructions. The JSON files contain the implemented runtime subset.
This extraction does not deliver all proposed Halloween skills, event scheduling
or persistent visitor memory.

## Select a profile

At an appropriate conversation pause, use the existing server restart command:

```sh
.venv/bin/python scripts/restart-server.py --profile halloween
# A different use case, when desired:
.venv/bin/python scripts/restart-server.py --profile neutral
```

The command validates the files before stopping the server, waits for the old
process to exit, then starts the new one. The old conversation, scene state and
queued output disappear with that process. Omitting `--profile` preserves the
selection reported by voice `/health`. Native clients reconnect. This is a
restart-based event change, not in-conversation character rotation.

For fresh services, set `FACEBOT_PROFILE=neutral` before starting
`python -m server.app` with the existing pairing configuration. Run the settings
service and coaching CLI with the same profile environment:

```sh
FACEBOT_PROFILE=neutral .venv/bin/python -m server.admin --host 127.0.0.1
FACEBOT_PROFILE=neutral .venv/bin/python scripts/coach.py show
```

Preserve existing approved host/client-access options for an existing settings
service. Its `/api/settings` response and page label identify the edited profile;
voice `/health` identifies the deployed profile. Selection and file content are
pinned until each service restarts. Settings and coaching within that profile
still apply on subsequent turns.

## Private-state isolation

Only Halloween uses the existing `.local/runtime-settings.json`,
`.local/night-coaching.json`, `.local/recording-config.json` and
`.local/interactions/` paths. This preserves current owner overrides, no-name
and no-proximity-nagging direction, and explicit recording configuration.

Other profiles use `.local/profiles/<id>/` with the same filenames. Missing files
use character defaults, empty coaching and recording disabled, with no fallback
to Halloween state or consent. Recordings are never read as conversation memory.
Persistent event memory is not implemented; conversation/scene state is ephemeral.

## Add a use case

Copy `events/neutral.json`, make the id match its filename, and edit its rules,
facts and reactions. Reference an existing character or copy
`characters/host.json` with a matching new id. Identifiers use lowercase letters,
digits, underscores and hyphens. `{name}` is the only text placeholder. Voice ids
must refer to an installed compatible local voice; profiles do not install models.

The loader validates schemas, identifiers, bounded text/facts, presentation,
expressions and prepared speech of at most 12 words. Invalid profiles fail instead
of silently loading another event. Use only supported vision labels; profiles do
not create sensors. Shared safety/privacy/evidence and stop/mute rules remain
independent of profile content. Camera proximity and retreat stay silent.

## Verification and limits

`tests/test_profiles.py` covers neutral content, no-name instructions, fixed
startup selection, invalid profiles, a third data-only event, private-state
isolation and prepared reactions with mute/proximity. Related persona, interaction,
context-budget, recording, guard and settings tests cover shared integration.
Separate-process checks use the real tokenizer and a mocked speech engine; they
are API/pipeline evidence, not physical audience testing.

Name avoidance is preserved in required context, not a guarantee that a generative
model can never violate it. Physical dialogue quality, timing, full Halloween
behavior and overall product delivery retain their existing acceptance gates.

## Runtime capabilities

`capabilities/SOUND_EFFECTS.md` is loaded into the shared required persona context.
It tells the bot what sounds it can play and how visitors request them. The full
`skills/SOUND_EFFECTS.md` remains the implementation contract; audio routing and
automatic selection remain enforced by the server, independently of model prose.
