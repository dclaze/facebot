package org.facebot;

public final class EchoControlTest {
    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }
    public static void main(String[] args) {
        check(EchoControl.needsHalfDuplex("LENOVO", "Lenovo TB-J606F", 30), "observed model");
        check(EchoControl.needsHalfDuplex("Lenovo", "TB-J606F", 30), "unprefixed model");
        check(!EchoControl.needsHalfDuplex("Lenovo", "TB-J606F", 31), "newer OS keeps AEC");
        check(!EchoControl.needsHalfDuplex("Lenovo", "TB-J606L", 30), "other model keeps AEC");
        check(!EchoControl.needsHalfDuplex("Other", "TB-J606F", 30), "other maker keeps AEC");
        check(!EchoControl.needsHalfDuplex(null, null, 30), "unknown device keeps AEC");

        EchoControl normal = new EchoControl(false);
        normal.outputActivity(100);
        check(!normal.silenceCapture(101, true), "full duplex permits interruption");
        EchoControl gate = new EchoControl(true);
        check(!gate.silenceCapture(100, false), "idle microphone passes");
        gate.outputActivity(100); // Packet accepted, before the first AudioTrack write.
        check(gate.silenceCapture(101, false), "queue-to-write gap is gated");
        check(gate.silenceCapture(10000, true), "long playback stays gated past initial tail");
        check(gate.silenceCapture(10599, false), "drained playback retains echo tail");
        check(!gate.silenceCapture(10600, false), "idle polling does not extend tail");
        gate.outputActivity(20000);
        check(gate.silenceCapture(20100, true), "second turn gates again");
        // An interrupt clears queued/written PCM, but must not erase room/capture echo.
        check(gate.silenceCapture(20101, false), "flush retains tail");
        check(!gate.silenceCapture(20700, false), "flush cannot leave microphone stuck muted");
        check(!new EchoControl(true).silenceCapture(10, false), "new connection has no stale gate");
        System.out.println("EchoControlTest passed");
    }
}
