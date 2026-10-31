package org.facebot;

/** App-local workload policy; no system settings or audio behavior are changed. */
final class ThermalCadence {
    private volatile int status;
    private long lastAnalysisMs=Long.MIN_VALUE; // Only the analysis executor writes this.

    void setStatus(int value) { if(value>=0 && value<=6) status=value; }
    int analysisIntervalMs() { return status>=4 ? 200 : status>=3 ? 100 : 0; }
    // Minimum requested spacing; vsync alignment may lower the actual redraw rate.
    int redrawDelayMs() { return status>=4 ? 67 : status>=3 ? 33 : 0; }
    boolean analyzeNow(long nowMs) {
        int interval=analysisIntervalMs();
        if(lastAnalysisMs!=Long.MIN_VALUE && nowMs>=lastAnalysisMs && nowMs-lastAnalysisMs<interval) return false;
        lastAnalysisMs=nowMs;
        return true;
    }
    static float gazeBlend(double elapsedMs) {
        // Preserve the former .18 blend at 60Hz, independently of draw cadence.
        double frames=Math.max(0,Math.min(250,elapsedMs))/(1000.0/60.0);
        return (float)(1-Math.pow(.82,frames));
    }
}
