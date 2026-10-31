package org.facebot;

public final class ThermalCadenceTest {
    private static void check(boolean condition) { if(!condition) throw new AssertionError(); }
    private static float moved(int frames) {
        float value=0;
        for(int i=0;i<frames;i++) value+=(1-value)*ThermalCadence.gazeBlend(200.0/frames);
        return value;
    }
    public static void main(String[] args) {
        for(int status=0;status<=6;status++) {
            ThermalCadence cadence=new ThermalCadence();cadence.setStatus(status);
            int accepted=0;
            for(int ms=0;ms<1000;ms++) if(cadence.analyzeNow(ms)) accepted++;
            check(accepted==(status>=4?5:status>=3?10:1000));
            check(cadence.redrawDelayMs()==(status>=4?67:status>=3?33:0));
        }
        // A 16ms callback can land on the very next 60Hz frame: no rate reduction.
        double vsync=1000.0/60;
        check(Math.ceil(16/vsync)==1);
        check(Math.ceil(33/vsync)>=2);
        check(Math.ceil(67/vsync)>=4);
        ThermalCadence cadence=new ThermalCadence();
        check(cadence.analyzeNow(1000));
        cadence.setStatus(3);check(!cadence.analyzeNow(1099));check(cadence.analyzeNow(1100));
        cadence.setStatus(4);check(!cadence.analyzeNow(1299));check(cadence.analyzeNow(1300));
        cadence.setStatus(3);check(!cadence.analyzeNow(1399));check(cadence.analyzeNow(1400));
        cadence.setStatus(2);check(cadence.analyzeNow(1401));check(cadence.redrawDelayMs()==0);
        cadence.setStatus(4);cadence.setStatus(-1);cadence.setStatus(99);
        check(cadence.analysisIntervalMs()==200); // Invalid events retain known policy.
        check(cadence.analyzeNow(5)); // A replaced/backward test clock cannot starve forever.
        check(Math.abs(ThermalCadence.gazeBlend(1000.0/60)-.18f)<.000001f);
        check(Math.abs(moved(12)-moved(6))<.000001f); // Same 200ms at 60/30fps.
        check(Math.abs(moved(12)-moved(3))<.000001f); // Same 200ms at 15fps.
        check(ThermalCadence.gazeBlend(0)==0 && ThermalCadence.gazeBlend(-10)==0);
        check(ThermalCadence.gazeBlend(10000)==ThermalCadence.gazeBlend(250));
        System.out.println("Thermal cadence transitions, recovery and elapsed-time gaze passed");
    }
}
