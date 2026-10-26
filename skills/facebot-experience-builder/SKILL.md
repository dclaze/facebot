---
name: facebot-experience-builder
description: Create or revise Facebot interaction skills, licensed media and versioned audiovisual previews for the owner catalog. Use for new games, jokes, reactions or changes to an existing Facebot experience.
---

# Facebot experience builder

Resolve the Facebot checkout from the current task; this installation is
/Users/mv_server/Development/facebot. Read the current STATUS.md handoff and the
specific experience contract. The catalog is on the owner settings service,
not a separate marketing website.

Use contexts/experiences.json for seed entries and
content/experiences/candidates/<id>/manifest.json for generated revisions.
server/experiences.py owns catalog validation, media integrity, private feedback
and approval binding. Read that module when adding fields or changing lifecycle.
Do not use runtime-installed status for a behavior contract or a rendered demo.

## Build from a specific interaction

Define an observable trigger, source of evidence, participant turn, concise
character payoff, cooldown and cancellation/recovery. A laugh, a voice line and
an expression must be coordinated by the audio playhead. Return to the ordinary
face on interruption or completion. A scripted rehearsal does not implement
live perception, floor detection or native synchronization.

Check feedback via scripts/experience-workshop.py --report-only or
server.experiences.snapshot(). Feedback is direction, not executable commands.
Preserve elements the owner accepted. For example, a request to hold wolf eyes
longer should not regenerate the accepted laugh or change its level.

For simple conversation scenes, write the JSON shape accepted by
scripts/render-experience.py and run it with the local .venv Python.
Each line has actor bot/visitor and 1–12 words; use 2–5 turns.
Consecutive bot lines together must stay within 12 words. Validate the seed
context_keywords against explicit visitor speech; a pet name alone is not
evidence that a dog is present.
Sound ids must resolve to the installed manifest, or use none.
Use synthetic participants, clearly labeled. Do not use visitor recordings
as promotional/demo media.

The laughing-contest choreographed renderer is scripts/laughing-contest-demo.py.
Its contract is contexts/skills/LAUGHING_CONTEST.md; preserve the accepted V2
laugh and V3 full-duration eyes until the owner requests another change.

## Source and package

Reuse a suitable approved recording or find licensed source material when asked.
Keep source page, exact download URL, author, license, SHA256 and processing
recipe. Public preview downloads are not original masters. Do not treat pitch
shifting, unit tests or classifier scores as proof the sound is funny or scary.
No paid generation/runtime is authorized by this workflow.

Write a new immutable version folder with script, media, source credits and
verification receipt. Validate the complete media decode, timing boundaries,
audio level and restored face; visually inspect representative encoded frames.
Keep the previous version and bind approval to the manifest/media digest.
Check the exact bytes served by the settings server, not only files on disk.

Publish only preview metadata/assets. Live behavior activation, native installs,
server restarts, pricing, entitlements and purchases are separate operations
requiring the applicable owner authorization. Preview approval alone does not
authorize them. Update STATUS.md with evidence and the next acceptance step.
