# Skill: Costume Dad Joke

Status: requested behavior contract; not installed runtime logic. Owned by the Android & iOS apps implementation chat. Activate through the Halloween event context or another explicitly selected costume event, never as a permanent core-app assumption.

## Intent

Deliver one relevant, original dad joke when an engaged visitor's costume provides a natural opening. Keep the delivery extremely sassy, playful and kid-safe. Visitors need no prior context and do not need to ask for the skill. A joke should feel like a reaction to them, not a random playlist.

## Inputs and grounding

- Fresh, confidence-qualified costume evidence from an implemented vision capability, OR the visitor's explicit costume statement.
- Current encounter/topic, conversational floor, recent jokes and mute/stop state.
- Relevant verified local fact if it naturally improves the joke.

Current camera processing detects faces; it does NOT identify costumes. Until costume recognition is implemented and tested, use spoken costume context only. Do not infer identity, age, gender, ethnicity, disability or mood from appearance. A person can wear a costume without consenting to personal ridicule.

## Decision

1. If muted, interrupted, empty, disengaged or dealing with genuine distress/help, suppress.
2. If costume evidence is absent/ambiguous, do not claim to see a specific costume. Continue the existing topic, use a broad greeting or ask a short natural question only when helpful.
3. If the visitor is speaking or another joke just landed, wait for the floor. Do not queue stale jokes to burst out later.
4. Select one concise costume-relevant joke from reviewed candidates. Prefer a locally grounded variant only when it makes sense. Exclude recent repetition within the encounter and bound global repetition during crowds.
5. Coordinate a restrained brow/gaze/mouth expression with the spoken setup and punchline. Leave space after it. No explanation of why it is funny unless asked.
6. If the visitor corrects the costume, accept the correction and move on. Do not argue from model confidence.

## Original tone example

Visitor says “I'm a bat.” Boo: “Excellent. Someone finally dressed for the night shift.”

This is a reference example, not a permanent stock reply or a claim of camera recognition. The dedicated local-joke research chat owns the larger reviewed corpus and stronger alternatives.

## Acceptance

Test bat vs cat ambiguity, visitor-provided bat context, a corrected costume, unknown costume, two differently dressed visitors, repeated arrivals, speech overlap, repeated-joke suppression, stop, fear and an off-topic question. Validate humor separately from safety and grounding. No raw visitor media or transcripts are required to test with synthetic scenes and adult role-play.
