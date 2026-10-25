# Facebot 👻

**Give your Halloween costume a face. And an attitude.**

Facebot is a planned open-source, locally powered Halloween character: a tablet becomes an expressive face that notices visitors, talks naturally, and delivers deeply unnecessary opinions about their candy etiquette.

> “One piece, darling. This is a haunting, not a wholesale operation.”

**Status: planning. There is no runnable application yet.** Facebot is a working name. Follow [STATUS.md](STATUS.md) for the current milestone and [the roadmap](docs/ROADMAP.md) for acceptance criteria.

## What we want to build

- A cute, expressive ghost with a name, animated eyes, and a mischievous personality.
- Very natural speech, continuous listening during active sessions, and fast interruption handling.
- Camera-based attention: notice approaching visitors and react immediately.
- Local speech, language, and vision processing using existing hardware, with no required cloud inference or token charges.
- Family-safe sass, operator mute, and no recording or identity recognition by default.
- Optional candy-bowl commentary that encourages one piece per visitor.
- Reliable operation for a 12-hour event.

The intended setup is a tablet on a stand, optionally inside a costume, connected to a local Mac server. Both iOS/iPadOS and Android are target platforms, with physical-device validation required for each. A shared browser client and native clients are being evaluated; models and application architecture have not been selected.

## Responsiveness is a core requirement

These are **proposed benchmark targets**, not measured capabilities:

| Behavior | Target |
| --- | --- |
| Visible reaction to an approaching visitor | p95 at or below 200 ms |
| Stop speaking when interrupted | p95 at or below 250 ms |
| First meaningful generated speech after a visitor finishes | Median around 1 second; p95 at or below 1.5 seconds |
| Sustained event operation | 12 hours on the actual hardware |

Measurements must include the complete user-visible path. Cached greetings and filler do not count as generated replies. Disabling the microphone while speaking does not satisfy the listening requirement.

## Candy commentary, with realistic expectations

A camera can help detect reaching and visible grabs. It cannot reliably count pieces concealed in a hand or physically enforce a one-piece rule. This feature needs experiments with actual lighting, candy, bowl placement, and crowds. Uncertain observations should produce playful reminders, not accusations.

## Open development

First: agree on requirements, prove the voice and camera experience, and make the installation work. Pricing discussions come later.

See [reference projects](docs/REFERENCES.md) for frameworks and examples under consideration. We aim to reuse suitable components and contribute broadly useful improvements upstream. No third-party implementation has been copied into this repository.

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Project code and original documentation are under the [MIT license](LICENSE). Third-party software, model weights, voices, and assets retain their own licenses.
