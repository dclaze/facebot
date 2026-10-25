package org.facebot;
import java.util.*;
public class GroupAttentionTest {
    static void check(boolean ok) { if(!ok) throw new AssertionError(); }
    public static void main(String[] args) {
        GroupAttention g = new GroupAttention();
        List<GroupAttention.Box> boxes = new ArrayList<>();
        for(int i=0;i<64;i++) boxes.add(new GroupAttention.Box((i%8)/8f,(i/8)/8f,.01f));
        g.update(boxes,0); check(g.size()==16);
        g.update(Collections.emptyList(),300); check(g.size()==16);
        g.update(Collections.emptyList(),1000); check(g.size()==0); check(g.x()==.5f);
        boxes=Arrays.asList(new GroupAttention.Box(.2f,.5f,.2f),new GroupAttention.Box(.8f,.5f,.02f));
        g.update(boxes,1100); check(Math.abs(g.x()-.5f)<.01f); // group, not largest
        long left=g.idNear(.2f,.5f);
        g.update(Arrays.asList(new GroupAttention.Box(.21f,.5f,.2f),new GroupAttention.Box(.79f,.5f,.02f)),1200);
        check(g.idNear(.21f,.5f)==left);
        for(int i=0;i<1000;i++) g.update(boxes,1300+i*20);
        check(g.size()<=16);
        System.out.println("GroupAttention synthetic bounds, continuity, expiry and group gaze passed");
    }
}
