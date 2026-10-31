"""Narrow VAD calibration for the Lenovo raw-capture compatibility profile."""
import numpy as np
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

LENOVO_RAW_CAPTURE = 'lenovo-j606f-raw-v1'


class CaptureVAD(SileroVADAnalyzer):
    def __init__(self, capture_profile=''):
        self.capture_profile = LENOVO_RAW_CAPTURE if capture_profile == LENOVO_RAW_CAPTURE else 'default'
        self.confidence_gain = 4 if self.capture_profile == LENOVO_RAW_CAPTURE else 1
        super().__init__(params=VADParams(start_secs=.1, stop_secs=.45))

    def voice_confidence(self, buffer):
        # Raw VOICE_RECOGNITION on this exact profile has much lower amplitude
        # than the old vendor-processed path. Calibrate only the detector input;
        # volume gating, stored/transmitted PCM and ASR retain the original.
        if self.confidence_gain != 1:
            samples = np.frombuffer(buffer, dtype='<i2').astype(np.float32)
            buffer = np.clip(samples * self.confidence_gain, -32768, 32767).astype('<i2').tobytes()
        return super().voice_confidence(buffer)

    def report(self):
        return {'capture_profile': self.capture_profile, 'confidence_gain': self.confidence_gain,
                'confidence': self.params.confidence, 'min_volume': self.params.min_volume,
                'start_secs': self.params.start_secs, 'stop_secs': self.params.stop_secs}
