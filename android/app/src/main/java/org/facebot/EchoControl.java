package org.facebot;

/** Narrow workaround for an observed Lenovo Android 11 vendor AEC crash. */
final class EchoControl {
    // Includes capture-buffer delay and a room-echo tail; not measured acoustic latency.
    static final long TAIL_MS = 600;
    final boolean halfDuplex;
    private long silenceUntil;

    EchoControl(boolean halfDuplex) { this.halfDuplex = halfDuplex; }

    static boolean needsHalfDuplex(String manufacturer, String model, int sdk) {
        return sdk == 30 && "lenovo".equalsIgnoreCase(manufacturer)
            && ("Lenovo TB-J606F".equalsIgnoreCase(model) || "TB-J606F".equalsIgnoreCase(model));
    }

    // Called before playback can consume accepted PCM, and while its head trails writes.
    // Access is serialized with VoiceClient's audioLock, including interruption/flush.
    void outputActivity(long now) {
        if (halfDuplex) silenceUntil = Math.max(silenceUntil, now + TAIL_MS);
    }

    boolean silenceCapture(long now, boolean outputPending) {
        if (!halfDuplex) return false;
        if (outputPending) outputActivity(now);
        return now < silenceUntil;
    }
}
