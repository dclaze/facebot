# Facebot 👻

**Give your Halloween costume a face. And an attitude.**

Facebot is an open-source, locally powered Halloween character: a tablet becomes an expressive face that notices visitors, talks naturally, and delivers deeply unnecessary opinions about their candy etiquette.

> “One piece, darling. This is a haunting, not a wholesale operation.”

**Halloween Android alpha:** download the signed APK from [Releases](https://github.com/dclaze/facebot/releases) and follow the [setup guide](docs/PUBLIC_SETUP.md). Requires an Android tablet (Android 8+) and an Apple Silicon Mac host. The public APK contains no pairing credentials or models.

The free skill shop includes a candy host, short jokes, invited playful scares, an explicit-turn laugh challenge and licensed sound effects. Enable packs from the Mac owner controls; upgrades in this release are bundled and free, with no checkout. Personal guest performances require separately supplied local media and are not distributed. Kiosk mode uses bounded authored replies, including a safe fallback, rather than open-ended chat.

The host watchdog restarts the voice service and owner controls independently and keeps the Mac awake. An optional USB watchdog can reopen an absent tablet app process while voice stays on Wi-Fi. Default Home selection alone did not recover a forced crash on the tested Lenovo. This is an experimental self-hosted release: full 12-hour endurance and generated acoustic latency acceptance remain outstanding. See [readiness tooling](skills/facebot-kiosk-certification/SKILL.md), [STATUS.md](STATUS.md) and [the roadmap](docs/ROADMAP.md).

## What we want to build

- A cute, expressive ghost with a name, animated eyes, and a mischievous personality.
- Very natural speech, continuous listening during active sessions, and fast interruption handling.
- Camera-based attention: notice approaching visitors and react immediately.
- Local speech, language, and vision processing using existing hardware, with no required cloud inference or token charges.
- Full-screen character presentation, visitor touches disabled, and owner-only exit.
- Family-safe sass, operator mute, and no recording or identity recognition by default.
- Optional candy-bowl commentary that encourages one piece per visitor.
- Reliable operation for a 12-hour event.

The intended setup is a tablet on a stand, optionally inside a costume, connected to a local Mac server. Both iOS/iPadOS and Android are target platforms, with physical-device validation required for each. The Android alpha uses native playback with local Whisper, Kokoro and Ollama on the Mac. iOS remains a separate validation target.

## Responsiveness is a core requirement

These are **acceptance targets**, not measured capabilities. The speech target was tightened on 2026-10-25 at the owner’s request to match typical human turn timing:

| Behavior | Target |
| --- | --- |
| Visible reaction to an approaching visitor | p95 at or below 200 ms |
| Stop speaking when interrupted | p95 at or below 250 ms |
| First meaningful generated speech after a visitor finishes | Median at or below **200 ms**; p95 at or below **500 ms** |
| Sustained event operation | 12 hours on the actual hardware |

The speech clock starts at the visitor’s actual utterance end and stops at the first meaningful audible generated response. It includes endpoint detection, inference, output checks, network and playback buffers. A 10-language conversational study found a mean turn gap of 208 ms and median of 100 ms; our 200 ms median target uses that human-scale timing. The 500 ms p95 is our engineering tail-latency requirement, not a published universal naturalness threshold. See [timing evidence and measurement rules](docs/CONVERSATION_TIMING.md).

Measurements must include the complete user-visible path. Cached greetings and filler do not count as generated replies. Disabling the microphone while speaking does not satisfy the listening requirement.

## Candy commentary, with realistic expectations

A camera can help detect reaching and visible grabs. It cannot reliably count pieces concealed in a hand or physically enforce a one-piece rule. This feature needs experiments with actual lighting, candy, bowl placement, and crowds. Uncertain observations should produce playful reminders, not accusations.

## Open development

First: agree on requirements, prove the voice and camera experience, and make the installation work. Pricing discussions come later.

See [reference projects](docs/REFERENCES.md) for frameworks and examples under consideration. We aim to reuse suitable components and contribute broadly useful improvements upstream. No third-party implementation has been copied into this repository.

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Project code and original documentation are under the [MIT license](LICENSE). Third-party software, model weights, voices, and assets retain their own licenses.
