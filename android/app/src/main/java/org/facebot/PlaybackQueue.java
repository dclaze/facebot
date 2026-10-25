package org.facebot;

import java.util.ArrayDeque;

/** Byte-bounded FIFO. Admission is atomic for an entire protocol message. */
final class PlaybackQueue {
    static final int MAX_PCM_BYTES = 7680; // 160 ms, mono PCM16 at 24 kHz.
    static final int CAPACITY_BYTES = 11520; // 240 ms queued, excluding active write/device buffer.
    static final class Packet {
        final long epoch;
        final byte[] pcm;
        Packet(long epoch, byte[] pcm) { this.epoch = epoch; this.pcm = pcm; }
    }
    private final ArrayDeque<Packet> packets = new ArrayDeque<>();
    private int bytes;
    synchronized boolean offer(long epoch, byte[] pcm) {
        if (pcm.length == 0 || pcm.length % 2 != 0 || pcm.length > MAX_PCM_BYTES
                || bytes + pcm.length > CAPACITY_BYTES) return false;
        packets.addLast(new Packet(epoch, pcm.clone()));
        bytes += pcm.length;
        notifyAll();
        return true;
    }
    synchronized Packet poll() throws InterruptedException {
        if (packets.isEmpty()) wait(100);
        Packet packet = packets.pollFirst();
        if (packet != null) bytes -= packet.pcm.length;
        return packet;
    }
    synchronized void clear() { packets.clear(); bytes = 0; }
    synchronized int queuedBytes() { return bytes; }
}
