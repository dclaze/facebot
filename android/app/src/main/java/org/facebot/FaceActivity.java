package org.facebot;

import androidx.activity.ComponentActivity;
import androidx.camera.view.PreviewView;
import android.widget.FrameLayout;
import android.view.Gravity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.Manifest;
import android.content.pm.PackageManager;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;

/** Native face and continuous voice client. Strong kiosk setup remains owner-controlled. */
public final class FaceActivity extends ComponentActivity {
    private final Handler main = new Handler(Looper.getMainLooper());
    private VoiceClient voice;
    private Attention attention;
    private PreviewView preview;
    private float gazeX=.5f, gazeY=.5f;
    private boolean present;
    private FaceView face;
    private boolean resumed;
    private int connectionGeneration;
    private String endpoint, token, characterName = "Boo", state = "Pairing required";
    private boolean speaking;
    private final Runnable reconnect = this::connectVoice;
    @Override public void onCreate(Bundle savedState) {
        super.onCreate(savedState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        face = new FaceView();
        FrameLayout scene = new FrameLayout(this);
        preview = new PreviewView(this);
        preview.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        scene.addView(preview, new FrameLayout.LayoutParams(-1,-1));
        scene.addView(face, new FrameLayout.LayoutParams(-1,-1));
        setContentView(scene);
        try (InputStream input = getAssets().open("local-config.json")) {
            byte[] buffer = new byte[8192];
            int size = input.read(buffer);
            if (size <= 0 || input.read() != -1) throw new IllegalArgumentException();
            JSONObject config = new JSONObject(new String(buffer, 0, size, StandardCharsets.UTF_8));
            endpoint = config.getString("url"); token = config.getString("token");
            characterName = config.optString("name", "Boo");
            // Owner-enabled development preview, not a recording or visitor control.
            if (config.optBoolean("showCamera", false)) {
                float density = getResources().getDisplayMetrics().density;
                FrameLayout.LayoutParams cameraLayout = new FrameLayout.LayoutParams(
                    (int)(160*density), (int)(120*density), Gravity.TOP | Gravity.END);
                cameraLayout.setMargins((int)(16*density),(int)(16*density),(int)(16*density),0);
                preview.setLayoutParams(cameraLayout);
                preview.bringToFront();
                preview.setClickable(false);
            }
        } catch (Exception ignored) { state = "Pairing required"; }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED ||
            checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA}, 1);
        immerse();
    }
    @Override protected void onResume() {
        super.onResume(); resumed = true; connectVoice(); startAttention();
    }
    @Override protected void onPause() {
        resumed = false; connectionGeneration++; main.removeCallbacks(reconnect);
        if (voice != null) { voice.close(); voice = null; }
        speaking = false; state = "Muted";
        super.onPause();
    }
    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (resumed) { connectVoice(); startAttention(); }
    }
    @Override protected void onDestroy() {
        if (attention != null) attention.close();
        super.onDestroy();
    }
    private void startAttention() {
        if (attention != null || checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return;
        try {
            attention = new Attention(this, preview, (found, x, y) -> {
                present = found; gazeX = found ? x : .5f; gazeY = found ? y : .5f;
            });
        } catch (Exception ignored) { present = false; }
    }
    private void connectVoice() {
        main.removeCallbacks(reconnect);
        if (!resumed || endpoint == null || voice != null) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            state = "Microphone permission needed"; return;
        }
        final int generation = ++connectionGeneration;
        voice = new VoiceClient(this, (message, talking) -> main.post(() -> {
            if (!resumed || generation != connectionGeneration) return;
            state = message; speaking = talking;
            if (message.equals("Reconnecting")) {
                voice = null;
                main.removeCallbacks(reconnect); main.postDelayed(reconnect, 1500);
            }
        }));
        voice.connect(endpoint, token);
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
            canvas.save();
            canvas.translate((gazeX-.5f)*w*.12f,(gazeY-.5f)*h*.045f);
            canvas.drawOval(w*.15f,h*(.37f-blink)+bob,w*.40f,h*(.37f+blink)+bob,paint);
            canvas.drawOval(w*.60f,h*(.37f-blink)+bob,w*.85f,h*(.37f+blink)+bob,paint);
            canvas.restore();
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(w*.025f);
            paint.setStrokeCap(Paint.Cap.ROUND);
            if (speaking) canvas.drawOval(w*.43f,h*.52f+bob,w*.57f,h*(.62f+.025f*(float)Math.sin(seconds*16))+bob,paint);
            else canvas.drawArc(w*.34f,h*.48f+bob,w*.66f,h*.62f+bob,10,160,false,paint);
            paint.setStyle(Paint.Style.FILL);
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTextSize(w*.065f);
            canvas.drawText(characterName,w*.5f,h*.77f,paint);
            paint.setTextSize(w*.025f);
            paint.setAlpha(130);
            canvas.drawText(state,w*.5f,h*.82f,paint);
            paint.setAlpha(255);
            postInvalidateOnAnimation();
        }
    }
}
