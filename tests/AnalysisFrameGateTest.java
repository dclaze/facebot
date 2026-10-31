package org.facebot;

public final class AnalysisFrameGateTest {
    private static final class Frame {
        int snapshots,submits,closes;
        void snapshot() { check(closes==0); snapshots++; }
        void submit() { check(snapshots==1 && closes==0); submits++; }
        void close() { closes++; }
    }
    private static void check(boolean condition) { if(!condition) throw new AssertionError(); }
    public static void main(String[] args) {
        Frame skipped=new Frame();
        AnalysisFrameGate.dispatch(true,skipped::snapshot,()->false,skipped::submit,skipped::close);
        check(skipped.snapshots==1 && skipped.submits==0 && skipped.closes==1);
        Frame accepted=new Frame();
        AnalysisFrameGate.dispatch(true,accepted::snapshot,()->true,accepted::submit,accepted::close);
        check(accepted.snapshots==1 && accepted.submits==1 && accepted.closes==0);
        accepted.close();check(accepted.closes==1); // Fake asynchronous MLKit owner completes.
        Frame stopped=new Frame();
        AnalysisFrameGate.dispatch(false,stopped::snapshot,()->true,stopped::submit,stopped::close);
        check(stopped.snapshots==0 && stopped.submits==0 && stopped.closes==1);
        Frame snapshotFailure=new Frame();
        try {
            AnalysisFrameGate.dispatch(true,()->{throw new IllegalStateException();},()->true,
                snapshotFailure::submit,snapshotFailure::close);
            throw new AssertionError();
        } catch(IllegalStateException expected) { check(snapshotFailure.closes==1); }
        Frame submissionFailure=new Frame();
        try {
            AnalysisFrameGate.dispatch(true,submissionFailure::snapshot,()->true,
                ()->{throw new IllegalStateException();},submissionFailure::close);
            throw new AssertionError();
        } catch(IllegalStateException expected) { check(submissionFailure.closes==1); }
        // Skipping thousands of frames still snapshots each one and retains none.
        for(int i=0;i<10000;i++) {
            Frame frame=new Frame();
            AnalysisFrameGate.dispatch(true,frame::snapshot,()->false,frame::submit,frame::close);
            check(frame.snapshots==1 && frame.closes==1);
        }
        System.out.println("Analysis frame snapshot/close/async ownership and failure paths passed");
    }
}
