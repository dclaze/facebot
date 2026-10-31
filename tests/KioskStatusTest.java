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
        System.out.println("KioskStatusTest passed: mute survives ready ticks, stale epoch rejected, resume and close reset");
    }
}
