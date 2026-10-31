package org.facebot;

import android.content.Context;
import android.os.Build;
import android.os.PowerManager;
import java.util.function.IntConsumer;

/** Activity start/stop-scoped thermal observation, with API29 types isolated for minSDK26. */
final class ThermalMonitor {
    private final Context context;
    private final IntConsumer consumer;
    private Api29 monitor;
    ThermalMonitor(Context context,IntConsumer consumer) {
        this.context=context.getApplicationContext();this.consumer=consumer;
    }
    void start() {
        if(Build.VERSION.SDK_INT<29) return;
        if(monitor==null) monitor=new Api29(context,consumer);
        monitor.start();
    }
    void stop() { if(monitor!=null) monitor.stop(); }

    @android.annotation.TargetApi(29)
    private static final class Api29 {
        private final Context context;
        private final PowerManager power;
        private final IntConsumer consumer;
        private PowerManager.OnThermalStatusChangedListener listener;
        private int generation;
        Api29(Context context,IntConsumer consumer) {
            this.context=context;this.consumer=consumer;
            power=(PowerManager)context.getSystemService(Context.POWER_SERVICE);
        }
        void start() {
            if(power==null || listener!=null) return;
            final int current=++generation;
            listener=status -> { if(listener!=null && current==generation) consumer.accept(status); };
            try {
                power.addThermalStatusListener(context.getMainExecutor(),listener);
                consumer.accept(power.getCurrentThermalStatus());
            } catch(RuntimeException unavailable) {
                stop(); // Retain the last known policy if this device stops reporting.
            }
        }
        void stop() {
            generation++;
            PowerManager.OnThermalStatusChangedListener old=listener;
            listener=null;
            if(old!=null && power!=null) {
                try { power.removeThermalStatusListener(old); } catch(RuntimeException ignored) { }
            }
        }
    }
}
