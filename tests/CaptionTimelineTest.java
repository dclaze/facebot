package org.facebot;
import java.util.Arrays;
import java.util.Collections;
public final class CaptionTimelineTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    static CaptionTimeline.Cue cue(long a,long b,String text){return new CaptionTimeline.Cue(a,b,text);}
    static void rejects(Runnable action){try{action.run();throw new AssertionError("accepted invalid caption");}catch(IllegalArgumentException expected){}}
    public static void main(String[] args){
        CaptionTimeline t=new CaptionTimeline();t.reset(2);
        t.append(2,24000,Arrays.asList(cue(0,12000,"First phrase"),cue(12000,24000,"Next phrase")));
        check(t.textAt(23999).isEmpty());check(t.textAt(24000).equals("First phrase"));
        check(t.textAt(36000).equals("Next phrase"));check(t.textAt(48000).isEmpty());
        t.append(2,48000,Arrays.asList(cue(0,10,"One"),cue(20,30,"After silence")));
        check(t.textAt(48010).isEmpty());check(t.textAt(48020).equals("After silence"));
        t.reset(3);t.append(2,0,Arrays.asList(cue(0,100,"Stale")));check(t.textAt(0).isEmpty());
        t.append(3,0,Arrays.asList(cue(0,100,"Current")));
        rejects(()->t.append(3,10,Arrays.asList(cue(0,100,"Overlap"))));
        rejects(()->t.append(3,Long.MAX_VALUE,Arrays.asList(cue(0,100,"Overflow"))));
        rejects(()->t.append(3,100,Arrays.asList(cue(0,10,"Valid"),cue(5,20,"Invalid"))));
        check(t.textAt(99).equals("Current"));check(t.textAt(100).isEmpty());
        rejects(()->t.append(3,100,Arrays.asList(cue(0,10,"x".repeat(161)))));
        rejects(()->t.append(3,100,Arrays.asList(cue(0,10,"a\nb"))));
        rejects(()->t.append(3,0,Collections.nCopies(513,cue(0,1,"Too many"))));
        t.reset(4);t.append(4,0,Arrays.asList(cue(0,2880000,"🙂".repeat(160))));
        check(!t.textAt(2879999).isEmpty());check(t.textAt(2880000).isEmpty());
        t.reset(5);check(t.textAt(0).isEmpty());
        System.out.println("CaptionTimeline tests passed: audio boundaries, silence, interrupt, stale epochs, atomic validation and bounds");
    }
}
