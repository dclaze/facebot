package org.facebot;

/** Local silence is immediate; host persistence is reported only after confirmation. */
final class QuietControlState {
    boolean localHold, serverMuted, pending, failed;
    private boolean requestedQuiet;
    private int request;
    int begin(boolean quiet) {
        pending=true; failed=false; requestedQuiet=quiet;
        if(quiet) localHold=true;
        return ++request;
    }
    boolean complete(int id, boolean success) {
        if(id!=request || !pending) return false;
        pending=false; failed=!success;
        if(success) { serverMuted=requestedQuiet; localHold=requestedQuiet; }
        return true;
    }
    void serverState(boolean muted) {
        boolean resumed=serverMuted && !muted;
        serverMuted=muted;
        if(!pending && resumed) { localHold=false; failed=false; }
    }
    void cancelPending() {
        if(pending) failed=true;
        pending=false; ++request; // Ignore callbacks from the old owner connection.
    }
    String status(String voiceState,boolean outputPlaying) {
        if(pending) return requestedQuiet ? "Pausing…" : "Resuming…";
        if(failed) return localHold ? "Paused here · host not confirmed" : "Host not reached · try again";
        if(serverMuted || "Quiet mode".equals(voiceState)) return "Quiet mode · tap Resume";
        if(localHold) return "Paused here · tap Resume";
        if(outputPlaying) return "Speak after the face finishes";
        if("Listening".equals(voiceState)) return "Say hello";
        if("Connecting".equals(voiceState) || "Reconnecting".equals(voiceState))
            return "One moment… reconnecting";
        // Pending/unknown transport work must not become a speaking invitation.
        return "One moment…";
    }
}
