package org.facebot;
public final class KioskStatusTest {
    static void check(boolean ok){if(!ok)throw new AssertionError();}
    public static void main(String[] args){
        KioskStatus state=new KioskStatus();check(state.readyText().equals("Listening"));
        check(state.apply(4,4,true));
        for(int i=0;i<100;i++)check(state.readyText().equals("Quiet mode"));
        check(!state.apply(3,4,false));check(state.readyText().equals("Quiet mode"));
        check(!state.apply(5,4,false));check(!state.apply(-1,-1,false));
        check(state.apply(5,5,false));check(state.readyText().equals("Listening"));
        check(state.apply(5,5,true));state.reset();check(state.readyText().equals("Listening"));
        // Actual cackle screenshot regression: captionless wolf-eyes must not invite
        // speech merely because the transport posts its normal ready/Listening tick.
        PerformanceFaceCue cackle=new PerformanceFaceCue();cackle.set(6,0,24000,"wolf_eyes");
        for(long head:new long[]{1,12000,23999}) {
            check(cackle.at(6,head,24000).equals("wolf_eyes"));
            check(KioskStatus.visitorText(state.readyText(),false,head<24000).equals("Performing"));
        }
        check(cackle.at(6,24000,24000).isEmpty());
        check(KioskStatus.visitorText(state.readyText(),false,false).equals("Say hello"));
        check(KioskStatus.visitorText("Listening",true,true).equals("Speech paused · tap Resume"));
        check(state.apply(6,6,true));
        check(KioskStatus.visitorText(state.readyText(),false,true).equals("Quiet mode"));
        check(KioskStatus.visitorText("Reconnecting",false,true).equals("One moment… reconnecting"));
        System.out.println("KioskStatusTest passed: mute survives ready ticks, stale epoch rejected, resume and close reset");
    }
}
