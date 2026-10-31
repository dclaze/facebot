package org.facebot;

/** Server output mute survives normal playback-ready notifications, not reconnects. */
final class KioskStatus {
    private volatile boolean muted;
    boolean apply(long incoming,long current,boolean nextMuted) {
        if(incoming<0 || incoming!=current) return false;
        muted=nextMuted;return true;
    }
    String readyText(){return muted ? "Quiet mode" : "Listening";}
    void reset(){muted=false;}
}
