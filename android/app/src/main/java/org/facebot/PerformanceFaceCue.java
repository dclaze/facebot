package org.facebot;
/** Single short performance expression on the same 24 kHz PCM clock as speech. */
final class PerformanceFaceCue {
    private long epoch=-1,start,end;
    private String name="";
    void set(long incoming,long offset,long duration,String value) {
        if(incoming<0 || offset<0 || duration<=0 || duration>24000L*120 || offset>Long.MAX_VALUE-duration || !"wolf_eyes".equals(value)) throw new IllegalArgumentException();
        epoch=incoming;start=offset;end=offset+duration;name=value;
    }
    String at(long current,long sample,long written) { return epoch==current && sample>=start && sample<end && sample<written ? name : ""; }
    void reset(){epoch=-1;name="";}
}
