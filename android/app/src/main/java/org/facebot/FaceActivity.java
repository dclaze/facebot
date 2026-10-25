package org.facebot;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;

/** Display-only feasibility shell. Audio, attention and owner kiosk setup follow. */
public final class FaceActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(new FaceView());
        immerse();
    }
    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) immerse();
    }
    private void immerse() {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN |
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }
    private final class FaceView extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        FaceView() { super(FaceActivity.this); setBackgroundColor(Color.BLACK); }
        @Override public boolean onTouchEvent(MotionEvent event) { return true; }
        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float w = getWidth(), h = getHeight();
            double seconds = android.os.SystemClock.uptimeMillis() / 1000.0;
            float bob = (float)Math.sin(seconds * 1.4) * h * .008f;
            float blink = seconds % 4.7 < .13 ? .012f : .09f;
            paint.setColor(Color.rgb(192, 255, 231));
            canvas.drawOval(w*.15f,h*(.37f-blink)+bob,w*.40f,h*(.37f+blink)+bob,paint);
            canvas.drawOval(w*.60f,h*(.37f-blink)+bob,w*.85f,h*(.37f+blink)+bob,paint);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(w*.025f);
            paint.setStrokeCap(Paint.Cap.ROUND);
            canvas.drawArc(w*.34f,h*.48f+bob,w*.66f,h*.62f+bob,10,160,false,paint);
            paint.setStyle(Paint.Style.FILL);
            postInvalidateOnAnimation();
        }
    }
}
