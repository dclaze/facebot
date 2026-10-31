package org.facebot;

/** Server output mute survives normal playback-ready notifications, not reconnects. */
final class KioskStatus {
    private volatile boolean muted;
    boolean apply(long incoming,long current,boolean nextMuted) {
        if(incoming<0 || incoming!=current) return false;
        muted=nextMuted;return true;
    }
    String readyText(){return muted ? "Quiet mode" : "Listening";}
    static String visitorText(String state,boolean localHold,boolean outputPlaying) {
        if(localHold) return "Speech paused · tap Resume";
        if(state.equals("Listening")) return outputPlaying ? "Performing" : "Say hello";
        if(state.equals("Reconnecting") || state.equals("Connecting")) return "One moment… reconnecting";
        return state;
    }
    void reset(){muted=false;}
}
