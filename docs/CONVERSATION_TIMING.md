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

## Current instrumentation and replay — 2026-10-25

The owner-authenticated `/diagnostics` endpoint keeps at most 64 numeric stage records in memory. It accepts the same Bearer pairing authorization as the voice connection; do not publish that token. It records detector speech stop, final transcription, LLM request/first text/completion, synthesis start and first PCM. No speech text, names, audio or images are retained by the timing collector. These are server boundaries, not actual acoustic endpoints; VAD-stop time excludes the detector’s preceding endpoint wait. Proactive replies without a user-turn anchor are excluded. Incomplete turns are counted separately.

A fresh synthetic network replay of “Hey Boo, do you hear me?” received first PCM 1699.24 ms after synthetic input end; explicit interrupt round-trip was 3.56 ms. This single replay is neither physical audible latency nor a p50/p95 estimate. Two server-stage records during the check measured first LLM text at1056–1111 ms after request and first synthesis PCM at112–329 ms after synthesis start. Stage and replay clocks have different anchors. The old1749.3 ms replay remains historical.

`FACEBOT_SPEECH_RATE` selects Kokoro delivery speed, validated from0.8 through1.3. The owner-requested trial uses1.12 versus the prior1.05; this is about6.7% faster speaking, not a6.7% reduction in response delay. Timing cues come from synthesis at the selected speed; physical intelligibility and lip-sync still need validation.
