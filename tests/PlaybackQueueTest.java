package org.facebot;

/** Host JVM tests: deliberately never start a consumer until after admission. */
public final class PlaybackQueueTest {
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError();
    }
    public static void main(String[] args) throws Exception {
        PlaybackQueue q = new PlaybackQueue();
        byte[] maximum = new byte[PlaybackQueue.MAX_PCM_BYTES];
        check(q.offer(1, maximum));
        maximum[0] = 42;
        check(q.queuedBytes() == 7680);
        check(q.poll().pcm[0] == 0); // Caller mutation cannot corrupt queued audio.
        for (int n = 0; n < 6; n++) check(q.offer(n, new byte[1920])); // 40 ms burst.
        check(!q.offer(7, new byte[1920]));
        check(q.queuedBytes() == PlaybackQueue.CAPACITY_BYTES);
        for (int n = 0; n < 6; n++) check(q.poll().epoch == n);
        check(q.queuedBytes() == 0);
        check(q.offer(8, new byte[5760]));
        check(!q.offer(8, new byte[7680])); // No partial packet admission.
        check(q.queuedBytes() == 5760);
        q.clear();
        check(q.queuedBytes() == 0);
        check(!q.offer(9, new byte[7682]));
        check(!q.offer(9, new byte[1]));
        check(!q.offer(9, new byte[0]));
        check(q.offer(10, new byte[7680]));
        check(q.poll().epoch == 10);
        System.out.println("PlaybackQueue delayed-consumer and burst checks passed");
    }
}
