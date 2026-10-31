package org.facebot;

import java.util.ArrayDeque;
import java.util.List;

/** Bounded captions addressed by the same epoch and PCM sample clock as audio. */
final class CaptionTimeline {
    static final long MAX_SAMPLES = 24000L * 120;
    static final class Cue {
        final long start, end; final String text;
        Cue(long start, long end, String text) { this.start=start; this.end=end; this.text=text; }
    }
    private final ArrayDeque<Cue> cues = new ArrayDeque<>();
    private long epoch;
    void reset(long next) { epoch=next; cues.clear(); }
    void append(long incoming, long offset, List<Cue> batch) {
        if (incoming<epoch) return;
        if (incoming!=epoch || offset<0 || offset>Long.MAX_VALUE-MAX_SAMPLES ||
                batch.size()>512 || cues.size()+batch.size()>1024) throw new IllegalArgumentException();
        long previous=0;
        // Validate the whole message before changing the live timeline.
        for(Cue cue:batch) {
            if(cue.start<previous || cue.end<=cue.start || cue.end>MAX_SAMPLES ||
                    cue.text==null || cue.text.trim().isEmpty() ||
                    cue.text.codePointCount(0,cue.text.length())>160 ||
                    cue.text.chars().anyMatch(c -> c<32)) throw new IllegalArgumentException();
            previous=cue.end;
        }
        if(!batch.isEmpty() && !cues.isEmpty() && offset+batch.get(0).start<cues.peekLast().end)
            throw new IllegalArgumentException();
        for(Cue cue:batch) cues.addLast(new Cue(offset+cue.start,offset+cue.end,cue.text));
    }
    String textAt(long sample) {
        while(!cues.isEmpty() && cues.peekFirst().end<=sample) cues.removeFirst();
        Cue cue=cues.peekFirst();
        return cue!=null && cue.start<=sample ? cue.text : "";
    }
}
