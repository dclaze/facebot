package org.facebot;
public final class PlaybackProbeTest {
    static final String ID="12345678-abcd-4321-abcd-123456789abc";
    static final String NEXT="12345678-abcd-4321-abcd-123456789def";
    static void check(boolean ok){if(!ok)throw new AssertionError();}
    public static void main(String[] args){
        PlaybackProbe probe=new PlaybackProbe();
        check(!probe.arm("not-a-uuid",3,3,100,20));check(!probe.arm(ID,2,3,100,20));
        check(!probe.arm(ID,3,3,-1,20));check(probe.arm(ID,3,3,100,20));
        check(probe.observed(3,99,21)==null);check(probe.observed(3,100,22)==null);
        PlaybackProbe.Receipt receipt=probe.observed(3,101,23);
        check(receipt!=null && receipt.id.equals(ID) && receipt.epoch==3 && receipt.sample==101);
        check(probe.observed(3,150,24)==null);
        probe.arm(ID,3,3,100,20);check(probe.observed(4,101,30)==null);check(probe.observed(3,101,31)==null);
        probe.arm(ID,3,3,100,20);probe.reset();check(probe.observed(3,101,21)==null);
        probe.arm(ID,3,3,100,20);check(probe.observed(3,101,20+PlaybackProbe.TIMEOUT_MS)==null);
        probe.arm(ID,3,3,100,20);probe.arm(NEXT,3,3,200,21);check(probe.observed(3,150,22)==null);
        check(probe.observed(3,201,23).id.equals(NEXT));
        probe.arm(ID,3,3,100,20);check(probe.observed(3,101,19)==null);
        System.out.println("PlaybackProbeTest passed: actual head, strict offset, epoch, timeout, reset, one receipt, bounded replacement");
    }
}
