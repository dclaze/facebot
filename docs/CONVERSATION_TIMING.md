# Human conversational timing target

Owner requested human response timing as Facebot’s target on 2026-10-25.

## Evidence

[Stivers et al. (2009), Universals and cultural variation in turn-taking in conversation](https://pmc.ncbi.nlm.nih.gov/articles/PMC2705608/) studied question–response sequences across ten languages. The cross-language mean gap was 208 ms, median 100 ms; each language’s distribution peaked between 0 and 200 ms. Individual and cultural variation exists, and question type affects timing. These are observed conversational timings, not a universal threshold guaranteeing that an AI feels natural.

[Levinson and Torreira (2015), Timing in turn-taking and its implications for processing models of language](https://pmc.ncbi.nlm.nih.gov/articles/PMC4464110/) explains the gap between roughly 200 ms turn transitions and speech-production latencies exceeding 600 ms: listeners prepare responses while the other person is still speaking and predict turn endings.

## Binding Facebot acceptance target

- Median <=200 ms from actual visitor utterance end to first meaningful audible generated response.
- p95 <=500 ms over a representative physical-device test set. This tail limit is an engineering choice, not a percentile established by the cited research.
- Keep visible attention p95 <=200 ms and barge-in p95 <=250 ms as separate requirements.
- No cached filler, generic acknowledgement, animation, or pre-recorded greeting counts as generated-response success.
- Include endpointing, STT, language inference, output checks, TTS, transport, and actual speaker buffering. Timestamping the server’s final transcript instead of actual utterance end is invalid.
- Measure Android and iOS separately. Include varied question lengths, unpredictable final words, mid-sentence pauses, corrections, interruption, background noise and concurrent Mac workloads. Report sample size, failures, full distribution, early starts/overlap and false interruptions alongside latency; do not discard slow successful turns.
- A prepared response may be generated while listening, but must be invalidated if the visitor changes or extends the utterance. Premature speech cannot improve the success metric. Label intended backchannels separately.
- Fast but irrelevant, unsafe, repeatedly interrupted or unnatural-sounding output does not satisfy conversational acceptance. Human-like voice quality and turn appropriateness remain required.

## Implementation consequence

The current segmented-STT → complete sentence → TTS prototype is a baseline, not the final latency architecture. Its 250 ms silence detector alone exceeds the median target. Evaluate incremental transcription, response preparation before turn-end, cancellation of outdated work, streaming synthesis and/or mature local full-duplex speech-to-speech components. Do not silently relax the target if this hardware fails it; record the remaining gap.

The earlier 1 s median / 1.5 s p95 proposal is superseded, not an alternative passing tier. Current measured 9B text-to-PCM timing does not pass even that earlier target.
