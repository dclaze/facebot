package org.facebot;

/** One content-free receipt, released only by observed native playback progress. */
final class PlaybackProbe {
    static final long TIMEOUT_MS=15000;
    static final class Receipt {
        final String id; final long epoch,sample;
        Receipt(String id,long epoch,long sample){this.id=id;this.epoch=epoch;this.sample=sample;}
    }
    private String id;
    private long epoch,offset,armedAt;
    boolean arm(String nextId,long incoming,long current,long sampleOffset,long now) {
        if(nextId==null || !nextId.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}") ||
                incoming<0 || incoming!=current || sampleOffset<0 || now<0) return false;
        id=nextId;epoch=incoming;offset=sampleOffset;armedAt=now;
        return true;
    }
    Receipt observed(long current,long head,long now) {
        if(id==null) return null;
        if(current!=epoch || now<armedAt || now-armedAt>=TIMEOUT_MS) { reset();return null; }
        if(head<=offset) return null;
        Receipt receipt=new Receipt(id,epoch,head);reset();return receipt;
    }
    void reset(){id=null;}
}
