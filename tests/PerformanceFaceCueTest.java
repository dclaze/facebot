package org.facebot;
public class PerformanceFaceCueTest {
    static void check(boolean ok){if(!ok)throw new AssertionError();}
    public static void main(String[] args){
        PerformanceFaceCue cue=new PerformanceFaceCue();cue.set(7,2400,48000,"wolf_eyes");
        check(cue.at(7,2399,2500).isEmpty());check(cue.at(7,2400,2500).equals("wolf_eyes"));
        check(cue.at(7,3000,3000).isEmpty());check(cue.at(7,50400,51000).isEmpty());check(cue.at(8,2500,3000).isEmpty());
        cue.reset();check(cue.at(7,2500,3000).isEmpty());
        try{cue.set(1,Long.MAX_VALUE,4,"wolf_eyes");throw new AssertionError();}catch(IllegalArgumentException expected){}
        try{cue.set(1,0,24000L*121,"wolf_eyes");throw new AssertionError();}catch(IllegalArgumentException expected){}
        System.out.println("PerformanceFaceCueTest passed: PCM timing, starvation, epoch, clear, bounds");
    }
}
