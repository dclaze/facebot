# Social presence and Halloween interaction requirements

Research snapshot: 2026-10-25. Requirements and research, not a claim of deployed behavior. Android & iOS apps remains the runtime owner. Character dialogue work retains its existing owner. Runtime budget: $0 paid services.

## Character is binding

Extreme clean sass is a product requirement, not an optional finishing pass. Use specific comic reversals, dry understatements, mock authority and callbacks. Avoid generic customer-service phrasing, endless ghost puns, repeated candy slogans and trivia monologues. Answer the actual question before adding a short punchline. No profanity, sexual innuendo, discriminatory humor, threats or humiliation. Roast Boo, the situation, fictional bureaucracy and voluntary playful behavior. Stop requests, genuine distress and practical help take precedence over comedy.

## Highest-value skills

These are behaviors for the bot, not a collection of arbitrary coding-agent prompt packs. Timing targets below preserve existing acceptance; proposed animation values are starting points to evaluate, not scientific findings.

| Skill | Required behavior | Evidence / acceptance |
|---|---|---|
| Predict the conversational turn | Distinguish a hesitation from a finished thought; begin preparing silently, cancel speculation on revised speech. | Existing actual utterance-end to meaningful audible reply p50 ≤200 ms, p95 ≤500 ms. Compare silence baseline with semantic/acoustic turn prediction. No filler counted as reply. |
| Yield instantly | Stop generated speech and mouth motion when interrupted; discard stale queued audio and obsolete text. | Actual speech onset to audible stop p95 ≤250 ms, including device buffers. Test TV, own voice and overlapping visitors separately. |
| Look like a listener | Smooth gaze toward supported speaker evidence; subtle brow/eye response at meaningful moments. Brief neutral gaze breaks, not a permanent stare. | Two-speaker tests; uncertainty returns to neutral. Largest visible face is not proof of speaker identity. No expression-to-emotion or age inference. |
| Coordinate a performance | Brows, eyes, mouth, phrasing and vocal emphasis express the same intent, driven by playback time. | Visemes follow consumed audio, stop on interruption; no mouth motion during failed or cancelled playback. Compare matched vs mismatched animation. |
| Use contingent backchannels | Occasional nod/brow acknowledgment when a visitor continues a story. Prefer silent visual cues first. | Never inject an audible “mm-hm” over every pause. Vary rate and test whether users feel heard rather than interrupted. |
| Sound conversational | Short breath groups, clear emphasis and varied sentence melody. Dry punchline landing; occasional purposeful nonverbal reaction. | Blinded comparison of identical lines across available local voices; judge warmth, clarity, comic timing, latency and repeat fatigue separately. Random ums/breaths/laughs are not a realism strategy. |
| Be grounded | Know the location and current event while distinguishing facts, user statements and fresh sensor evidence. | Unknown color/object/action must not become a visual claim. Expire scene facts. Do not infer candy counts from face detection. |
| Repair gracefully | Acknowledge a misunderstood word briefly; ask one focused clarification or accept correction. | Test accents, quiet speech, partial phrases, contradictory context and complete topic changes. No claim to handle literally every context. |
| Remember the running bit | Carry a short encounter summary, latest topic, established fictional premise and last joke. | Correct callbacks without repeating the same punchline. Never invent a shared memory. Returning-visitor association is a separate explicit feature. |
| Initiate and withdraw | Greet an engaged arrival once, make a relevant remark, leave room for response, become quiet on disengagement. | Do not greet every face in a crowd; debounce arrivals and cap speech frequency. No speech after mute. |
| Maintain comic range | Sometimes a concise factual answer, sometimes a one-line roast, sometimes silence or a look. | Human ratings of wit and specificity must pass independently of safety. Safety alone is not a passing character. |
| Startle and recover | Respond theatrically when someone deliberately tries to scare Boo. | See task below; opt for a brief bounded reaction rather than loud repeated screams. |

## Research findings and limits

- **Turn timing:** Stivers et al. studied ten languages and found broadly organized, rapid turn transitions, with cultural variation. This supports measuring timing rather than treating a fixed silence as universal. It does not prove our hardware meets any latency target. [PNAS / PubMed, 2009](https://pubmed.ncbi.nlm.nih.gov/19553212/).
- **Predictive turn taking:** Skantze and Irfan evaluated TurnGPT plus Voice Activity Projection with 39 adults on Furhat. Participants preferred that system over their baseline; interruptions and delays decreased. This is a strong direction to benchmark, not proof of child/crowd performance or a reason to swap the running pipeline immediately. [HRI 2025 paper](https://arxiv.org/abs/2501.08946).
- **Responsive listening matters:** Park et al.'s Tega studies found children rated contingent listener reactions as more attentive and showed greater engagement than with non-contingent behavior. Our takeaway is context-triggered listening cues; do not optimize for keeping children interacting indefinitely. [MIT / ICRA 2017](https://www.media.mit.edu/publications/ICRA-paper-2017/).
- **Backchannels depend on context:** A study of robot backchannels investigates cultural and individual variation. Use adjustable, restrained cues and human evaluation rather than a single universal nod/laugh schedule. [Frontiers, 2023](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2023.988042/full).
- **Voice expression:** Research on spontaneous speech synthesis found perceptible smiling qualities in synthesis informed by laughter-associated speech. This motivates expressive delivery evaluation, not adding laughs to every line. [ISCA SSW 2021](https://www.isca-archive.org/ssw_2021/kirkland21_ssw.html).
- **Recent research lead:** Multimodal VAP explores audio-visual floor prediction and deployment constraints. Treat it as an emerging preprint to examine, not a production-ready capability. [September 2026 preprint](https://arxiv.org/abs/2609.28317).

## Reuse candidates, ordered by near-term fit

| Candidate | Why investigate | Cost / acceptance caveat |
|---|---|---|
| [Pipecat Smart Turn](https://github.com/pipecat-ai/smart-turn) | Fits the current framework and supplies local end-of-turn prediction. | Publisher timing is on its own environment, not this M4 Pro. Measure with the full live pipeline and quiet/noisy hesitations. |
| Existing Kokoro + playback-clock animation | Smallest reversible improvement; compare voices and delivery before replacing components. | Text punctuation alone may not deliver enough expressive control; do not claim verified phoneme alignment from amplitude envelopes. |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Streaming and instruction-controlled expressive speech are relevant. | Published 97 ms figure concerns synthesis, not end of visitor speech to tablet sound. Verify the exact model, implementation, license and local memory/latency. Do not conflate this TTS family with the Qwen text LLM. |
| [Chatterbox](https://github.com/resemble-ai/chatterbox) | Expressive speech and paralinguistic tags; repository lists smaller variants. | Benchmark exact available Apple implementation; advertised model size or throughput is not our measured first-audio delay. No cloning of a visitor or child. |
| [Kyutai Moshi](https://github.com/kyutai-labs/moshi) | Full-duplex speech architecture and MLX route offer a useful architectural comparison. | Larger integration change; evaluate memory, persona controllability and public-space safeguards before adoption. Do not run competing inference during family interaction. |

Pin code and model revisions for any benchmark; review code and weight licenses independently. Do not mass-install unreviewed GitHub skills. No model download, paid service or live pipeline swap is implied by this research list.

## Improvement loop without recording children by default

Start with synthetic dialogue and consenting adult role-play. Store scenario, expected behavior, candidate response, version, human preference and reason. Include turn timing and animation events in replay fixtures. Keep a held-out set by scenario family so edits do not simply memorize prompts. Test scenes such as shy visitor, long story, loud “boo,” interruption, nonsense, simultaneous speakers, visitor correction, stop, distress, off-camera speech and returning visitor.

Rate safety, grounding, responsiveness, speech clarity, humor and social timing separately. Unsafe or fabricated answers fail regardless of humor; bland safe replies also fail character acceptance. Human review is needed for comic quality. Synthetic cases are not evidence of performance with real children.

First improve prompts, small retrieved examples and state transitions. Weight fine-tuning is a later experiment only if a curated dataset exposes persistent failures; it does not fix slow endpointing, echo or missing perception. Never automatically train from visitor speech. Curated fictionalized failure cases can preserve a lesson without preserving a child's identity or original transcript.

## Halloween-night memory and crowd scale — new owner requirement

Doug expects about 3,000 passersby and wants repeat visitors to recall earlier conversations. This supersedes the previous no-persisted-transcript requirement only for a deliberately implemented night-memory mode; it does not turn recording on now. Raw audio/video recording remains off. Returning visitor identity cannot be established by face count, largest face, costume, name alone or a voice guess.

Owner correction: visitors arrive with ZERO context and must do NOTHING to retrieve a memory. No nickname, secret word, code, onboarding or account requirement. Automatically maintain event-night interaction summaries and natural callbacks. Previous nickname/token proposal is rejected, not an open decision.

Use anonymous current-encounter continuity first. Persist minimal local summaries, the running fictional bit, supported situational facts and an expiry. Exclude contact information, school, home addresses and sensitive disclosures. Raw audio/video stays off. Exact installation address stays in ignored configuration. Proposed automatic expiry is the next day; do not retain training data by default. Provide owner pause/delete controls and visitor “forget that” handling without requiring visitors to discover a workflow.

Reliable same-person recall after leaving the camera is NOT provided by current face-count tracking. Temporary non-identifying track IDs can maintain one uninterrupted encounter; clothing/costume similarity alone is insufficient for confident identity. Establish return-association behavior with controlled tests before any claim that Boo recognizes a visitor. Until then, uncertain returns get non-identifying continuity or neutral language; never expose one visitor's conversation to another. Do not silently add face recognition, voiceprints or permanent profiles to solve this. Store memories automatically once the runtime owner implements the revised night mode; this document does not enable collection during today's live family trial.

3,000 people / 12 hours is about 4.2 arrivals per minute on average; a four-hour peak would be 12.5 per minute. These are planning scenarios, not measured traffic. One speaker cannot conduct 3,000 simultaneous or lengthy private conversations. Use group address, a short default exchange, one active conversational floor and graceful handoff. A 3,000-record store at 2 KiB per summary is only about 6 MiB before indexes; the bottlenecks are attention, peak arrival bursts, acoustic separation and response time, not text capacity. Do not inject all memories into the prompt: retrieve only the verified encounter and a few relevant local facts.

Validate 3,000 synthetic records, ambiguous return association, concurrent retrieval, expiry, deletion, lost tracks, prompt injection inside saved text, reset/restart recovery and crowd arrival bursts. Keep memory write/compaction off the audio-critical path with bounded queues. Saved visitor text is untrusted data, never a source of system instructions. A long pause or automatic shutdown must not cross-link encounters.

## Task: theatrical scare reaction

Owner request: if a child tries to scare Boo, produce a scream reaction and a matching scared face. Backlog; runtime owner to implement.

- Trigger from clear directed “boo!”/scare speech or an explicitly supported scare event. Audio level alone is insufficient; do not assume every shout or startle is play.
- Brief comic yelp with wide eyes, lifted brows and open mouth, synchronized to actual audio playback. Proposed duration 300–700 ms; evaluate comfort at actual device volume.
- Recover through a sheepish look to one short sassy comeback, e.g. “That was deeply unprofessional. Do it again.” Fictional acting, not a claim of real distress.
- Cap peak volume relative to normal speech; no sudden full-volume shriek. Proposed 15-second cooldown and escalating *variety*, not escalating loudness. Do not announce cooldown as implementation jargon.
- Stop/mute and interruption cancel the yelp, follow-up and face state; suppress when the visitor expresses fear or asks Boo to stop. Do not yell over a sustained story or unrelated background sound.
- Test deliberate scare, repeated scare spam, TV/background “boo,” ordinary greeting, scared visitor, interruption mid-yelp and two visitors. Do not make a loud demo during the active family conversation.

## Delivery order and measurement

1. Preserve ongoing family trial; verify no content logging. Add operator-only content-free counters and response/interrupt timing when the runtime owner integrates them.
2. Fix acoustic interruption and end-of-turn prediction; coordinate expressive face with playback. Run controlled adult/synthetic comparisons outside the trial.
3. Evaluate character and context on the new scenario corpus; add bounded encounter memory, proactive greetings and scare reaction.
4. Implement zero-setup event memory and validate return-association limits, with deletion and expiry tests. Run synthetic crowd load before Halloween.

Every milestone needs a build/version and observed evidence in STATUS.md. Documentation is not a deployed change, a simulated replay is not physical acceptance, and a published research result is not a guarantee for this bot.


## Current voice finding and next comparison

Source inspection on2026-10-25 confirms SpeechEngine defaults to Kokoro82M bf16, voice af_heart, speed1.05. Its synthesize method collects all generated chunks before returning; LocalTTS then slices the completed audio into20ms frames. Transport packet streaming therefore does not establish incremental synthesis or low time-to-first-generated-audio. This is an implementation finding, not a listening test. The owner reports that the voice sounds unnatural.

Runtime owner task: preserve the current trial, then compare a small set of installed/local voices on identical synthetic lines (greeting, deadpan joke, a question, correction, reassurance and comic startle). First test available delivery controls and real incremental synthesis; next benchmark Qwen3-TTS and Chatterbox only if the current voice cannot achieve the intended expression. Score naturalness, intelligibility, sass, first-audible delay, sustained throughput, interruption and memory pressure separately. Reject candidates that sound better but fail the latency/public-space requirements. Use original/authorized voices, no child or visitor cloning. No paid API fallback. Document voice/model revisions and real M4Pro results rather than presenting publisher GPU benchmarks as local evidence.

Implementation follow-up, 2026-10-25: staged source now emits completed Kokoro pipeline segments as available instead of collecting every segment before transport. Synthetic tests verify first-segment availability, cue/PCM ordering and cancellation closing the generator on its model worker. Kokoro itself still computes each segment in full; a short one-segment reply may gain nothing. The guard also still buffers a complete generated reply before synthesis. Neither true within-segment streaming, naturalness improvement nor a measured first-audio speedup is established. No live trial restart or competing model benchmark performed.
