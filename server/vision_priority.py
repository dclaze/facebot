"""Best-effort voice priority for NEW vision work; never queue camera frames."""


class VisionPriority:
    QUIET_GRACE_SECONDS = .3

    def __init__(self, state):
        self.state = state
        # Leave part of the freshness budget for the next real inference.
        # This is a scheduling cap, not a promise that inference meets the TTL.
        self.max_deferral_seconds = state.TTL / 2
        self.deferred_since = None
        self.interaction = None

    def should_defer(self, interaction):
        now = self.state.clock()
        if interaction is not self.interaction:
            self.interaction = interaction
            self.deferred_since = None
        reason = self._reason(interaction, now)
        if reason is None:
            self.deferred_since = None
            return False
        if self.deferred_since is None:
            self.deferred_since = now
        if now >= self.deferred_since + self.max_deferral_seconds:
            self.deferred_since = None
            self.state.priority_refreshes += 1
            return False
        self.state.deferred_frames += 1
        self.state.last_defer_reason = reason
        return True

    def _reason(self, interaction, now):
        if interaction is None:
            return None
        stt = getattr(interaction, 'stt', None)
        if stt is not None and stt.inference_active:
            return 'speech_recognition'
        if interaction.user_speaking:
            return 'visitor_speaking'
        if interaction.bot_speaking or interaction.response_pending:
            # response_pending covers response routing and synthesis before
            # the first BotStartedSpeakingFrame arrives from the transport.
            return 'response_or_playback'
        ended = max(interaction.last_activity,
                    getattr(stt, 'last_inference_finished', float('-inf')))
        if now - ended < self.QUIET_GRACE_SECONDS:
            return 'quiet_grace'
        return None
