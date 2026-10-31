package org.facebot;
public final class PerformanceVideoCueTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    static void rejects(Runnable action){try{action.run();throw new AssertionError("Accepted invalid video cue");}catch(IllegalArgumentException expected){}}
    public static void main(String[] args){
        String path="/media/robin-williams/"+"a".repeat(64)+".mp4";
        PerformanceVideoCue cue=new PerformanceVideoCue("robin-williams",path,7,840000,60000);
        check(cue.sha256.equals("a".repeat(64)));
        check(!cue.active(7,839999));check(cue.active(7,840000));check(cue.positionMs(840000)==0);
        check(cue.positionMs(864000)==1000);check(cue.active(7,2279999));check(!cue.active(7,2280000));
        PerformanceVideoCue rounded=new PerformanceVideoCue("robin-williams",path,7,840000,80014);
        check(rounded.ended(7,840000+1920324,false)); // 80.0135s PCM vs 80014ms metadata.
        check(!rounded.ended(7,840000+1920324,true)); // Queued final PCM still owns playback.
        check(rounded.ended(7,840000+1920000,false)); // Within 25ms also clears a drained rounding tail.
        check(!rounded.ended(7,840000+1919000,false)); // A real earlier stall remains resumable.
        check(!cue.active(6,864000));check(!cue.active(8,864000));
        check(cue.positionMs(0)==0);check(cue.positionMs(Long.MAX_VALUE)==60000);
        for(String bad:new String[]{"https://example.com/"+path,path+"?token=secret",path.replace("robin-williams/","robin-williams/../"),path.replace(".mp4",".wav"),path.replace('a','A')})
            rejects(()->new PerformanceVideoCue("robin-williams",bad,7,0,1000));
        rejects(()->new PerformanceVideoCue("other",path,7,0,1000));
        rejects(()->new PerformanceVideoCue("robin-williams",path,-1,0,1000));
        rejects(()->new PerformanceVideoCue("robin-williams",path,7,-1,1000));
        rejects(()->new PerformanceVideoCue("robin-williams",path,7,0,0));
        rejects(()->new PerformanceVideoCue("robin-williams",path,7,0,180001));
        rejects(()->new PerformanceVideoCue("robin-williams",path,7,Long.MAX_VALUE,1));
        System.out.println("PerformanceVideoCue tests passed: preload interval, PCM clock, epoch cancellation, path confinement and bounds");
    }
}
