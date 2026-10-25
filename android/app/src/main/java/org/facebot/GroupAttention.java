package org.facebot;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Short-lived position tracks, never person identities or speaker evidence. */
final class GroupAttention {
    static final int LIMIT=16;
    static final long EXPIRE_MS=750;
    static final class Box {
        final float x,y,area;
        Box(float x,float y,float area) { this.x=x;this.y=y;this.area=area; }
    }
    private static final class Track {
        long id,seen; float x,y; boolean matched;
        Track(long id,Box b,long now) {this.id=id;x=b.x;y=b.y;seen=now;matched=true;}
    }
    private final List<Track> tracks=new ArrayList<>();
    private long nextId=1;
    void update(List<Box> boxes,long now) {
        tracks.removeIf(t -> now-t.seen>EXPIRE_MS);
        for(Track t:tracks) t.matched=false;
        // Keep the near interaction region bounded; size is not a person count.
        List<Box> selected=new ArrayList<>(LIMIT+1);
        for(Box b:boxes) {
            if(!Float.isFinite(b.x)||!Float.isFinite(b.y)||!Float.isFinite(b.area)
                    ||b.x<0||b.x>1||b.y<0||b.y>1||b.area<=0) continue;
            selected.add(b);
            selected.sort(Comparator.comparingDouble((Box a)->a.area).reversed());
            if(selected.size()>LIMIT) selected.remove(LIMIT);
        }
        for(Box b:selected) {
            Track best=null; float distance=.15f*.15f;
            for(Track t:tracks) {
                float dx=t.x-b.x,dy=t.y-b.y,d=dx*dx+dy*dy;
                if(!t.matched && d<distance) {best=t;distance=d;}
            }
            if(best!=null) {
                best.x+=(b.x-best.x)*.35f;best.y+=(b.y-best.y)*.35f;
                best.seen=now;best.matched=true;
            } else if(tracks.size()<LIMIT) tracks.add(new Track(nextId++,b,now));
            // Unmatched old positions expire; never reassign an ID to a distant face.
        }
    }
    int size() {return tracks.size();}
    float x() {float sum=0;for(Track t:tracks) sum+=t.x;return tracks.isEmpty()?.5f:sum/tracks.size();}
    float y() {float sum=0;for(Track t:tracks) sum+=t.y;return tracks.isEmpty()?.5f:sum/tracks.size();}
    long idNear(float x,float y) {
        Track best=null;float distance=Float.MAX_VALUE;
        for(Track t:tracks) {float d=(t.x-x)*(t.x-x)+(t.y-y)*(t.y-y);if(d<distance){distance=d;best=t;}}
        return best==null?-1:best.id;
    }
}
