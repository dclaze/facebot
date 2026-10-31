package org.facebot;

import java.util.function.BooleanSupplier;

/** Synchronous frame ownership: snapshot first, then hand off or release. Never queues a frame. */
final class AnalysisFrameGate {
    static void dispatch(boolean active, Runnable snapshot, BooleanSupplier allowAnalysis,
                         Runnable submitAnalysis, Runnable close) {
        boolean handedOff=false;
        try {
            if(!active) return;
            snapshot.run(); // Copies pixels if due; must finish before any close.
            if(!allowAnalysis.getAsBoolean()) return;
            submitAnalysis.run(); // MlKitAnalyzer owns closing after a successful handoff.
            handedOff=true;
        } finally {
            if(!handedOff) close.run();
        }
    }
}
