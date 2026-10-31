---
name: facebot-experience-reviewer
description: Review Facebot experience previews and owner feedback, prioritize revisions, and run the bounded local workshop toward a reviewable skill collection. Use for improving the catalog or recurring draft reviews.
---

# Facebot experience reviewer

Work in the current Facebot checkout (installed at
/Users/mv_server/Development/facebot). Read the current STATUS.md handoff.
Use scripts/experience-workshop.py --report-only for the queue before opening
large histories. Owner feedback comes from the private profile-scoped
experience-reviews.json store; never publish that store or actual visitor media.

Prioritize requested changes, then missing previews. An approved preview waits
for separately authorized integration; do not repeatedly regenerate it.
Approval is tied to the full manifest digest, not just the display version.
An old approval must not silently authorize changed media.

Review whether the visitor understands the premise without hidden context,
whether the payoff fits the observed/spoken trigger, and whether the turn leaves
room for the visitor. Keep observations, hypotheses, simulated evidence and
physical-device acceptance distinct. A current media decode/hash pass does not
establish comic quality, recognition accuracy or speaker loudness.

## Automatic lane

scripts/experience-workshop.py performs one bounded local model draft and renders
a preview. It uses installed Qwen via local Ollama and local Kokoro. It cannot
execute model-returned code or edit live runtime: output is validated scene JSON,
and only candidate media/manifests plus private workshop receipts are written.
An exclusive lock prevents overlapping runs. Quota lookup fails closed; at
7% or less remaining, no model work begins. Unchanged failed requests are skipped
until feedback/content changes. No reset credits.

The schedule is a local LaunchAgent at 9 AM Pacific through October 31, 2026.
After the deadline it is inert. Do not extend its scope, cadence or deadline
without owner direction. Runtime remains $0 paid services. A missing local model
or a failed render leaves the current catalog in place and records the issue.

The generic automatic lane handles short scripted conversation previews.
Choreographed scares and changes to the accepted laughing contest route to
$facebot-experience-builder; they must not be flattened into generic dialogue.
Do not infer that a contract's proposed vision feature is implemented.

## Review outcome

Publish a candidate only after script validation, full video decode and media
hashes pass. Confirm the catalog serves the new version and feedback persists
across reload. Human scariness, humor and taste remain for Doug to judge in the
preview panel. Stay quiet when a scheduled pass has no actionable work; record
meaningful progress/failure in the catalog workshop status. No unsolicited
messages, external sharing, purchases, live activation or authentication changes.

Record a concise STATUS.md checkpoint for meaningful milestones. For manual
revision work, use the builder skill; do not spawn duplicate implementation
owners or expand into unrelated platform fixes.
