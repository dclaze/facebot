package org.facebot;
public final class QuietControlStateTest {
    private static void check(boolean value,String message) { if(!value) throw new AssertionError(message); }
    public static void main(String[] args) {
        QuietControlState state=new QuietControlState();
        check(state.status("Listening",false).equals("Say hello"),"idle guidance must agree with the face invitation");
        check(state.status("Listening",true).equals("Speak after the face finishes"),"ready ticks during playback cannot invite speech");
        for(String busy:new String[]{"Processing","Thinking","Connecting","Reconnecting","Muted","",null})
            check(state.status(busy,false).startsWith("One moment"),"busy or unknown state must not invite speech");
        check(state.status("Quiet mode",true).equals("Quiet mode · tap Resume"),"server Quiet state precedes playback");
        int stop=state.begin(true);
        check(state.status("Listening",true).equals("Pausing…"),"pending stop precedes playback guidance");
        check(state.localHold && state.pending && !state.serverMuted,"quiet must mute before host confirms");
        state.serverState(false);
        check(state.localHold,"stale listening cannot undo pending local stop");
        state.complete(stop,false);
        check(state.localHold && state.status("Listening",false).contains("not confirmed"),"failure remains locally silent and truthful");
        int resume=state.begin(false);
        check(state.status("Listening",false).equals("Resuming…"),"pending resume cannot invite speech before confirmation");
        check(state.localHold,"resume waits for acknowledgement");
        state.complete(resume,false);
        check(state.localHold,"failed resume cannot produce sound");
        int retry=state.begin(false);
        check(!state.complete(resume,true) && state.localHold,"stale callback cannot resume");
        state.complete(retry,true);
        check(!state.localHold && !state.serverMuted,"confirmed resume releases hold");
        check(state.status("Listening",false).equals("Say hello"),"confirmed idle resume restores invitation");
        stop=state.begin(true);state.complete(stop,true);
        check(state.serverMuted && state.localHold,"confirmed stop");
        check(state.status("Listening",true).equals("Quiet mode · tap Resume"),"confirmed Quiet retains existing guidance");
        state.serverState(false);
        check(!state.localHold,"spoken or external resume after quiet releases local hold");
        stop=state.begin(true);state.cancelPending();
        check(!state.complete(stop,true) && state.localHold,"reconnect preserves immediate hold and rejects old callback");
        System.out.println("QuietControlStateTest passed");
    }
}
