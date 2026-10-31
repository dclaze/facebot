"""Narrow VAD calibration for the Lenovo raw-capture compatibility profile."""
import time
import numpy as np
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams, VADState

LENOVO_RAW_CAPTURE = 'lenovo-j606f-raw-v1'


class CaptureVAD(SileroVADAnalyzer):
    def __init__(self, capture_profile=''):
        self.capture_profile = LENOVO_RAW_CAPTURE if capture_profile == LENOVO_RAW_CAPTURE else 'default'
        self.confidence_gain = 4 if self.capture_profile == LENOVO_RAW_CAPTURE else 1
        self._metrics = {'input_frames': 0, 'input_samples': 0, 'analysis_frames': 0,
                         'last_confidence': 0.0, 'max_confidence': 0.0,
                         'last_volume': 0.0, 'max_volume': 0.0,
                         'candidate_frames': 0, 'speech_starts': 0, 'speech_stops': 0,
                         'state': 'quiet', 'last_input_at': None,
                         'last_candidate_at': None, 'last_start_at': None, 'last_stop_at': None}
        self._snapshot = dict(self._metrics)
        self._stable_state = VADState.QUIET
        super().__init__(params=VADParams(start_secs=.1, stop_secs=.45))

    def voice_confidence(self, buffer):
        # Raw VOICE_RECOGNITION on this exact profile has much lower amplitude
        # than the old vendor-processed path. Calibrate only the detector input;
        # volume gating, stored/transmitted PCM and ASR retain the original.
        if self.confidence_gain != 1:
            samples = np.frombuffer(buffer, dtype='<i2').astype(np.float32)
            buffer = np.clip(samples * self.confidence_gain, -32768, 32767).astype('<i2').tobytes()
        confidence = super().voice_confidence(buffer)
        value = float(np.asarray(confidence).reshape(-1)[0])
        self._metrics['analysis_frames'] += 1
        self._metrics['last_confidence'] = value
        self._metrics['max_confidence'] = max(self._metrics['max_confidence'], value)
        return confidence

    def _get_smoothed_volume(self, audio):
        volume = super()._get_smoothed_volume(audio)
        self._metrics['last_volume'] = float(volume)
        self._metrics['max_volume'] = max(self._metrics['max_volume'], float(volume))
        if self._metrics['last_confidence'] >= self.params.confidence and volume >= self.params.min_volume:
            self._metrics['candidate_frames'] += 1
            self._metrics['last_candidate_at'] = time.monotonic()
        return volume

    def _run_analyzer(self, buffer):
        state = super()._run_analyzer(buffer)
        now = time.monotonic()
        self._metrics['input_frames'] += 1
        self._metrics['input_samples'] += len(buffer) // 2
        self._metrics['last_input_at'] = now
        self._metrics['state'] = state.name.lower()
        # Match the controller's stable-state transitions; STOPPING -> SPEAKING
        # is continuation, not a new utterance. No PCM or transcript is retained.
        if state in (VADState.QUIET, VADState.SPEAKING) and state != self._stable_state:
            self._stable_state = state
            key = 'start' if state == VADState.SPEAKING else 'stop'
            self._metrics[f'speech_{key}s'] += 1
            self._metrics[f'last_{key}_at'] = now
        # Worker owns mutable metrics; the event loop reads one complete snapshot.
        self._snapshot = dict(self._metrics)
        return state

    def report(self):
        now = time.monotonic()
        metrics = dict(self._snapshot)
        for name in ('input', 'candidate', 'start', 'stop'):
            at = metrics.pop(f'last_{name}_at')
            metrics[f'last_{name}_age_s'] = None if at is None else round(max(0.0, now - at), 3)
        return {'activity': metrics, 'capture_profile': self.capture_profile, 'confidence_gain': self.confidence_gain,
                'confidence': self.params.confidence, 'min_volume': self.params.min_volume,
                'start_secs': self.params.start_secs, 'stop_secs': self.params.stop_secs}
