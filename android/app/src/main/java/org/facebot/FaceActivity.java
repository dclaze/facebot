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
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;

/** Native face and continuous voice client. Strong kiosk setup remains owner-controlled. */
public final class FaceActivity extends ComponentActivity {
    private final Handler main = new Handler(Looper.getMainLooper());
    private VoiceClient voice;
    private Attention attention;
    private PreviewView preview;
    private View cameraOverlay;
    private float gazeX=.5f, gazeY=.5f;
    private boolean present;
    private String visionState = "Vision starting";
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
                cameraOverlay = new View(this) {
                    private final Paint marker = new Paint(Paint.ANTI_ALIAS_FLAG);
                    @Override protected void onDraw(Canvas canvas) {
                        if (!present) return;
                        float x=gazeX*getWidth(), y=gazeY*getHeight();
                        marker.setColor(Color.rgb(94,255,184)); marker.setStrokeWidth(3);
                        marker.setStyle(Paint.Style.STROKE);
                        canvas.drawCircle(x,y,18,marker);
                        canvas.drawLine(x-26,y,x+26,y,marker);
                        canvas.drawLine(x,y-26,x,y+26,marker);
                    }
                };
                scene.addView(cameraOverlay, new FrameLayout.LayoutParams(cameraLayout));
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
            attention = new Attention(this, preview, (found, x, y, status, count, analysisMs) -> {
                present = found; gazeX = found ? x : .5f; gazeY = found ? y : .5f;
                visionState = status+" / "+analysisMs+" ms";
                if (voice != null && count >= 0) voice.observeScene(count,analysisMs);
                if (cameraOverlay != null) cameraOverlay.invalidate();
            });
        } catch (Exception ignored) { present = false; visionState = "Vision unavailable"; }
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
    @Override protected void onNewIntent(android.content.Intent intent) {
        super.onNewIntent(intent); setIntent(intent);
        if (intent.getBooleanExtra("renderFacePreview",false)) renderFacePreview();
    }
    private void renderFacePreview() {
        if ((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)==0 || face.getWidth()==0) return;
        for (String mouth : new String[]{"rest","closed","open","wide","round","pucker","teeth","tongue","narrow"}) {
            android.graphics.Bitmap image=android.graphics.Bitmap.createBitmap(600,1000,android.graphics.Bitmap.Config.ARGB_8888);
            Canvas canvas=new Canvas(image);canvas.scale(600f/face.getWidth(),1000f/face.getHeight());
            face.previewShape=mouth;face.draw(canvas);
            try (java.io.FileOutputStream output=openFileOutput("face-"+mouth+".png",MODE_PRIVATE)) {
                image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,output);
            } catch(java.io.IOException ignored) { }
            image.recycle();
        }
        face.previewShape=null;
    }
    private void immerse() {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN |
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }
    private final class FaceView extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path shape = new Path();
        private float lookX=.5f, lookY=.5f;
        private final MouthRenderer mouthRenderer=new MouthRenderer();
        String previewShape;
        FaceView() { super(FaceActivity.this); setBackgroundColor(Color.BLACK); }
        @Override public boolean onTouchEvent(MotionEvent event) { return true; }
        private void fill(int color) { paint.setShader(null); paint.setStyle(Paint.Style.FILL); paint.setColor(color); }
        private void curve(Canvas c,float ax,float ay,float bx,float by,float cx,float cy,float width,int color) {
            shape.reset(); shape.moveTo(ax,ay); shape.quadTo(bx,by,cx,cy);
            fill(color); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(width);
            paint.setStrokeCap(Paint.Cap.ROUND); c.drawPath(shape,paint); paint.setStyle(Paint.Style.FILL);
        }
        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float w=getWidth(), h=getHeight();
            double t=android.os.SystemClock.uptimeMillis()/1000.0;
            lookX+=(gazeX-lookX)*.18f; lookY+=(gazeY-lookY)*.18f;
            float dx=(lookX-.5f)*.10f, dy=(lookY-.5f)*.045f;
            float bob=(float)Math.sin(t*1.6)*.006f;
            int ice=Color.rgb(206,255,238), mint=Color.rgb(94,235,184), deep=Color.rgb(9,54,47);
            canvas.save(); canvas.scale(w,h); canvas.translate(0,bob);
            // A faint halo gives the disembodied face depth without a rectangular panel.
            paint.setShader(new RadialGradient(.5f,.47f,.49f,
                new int[]{Color.rgb(12,49,43),Color.rgb(3,15,14),Color.BLACK},null,Shader.TileMode.CLAMP));
            canvas.drawRect(0,0,1,1,paint); paint.setShader(null);
            float blink=t%5.3<.12 ? .10f : 1f;
            for(int side=0;side<2;side++) {
                float cx=side==0?.29f:.71f;
                float cy=(side==0?.395f:.375f)+dy*.3f;
                canvas.save(); canvas.rotate(side==0?-8:9,cx,cy);
                canvas.scale(1,blink,cx,cy);
                fill(deep); canvas.drawOval(cx-.182f,cy-.091f,cx+.182f,cy+.096f,paint);
                fill(ice); canvas.drawOval(cx-.163f,cy-.078f,cx+.163f,cy+.078f,paint);
                // Large moving pupils make attention visible from across the room.
                fill(mint); canvas.drawOval(cx+dx-.064f,cy+dy-.063f,cx+dx+.064f,cy+dy+.063f,paint);
                fill(Color.rgb(3,17,15)); canvas.drawOval(cx+dx-.036f,cy+dy-.053f,cx+dx+.036f,cy+dy+.053f,paint);
                fill(Color.WHITE); canvas.drawOval(cx+dx-.027f,cy+dy-.039f,cx+dx-.009f,cy+dy-.020f,paint);
                canvas.restore();
            }
            // One eyebrow is permanently skeptical. The other rises when someone appears.
            curve(canvas,.12f,.278f,.25f,present?.217f:.245f,.43f,.279f,.021f,mint);
            curve(canvas,.57f,.264f,.75f,.196f,.88f,.247f,.024f,ice);
            fill(mint); shape.reset(); shape.moveTo(.484f,.475f);shape.quadTo(.5f,.456f,.516f,.475f);
            shape.quadTo(.5f,.490f,.484f,.475f);canvas.drawPath(shape,paint);
            String mouth=previewShape!=null?previewShape:(voice!=null?voice.mouthShape():"rest");
            mouthRenderer.draw(canvas,mouth,t,previewShape!=null);
            curve(canvas,.19f,.548f,.21f,.528f,.25f,.530f,.009f,mint);
            curve(canvas,.76f,.510f,.80f,.495f,.82f,.518f,.009f,ice);
            canvas.restore();
            fill(mint);paint.setTextAlign(Paint.Align.CENTER);
            paint.setTypeface(android.graphics.Typeface.create("sans-serif-condensed",android.graphics.Typeface.BOLD));
            paint.setTextSize(w*.036f);canvas.drawText(characterName.toUpperCase(java.util.Locale.ROOT),w*.5f,h*.83f,paint);
            paint.setTypeface(android.graphics.Typeface.DEFAULT);paint.setTextSize(w*.023f);paint.setAlpha(160);
            canvas.drawText(previewShape!=null?"SYNTHETIC / "+previewShape:state+"  /  "+visionState,w*.5f,h*.875f,paint);paint.setAlpha(255);
            postInvalidateOnAnimation();
        }
    }
}
