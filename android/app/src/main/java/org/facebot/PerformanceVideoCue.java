package org.facebot;

/** Immutable, bounded metadata; video presentation uses the PCM playback clock. */
final class PerformanceVideoCue {
    final String path, sha256;
    final long epoch, offset, durationMs, end;
    PerformanceVideoCue(String id,String path,long epoch,long offset,long durationMs) {
        if(!"robin-williams".equals(id) || path==null ||
                !path.matches("/media/robin-williams/[a-f0-9]{64}\\.mp4") || epoch<0 || offset<0 ||
                durationMs<1 || durationMs>180000 || offset>Long.MAX_VALUE-durationMs*24)
            throw new IllegalArgumentException("Invalid performance video cue");
        this.path=path;this.sha256=path.substring(path.lastIndexOf('/')+1,path.length()-4);
        this.epoch=epoch;this.offset=offset;this.durationMs=durationMs;this.end=offset+durationMs*24;
    }
    boolean active(long epoch,long sample) {return this.epoch==epoch && sample>=offset && sample<end;}
    boolean ended(long epoch,long sample,boolean playing) {
        // Millisecond metadata rounds a 24 kHz sample boundary. Do not leave the
        // final frame stuck waiting for samples that the audio track will never play.
        return this.epoch!=epoch || sample>=end || (!playing && sample>offset && end-sample<=600);
    }
    int positionMs(long sample) {return (int)Math.max(0,Math.min(durationMs,(sample-offset)/24));}
}
