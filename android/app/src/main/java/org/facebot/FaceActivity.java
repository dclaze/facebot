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
    private PerformanceVideo performanceVideo;
    private SettingsClient settingsClient;
    private final boolean halfDuplex=EchoControl.needsHalfDuplex(
        android.os.Build.MANUFACTURER,android.os.Build.MODEL,android.os.Build.VERSION.SDK_INT);
    private final QuietControlState quietControl=new QuietControlState();
    private android.widget.LinearLayout quietPanel;
    private android.widget.Button quietButton,resumeButton;
    private android.widget.TextView quietStatus;
    private int[] palette={0xFFCEFFEE,0xFF5EEBB8,0xFF09362F,0xFF0C312B,0xFF030F0E};
    private Attention attention;
    private final ThermalCadence thermalCadence=new ThermalCadence();
    private ThermalMonitor thermalMonitor;
    private VisionClient vision;
    private String sceneLabels = "";
    private PreviewView preview;
    private View cameraOverlay;
    private float gazeX=.5f, gazeY=.5f;
    private boolean present;
    private String visionState = "Vision starting";
    private FaceView face;
    private boolean resumed;
    private int connectionGeneration, failures;
    private long readySince;
    private boolean allowPrivateLan, diagnostics, ownerDialog;
    private static final int OWNER_AUTH=41;
    private android.content.SharedPreferences pairing;
    private final Runnable ownerHold=this::authenticateOwner;
    private String endpoint, token, characterName = "Boo", state = "Pairing required";
    private boolean speaking;
    private String accessibilityDescription="";
    private final Runnable reconnect = this::connectVoice;
    @Override public void onCreate(Bundle savedState) {
        super.onCreate(savedState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        face = new FaceView();
        thermalMonitor=new ThermalMonitor(this,status -> { thermalCadence.setStatus(status); face.invalidate(); });
        FrameLayout scene = new FrameLayout(this);
        preview = new PreviewView(this);
        preview.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        scene.addView(preview, new FrameLayout.LayoutParams(-1,-1));
        scene.addView(face, new FrameLayout.LayoutParams(-1,-1));
        performanceVideo = new PerformanceVideo(this,scene,()->voice==null?null:voice.playbackPosition());
        if(halfDuplex) addQuietControls(scene);
        setContentView(scene);
        pairing=getSharedPreferences("owner-pairing",MODE_PRIVATE);
        quietControl.localHold=pairing.getBoolean("localQuiet",false);
        endpoint=pairing.getString("url",null); token=pairing.getString("token",null);
        characterName=pairing.getString("name","Boo");
        allowPrivateLan=pairing.getBoolean("allowPrivateLan",false);
        diagnostics=pairing.getBoolean("diagnostics",false);
        // Only the debug source set can contain a private bootstrap. Release has no assets.
        if(endpoint==null && (getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0) {
            try(InputStream input=getAssets().open("local-config.json")) {
                byte[] bytes=new byte[8192]; int count=input.read(bytes);
                if(count<=0 || input.read()!=-1) throw new IllegalArgumentException();
                JSONObject config=new JSONObject(new String(bytes,0,count,StandardCharsets.UTF_8));
                endpoint=config.getString("url"); token=config.getString("token");
                characterName=config.optString("name","Boo");
                allowPrivateLan=config.optBoolean("allowPrivateLan",false);
            } catch(Exception ignored) { }
        }
        if(!ConnectionPolicy.allows(endpoint,allowPrivateLan) || token==null || token.length()<24) {
            endpoint=null; token=null; state="Owner setup needed";
        }
        // Visitors cannot leave the face via Back; system navigation remains OS-controlled.
        getOnBackPressedDispatcher().addCallback(this,new androidx.activity.OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() { immerse(); }
        });
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED ||
            checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA}, 1);
        refreshAccessibility();
        immerse();
    }
    @Override protected void onStart() {
        super.onStart();
        if(thermalMonitor!=null) thermalMonitor.start();
    }
    @Override protected void onStop() {
        if(thermalMonitor!=null) thermalMonitor.stop();
        super.onStop();
    }
    @Override protected void onResume() {
        super.onResume(); resumed = true; face.invalidate(); startConnections();
    }
    private void startConnections() {
        if(ownerDialog) return;
        if(endpoint==null) state="Owner setup needed";
        refreshAccessibility();
        connectVoice();
        if(endpoint!=null && vision==null) vision=new VisionClient(endpoint,token,allowPrivateLan,
            labels -> main.post(() -> sceneLabels=labels));
        if(endpoint!=null && settingsClient==null) {
            try { settingsClient=new SettingsClient(this,endpoint,token,allowPrivateLan,(name,colors) -> {
                characterName=name; palette=colors; refreshAccessibility();
            }); } catch(IllegalArgumentException ignored) { }
        }
        startAttention(); refreshQuietControls();
    }
    @Override protected void onPause() {
        resumed = false;
        if(face!=null) face.removeCallbacks(face.thermalRedraw);
        stopConnections();
        super.onPause();
    }
    private void stopConnections() {
        quietControl.cancelPending();
        connectionGeneration++; main.removeCallbacks(reconnect); main.removeCallbacks(ownerHold);
        if (voice != null) { voice.close(); voice = null; }
        if (vision != null) { vision.close(); vision = null; }
        if(settingsClient!=null) { settingsClient.close(); settingsClient=null; }
        if(performanceVideo!=null)performanceVideo.clear();
        sceneLabels="";
        speaking = false; state = "Muted"; refreshAccessibility();
    }
    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (resumed) { connectVoice(); startAttention(); }
    }
    @Override protected void onDestroy() {
        if(thermalMonitor!=null) thermalMonitor.stop();
        if (attention != null) attention.close();
        if(performanceVideo!=null)performanceVideo.close();
        super.onDestroy();
    }
    private void startAttention() {
        if (attention != null || checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return;
        try {
            attention = new Attention(this, preview, (found, x, y, status, count, analysisMs, faceFill) -> {
                present = found; gazeX = found ? x : .5f; gazeY = found ? y : .5f;
                visionState = status+" / "+analysisMs+" ms";
                if (voice != null && count >= 0) voice.observeScene(count,analysisMs,faceFill);
                if (cameraOverlay != null) cameraOverlay.invalidate();
            }, image -> { if(resumed && vision!=null) vision.sample(image); }, thermalCadence);
        } catch (Exception ignored) { present = false; visionState = "Vision unavailable"; }
    }
    private void connectVoice() {
        main.removeCallbacks(reconnect);
        if (!resumed || ownerDialog || endpoint == null || voice != null) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            state = "Microphone permission needed"; refreshAccessibility(); return;
        }
        readySince=0;
        final int generation = ++connectionGeneration;
        voice = new VoiceClient(this, (message, talking) -> main.post(() -> {
            if (!resumed || generation != connectionGeneration) return;
            state = message; speaking = talking; refreshAccessibility();
            if(message.equals("Listening") || message.equals("Quiet mode")) {
                long now=android.os.SystemClock.elapsedRealtime();
                if(readySince==0) readySince=now;
                if(now-readySince>10000) failures=0;
            }
            if (message.equals("Reconnecting")) {
                connectionGeneration++; // Ignore delayed UI/video events from the dead socket.
                voice = null;
                if(performanceVideo!=null)performanceVideo.clear();
                main.removeCallbacks(reconnect); main.postDelayed(reconnect, ConnectionPolicy.retryDelay(++failures));
            }
        }));
        voice.setLocalQuiet(quietControl.localHold);
        voice.setKioskStateListener(muted -> main.post(() -> {
            if(!resumed || generation!=connectionGeneration) return;
            boolean wasHeld=quietControl.localHold;
            quietControl.serverState(muted);
            if(wasHeld!=quietControl.localHold) {
                persistLocalQuiet();
                if(voice!=null) voice.setLocalQuiet(quietControl.localHold);
            }
            refreshQuietControls();
        }));
        voice.setVideoListener(event -> main.post(() -> {
            if(resumed && generation==connectionGeneration && !quietControl.localHold && performanceVideo!=null)
                performanceVideo.receive(event,endpoint,token,allowPrivateLan);
        }));
        voice.connect(endpoint, token,allowPrivateLan);
    }
    private void refreshAccessibility() {
        refreshQuietControls();
        if(face==null) return;
        String status;
        switch(state) {
            case "Listening": status=outputPlaying() ? "Playing audio." : "Ready to listen.";break;
            case "Quiet mode": status="Quiet mode. Speech output is paused. The microphone remains active for resume.";break;
            case "Muted": status="Microphone paused.";break;
            case "Connecting": status="Connecting to the host.";break;
            case "Reconnecting": status="Reconnecting to the host.";break;
            default: status=state+".";
        }
        if(quietControl.localHold) status="Speech paused here. Tap Resume to allow speech.";
        String description=characterName+". "+status+" Owner setup is available in accessibility actions.";
        // Called by actual state/name changes, never by drawing or gaze updates.
        // Identical playback-ready ticks do not repeatedly announce themselves.
        if(!description.equals(accessibilityDescription)) {
            accessibilityDescription=description;
            face.setContentDescription(description);
        }
    }
    private boolean outputPlaying() {
        // A ready/Listening callback can arrive while accepted PCM still drains.
        // Use the same native playback head as performance-face cues, not a timer.
        VoiceClient.PlaybackPosition position=voice==null ? null : voice.playbackPosition();
        return position!=null && position.playing;
    }
    private void addQuietControls(FrameLayout scene) {
        float density=getResources().getDisplayMetrics().density;
        quietPanel=new android.widget.LinearLayout(this);
        // Video may reorder its panel; elevated controls must remain visible and tappable.
        quietPanel.setElevation(8*density);
        quietPanel.setOrientation(android.widget.LinearLayout.VERTICAL);
        quietPanel.setGravity(Gravity.CENTER);
        android.widget.LinearLayout row=new android.widget.LinearLayout(this);
        quietButton=new android.widget.Button(this); quietButton.setText("Quiet");
        quietButton.setContentDescription("Quiet: stop speech immediately");
        resumeButton=new android.widget.Button(this); resumeButton.setText("Resume");
        resumeButton.setContentDescription("Resume speech");
        for(android.widget.Button button:new android.widget.Button[]{quietButton,resumeButton}) {
            button.setAllCaps(false);button.setTextColor(0xFFCEFFEE);
            button.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xEE09362F));
            row.addView(button,new android.widget.LinearLayout.LayoutParams((int)(112*density),(int)(56*density)));
        }
        quietPanel.addView(row);
        quietStatus=new android.widget.TextView(this);quietStatus.setTextColor(0xFFCEFFEE);
        quietStatus.setTextSize(14);quietStatus.setGravity(Gravity.CENTER);
        quietStatus.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        quietPanel.addView(quietStatus);
        quietPanel.addOnLayoutChangeListener((view,left,top,right,bottom,oldLeft,oldTop,oldRight,oldBottom)-> {
            if(performanceVideo!=null) performanceVideo.setTopInset(bottom+(int)(16*density));
        });
        FrameLayout.LayoutParams position=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);
        position.topMargin=(int)(24*density);scene.addView(quietPanel,position);
        quietButton.setOnClickListener(v->requestQuiet(true));
        resumeButton.setOnClickListener(v->requestQuiet(false));
    }
    private void refreshQuietControls() {
        if(quietPanel==null) return;
        quietPanel.setVisibility(endpoint==null ? View.GONE : View.VISIBLE);
        boolean enabled=resumed && settingsClient!=null && !quietControl.pending;
        quietButton.setEnabled(enabled);resumeButton.setEnabled(enabled);
        String text=quietControl.status(state,outputPlaying());
        if(!text.contentEquals(quietStatus.getText())) quietStatus.setText(text);
    }
    private void persistLocalQuiet() {
        pairing.edit().putBoolean("localQuiet",quietControl.localHold).apply();
    }
    private void requestQuiet(boolean quiet) {
        if(!resumed || settingsClient==null || quietControl.pending) return;
        int request=quietControl.begin(quiet);
        if(quiet) {
            persistLocalQuiet();
            if(voice!=null) voice.setLocalQuiet(true);
            if(performanceVideo!=null) performanceVideo.clear();
        }
        refreshQuietControls();
        settingsClient.setQuiet(quiet,success -> {
            if(!quietControl.complete(request,success)) return;
            persistLocalQuiet();
            if(voice!=null) voice.setLocalQuiet(quietControl.localHold);
            refreshQuietControls();
        });
    }
    private void authenticateOwner() {
        if(ownerDialog || !resumed) return;
        android.app.KeyguardManager lock=(android.app.KeyguardManager)getSystemService(KEYGUARD_SERVICE);
        if(lock.isDeviceSecure()) {
            android.content.Intent challenge=lock.createConfirmDeviceCredentialIntent("Facebot owner setup","Unlock to change pairing or kiosk settings");
            if(challenge!=null) startActivityForResult(challenge,OWNER_AUTH);
        } else if(endpoint==null) showOwnerSetup();
        else new android.app.AlertDialog.Builder(this).setTitle("Protect owner setup")
            .setMessage("Set an Android screen lock PIN or password to unlock paired Facebot settings.")
            .setPositiveButton("Android security",(d,w)->startActivity(new android.content.Intent(android.provider.Settings.ACTION_SECURITY_SETTINGS)))
            .setNegativeButton("Cancel",null).show();
    }
    @Override protected void onActivityResult(int request,int result,android.content.Intent data) {
        super.onActivityResult(request,result,data);
        if(request==OWNER_AUTH && result==RESULT_OK) main.post(this::showOwnerSetup);
    }
    private void showOwnerSetup() {
        if(ownerDialog) return;
        ownerDialog=true; stopConnections();
        android.widget.LinearLayout form=new android.widget.LinearLayout(this);
        form.setOrientation(android.widget.LinearLayout.VERTICAL);
        int pad=(int)(20*getResources().getDisplayMetrics().density); form.setPadding(pad,pad,pad,pad);
        android.widget.TextView help=new android.widget.TextView(this);
        help.setText("Pair with your Facebot host on the same Wi-Fi. Owner settings use your Android screen lock. Hold the upper-left corner for 5 seconds to return.");form.addView(help);
        android.widget.EditText url=new android.widget.EditText(this);url.setHint("wss://host/voice");url.setSingleLine(true);url.setText(endpoint==null?"":endpoint);form.addView(url);
        android.widget.EditText secret=new android.widget.EditText(this);secret.setHint("Pairing token");secret.setSingleLine(true);
        secret.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        secret.setText(token==null?"":token);form.addView(secret);
        android.widget.CheckBox lan=new android.widget.CheckBox(this);lan.setText("Allow unencrypted private LAN (trusted Wi-Fi only)");lan.setChecked(allowPrivateLan);form.addView(lan);
        android.widget.CheckBox debug=new android.widget.CheckBox(this);debug.setText("Show owner diagnostics");debug.setChecked(diagnostics);form.addView(debug);
        android.widget.Button wifi=new android.widget.Button(this);wifi.setText("Wi-Fi settings");form.addView(wifi);
        wifi.setOnClickListener(v->startActivity(new android.content.Intent(android.provider.Settings.ACTION_WIFI_SETTINGS)));
        android.widget.Button home=new android.widget.Button(this);home.setText("Choose default Home app (optional)");form.addView(home);
        home.setOnClickListener(v->startActivity(new android.content.Intent(android.provider.Settings.ACTION_HOME_SETTINGS)));
        android.widget.Button pin=new android.widget.Button(this);pin.setText("Pin Facebot to screen (optional)");form.addView(pin);
        android.widget.TextView limits=new android.widget.TextView(this);limits.setText("Default Home can bring Facebot back after restart. Screen pinning resists accidental touches; Android still controls exit gestures, power and system dialogs. No device-owner enrollment is performed.");form.addView(limits);
        android.widget.ScrollView scroll=new android.widget.ScrollView(this);scroll.addView(form);
        android.app.AlertDialog dialog=new android.app.AlertDialog.Builder(this).setTitle("Facebot · Owner setup")
            .setView(scroll).setPositiveButton("Save & connect",null).setNegativeButton("Cancel",null).create();
        dialog.setOnDismissListener(d->{ownerDialog=false; if(resumed) startConnections(); immerse();});
        dialog.show();
        pin.setOnClickListener(v->{dialog.dismiss();startLockTask();});
        dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String nextUrl=url.getText().toString().trim(), nextToken=secret.getText().toString().trim();
            if(!ConnectionPolicy.allows(nextUrl,lan.isChecked())) { url.setError("Use wss://host/voice, or opt in to ws://private IPv4:port/voice");return; }
            if(nextToken.length()<24 || nextToken.length()>512 || !nextToken.matches("[!-~]+")) { secret.setError("Enter the host pairing token (24–512 characters)");return; }
            endpoint=nextUrl;token=nextToken;allowPrivateLan=lan.isChecked();diagnostics=debug.isChecked();failures=0;
            pairing.edit().putString("url",endpoint).putString("token",token).putBoolean("allowPrivateLan",allowPrivateLan).putBoolean("diagnostics",diagnostics).apply();
            dialog.dismiss();
        });
    }
    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) immerse();
    }
    @Override protected void onNewIntent(android.content.Intent intent) {
        super.onNewIntent(intent); setIntent(intent);
        if (intent.getBooleanExtra("renderFacePreview",false)) renderFacePreview();
        if (intent.getBooleanExtra("renderCaptionPreview",false)) renderCaptionPreview();
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
    private void renderCaptionPreview() {
        if((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)==0 || face.getWidth()==0)return;
        String previous=face.previewShape;
        String[] phrases={"I have a name.","Mill Valley Planning Department","Café — happy Halloween!","WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW"};
        try {
            face.previewShape="open";
            for(int[] size:new int[][]{{600,1000},{1000,600}})for(int index=0;index<phrases.length;index++) {
                android.graphics.Bitmap image=android.graphics.Bitmap.createBitmap(size[0],size[1],android.graphics.Bitmap.Config.ARGB_8888);
                Canvas canvas=new Canvas(image);canvas.save();
                canvas.scale((float)size[0]/face.getWidth(),(float)size[1]/face.getHeight());face.draw(canvas);canvas.restore();
                new CaptionRenderer().draw(canvas,phrases[index],size[0],size[1],0);
                try(java.io.FileOutputStream output=openFileOutput("caption-"+size[0]+"x"+size[1]+"-"+index+".png",MODE_PRIVATE)) {
                    image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,output);
                } catch(java.io.IOException ignored) { }
                image.recycle();
            }
        } finally {face.previewShape=previous;}
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
        private long lastGazeAt;
        private final Runnable thermalRedraw=() -> { if(resumed) invalidate(); };
        private Shader halo;
        private int haloInner,haloOuter;
        private final android.graphics.Typeface titleTypeface=android.graphics.Typeface.create(
            "sans-serif-condensed",android.graphics.Typeface.BOLD);
        private final MouthRenderer mouthRenderer=new MouthRenderer();
        private final CaptionRenderer captionRenderer=new CaptionRenderer();
        String previewShape;
        FaceView() {
            super(FaceActivity.this); setBackgroundColor(Color.BLACK);
            setFocusable(true); setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
            setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        }
        @Override protected void onDetachedFromWindow() {
            removeCallbacks(thermalRedraw);
            super.onDetachedFromWindow();
        }
        @Override public void onInitializeAccessibilityNodeInfo(android.view.accessibility.AccessibilityNodeInfo info) {
            super.onInitializeAccessibilityNodeInfo(info);
            info.addAction(new android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction(
                R.id.facebot_owner_setup,"Owner setup"));
        }
        @Override public boolean performAccessibilityAction(int action,Bundle arguments) {
            if(action==R.id.facebot_owner_setup) {
                authenticateOwner(); // Same credential boundary as the five-second touch gesture.
                return true;
            }
            return super.performAccessibilityAction(action,arguments);
        }
        @Override public boolean onTouchEvent(MotionEvent event) {
            if(event.getActionMasked()==MotionEvent.ACTION_DOWN && event.getX()<getWidth()*.14f && event.getY()<getHeight()*.14f)
                main.postDelayed(ownerHold,5000);
            if(event.getActionMasked()==MotionEvent.ACTION_UP || event.getActionMasked()==MotionEvent.ACTION_CANCEL ||
                event.getPointerCount()>1 || event.getX()>getWidth()*.14f || event.getY()>getHeight()*.14f) main.removeCallbacks(ownerHold);
            return true;
        }
        private void fill(int color) { paint.setShader(null); paint.setStyle(Paint.Style.FILL); paint.setColor(color); }
        private void curve(Canvas c,float ax,float ay,float bx,float by,float cx,float cy,float width,int color) {
            shape.reset(); shape.moveTo(ax,ay); shape.quadTo(bx,by,cx,cy);
            fill(color); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(width);
            paint.setStrokeCap(Paint.Cap.ROUND); c.drawPath(shape,paint); paint.setStyle(Paint.Style.FILL);
        }
        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float w=getWidth(), h=getHeight();
            long now=android.os.SystemClock.uptimeMillis();
            double t=now/1000.0;
            float blend=ThermalCadence.gazeBlend(lastGazeAt==0 ? 1000.0/60 : now-lastGazeAt);
            lastGazeAt=now;
            lookX+=(gazeX-lookX)*blend; lookY+=(gazeY-lookY)*blend;
            float dx=(lookX-.5f)*.10f, dy=(lookY-.5f)*.045f;
            float bob=(float)Math.sin(t*1.6)*.006f;
            int ice=palette[0], mint=palette[1], deep=palette[2];
            mouthRenderer.setColors(mint,ice);
            canvas.save(); canvas.scale(w,h); canvas.translate(0,bob);
            // A faint halo gives the disembodied face depth without a rectangular panel.
            if(halo==null || haloInner!=palette[3] || haloOuter!=palette[4]) {
                haloInner=palette[3];haloOuter=palette[4];
                halo=new RadialGradient(.5f,.47f,.49f,
                    new int[]{haloInner,haloOuter,Color.BLACK},null,Shader.TileMode.CLAMP);
            }
            paint.setShader(halo);
            canvas.drawRect(0,0,1,1,paint); paint.setShader(null);
            float blink=t%5.3<.12 ? .10f : 1f;
            String reaction=voice!=null?voice.expression():"neutral";
            if(reaction.equals("wolf_eyes")) { ice=Color.rgb(255,220,80);mint=Color.rgb(255,138,39);deep=Color.rgb(60,24,6); }

            for(int side=0;side<2;side++) {
                float cx=side==0?.29f:.71f;
                float cy=(side==0?.395f:.375f)+dy*.3f;
                canvas.save(); canvas.rotate(reaction.equals("wolf_eyes")?(side==0?18:-18):(side==0?-8:9),cx,cy);
                float expressionScale=(reaction.equals("scared")||reaction.equals("surprised"))?1.35f:
                    (reaction.equals("wolf_eyes"))?.62f:(reaction.equals("skeptical") && side==0)?.5f:1f;
                canvas.scale(1,blink*expressionScale,cx,cy);
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
            String caption=previewShape==null && voice!=null && !performanceVideo.isVisible()?voice.captionText():"";
            if(caption.isEmpty()) {
            fill(mint);paint.setTextAlign(Paint.Align.CENTER);
            paint.setTypeface(titleTypeface);
            paint.setTextSize(w*.045f);canvas.drawText(characterName.toUpperCase(java.util.Locale.ROOT),w*.5f,h*.80f,paint);
            paint.setTypeface(android.graphics.Typeface.DEFAULT);paint.setTextSize(w*.031f);paint.setAlpha(190);
            String visitorState=KioskStatus.visitorText(state,quietControl.localHold,outputPlaying());
            canvas.drawText(previewShape!=null?"SYNTHETIC / "+previewShape:visitorState,w*.5f,h*.85f,paint);paint.setAlpha(255);
            if(endpoint==null) { paint.setTextSize(w*.024f);canvas.drawText("Owner: hold the upper-left corner for 5 seconds",w*.5f,h*.90f,paint); }
            if(diagnostics) { paint.setTextSize(w*.022f);canvas.drawText(visionState,w*.5f,h*.94f,paint); }
            if(diagnostics && !sceneLabels.isEmpty()) {
                paint.setTextSize(w*.018f);paint.setAlpha(140);
                canvas.drawText("Seeing: "+sceneLabels,w*.5f,h*.915f,paint);paint.setAlpha(255);
            }
            } else {
                android.view.WindowInsets insets=getRootWindowInsets();
                captionRenderer.draw(canvas,caption,w,h,insets!=null?insets.getStableInsetBottom():0);
            }
            removeCallbacks(thermalRedraw);
            if(resumed) {
                int delay=thermalCadence.redrawDelayMs();
                if(delay==0) postInvalidateOnAnimation();
                else postOnAnimationDelayed(thermalRedraw,delay);
            }
        }
    }
}
