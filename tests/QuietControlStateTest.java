package org.facebot;
public final class QuietControlStateTest {
    private static void check(boolean value,String message) { if(!value) throw new AssertionError(message); }
    public static void main(String[] args) {
        QuietControlState state=new QuietControlState();
        int stop=state.begin(true);
        check(state.localHold && state.pending && !state.serverMuted,"quiet must mute before host confirms");
        state.serverState(false);
        check(state.localHold,"stale listening cannot undo pending local stop");
        state.complete(stop,false);
        check(state.localHold && state.status().contains("not confirmed"),"failure remains locally silent and truthful");
        int resume=state.begin(false);
        check(state.localHold,"resume waits for acknowledgement");
        state.complete(resume,false);
        check(state.localHold,"failed resume cannot produce sound");
        int retry=state.begin(false);
        check(!state.complete(resume,true) && state.localHold,"stale callback cannot resume");
        state.complete(retry,true);
        check(!state.localHold && !state.serverMuted,"confirmed resume releases hold");
        stop=state.begin(true);state.complete(stop,true);
        check(state.serverMuted && state.localHold,"confirmed stop");
        state.serverState(false);
        check(!state.localHold,"spoken or external resume after quiet releases local hold");
        stop=state.begin(true);state.cancelPending();
        check(!state.complete(stop,true) && state.localHold,"reconnect preserves immediate hold and rejects old callback");
        System.out.println("QuietControlStateTest passed");
    }
}
