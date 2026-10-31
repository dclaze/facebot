package org.facebot;

import android.graphics.Bitmap;
import android.graphics.Matrix;
import androidx.camera.core.ImageProxy;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import okhttp3.*;
import okio.ByteString;
import org.json.JSONObject;

/** Sampled images over a separate socket. One in flight, no recording or backlog. */
final class VisionClient extends WebSocketListener {
    interface Listener { void labels(String labels); }
    private final OkHttpClient http = new OkHttpClient.Builder().pingInterval(10,TimeUnit.SECONDS).build();
    private final ExecutorService encode = Executors.newSingleThreadExecutor();
    private final ScheduledExecutorService network = Executors.newSingleThreadScheduledExecutor();
    private final AtomicBoolean pending = new AtomicBoolean();
    private final Listener listener;
    private volatile WebSocket socket;
    private volatile boolean closed, ready;
    private volatile long lastCapture;
    private Request request;
    VisionClient(String url,String token,boolean allowPrivateLan,Listener listener) {
        this.listener=listener;
        HttpUrl target=HttpUrl.parse(url.replaceFirst("^ws","http"));
        if(!ConnectionPolicy.allows(url,allowPrivateLan)) {
            closed=true; return;
        }
        request=new Request.Builder().url(target.newBuilder().encodedPath("/vision").build())
            .header("Authorization","Bearer "+token).build();
        connect();
        network.scheduleWithFixedDelay(() -> {
            if(!closed && pending.get() && android.os.SystemClock.elapsedRealtime()-lastCapture>25000 && socket!=null) socket.cancel();
        },5,5,TimeUnit.SECONDS);
    }
    private void connect() { if(!closed) socket=http.newWebSocket(request,this); }
    @Override public void onOpen(WebSocket ws,Response response) { if(closed) { ws.cancel(); return; } ready=true; }
    /** Must copy pixels before MlKitAnalyzer closes the ImageProxy. */
    void sample(ImageProxy image) {
        long now=android.os.SystemClock.elapsedRealtime();
        if(closed || !ready || now-lastCapture<1500 || !pending.compareAndSet(false,true)) return;
        lastCapture=now;
        try {
            Bitmap pixels=image.toBitmap();
            int rotation=image.getImageInfo().getRotationDegrees();
            encode.execute(() -> {
                Bitmap scaled=null,rotated=null;
                try {
                    float ratio=Math.min(1f,448f/Math.max(pixels.getWidth(),pixels.getHeight()));
                    scaled=Bitmap.createScaledBitmap(pixels,Math.max(1,Math.round(pixels.getWidth()*ratio)),Math.max(1,Math.round(pixels.getHeight()*ratio)),true);
                    Matrix matrix=new Matrix(); matrix.postRotate(rotation);
                    rotated=Bitmap.createBitmap(scaled,0,0,scaled.getWidth(),scaled.getHeight(),matrix,true);
                    ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                    rotated.compress(Bitmap.CompressFormat.JPEG,75,bytes);
                    long age=android.os.SystemClock.elapsedRealtime()-now;
                    byte[] jpeg=bytes.toByteArray();
                    if(closed || age>1000 || jpeg.length>256000 || socket==null || socket.queueSize()>0) { pending.set(false); return; }
                    ByteBuffer packet=ByteBuffer.allocate(4+jpeg.length).putInt((int)age).put(jpeg);
                    if(!socket.send(ByteString.of(packet.array()))) pending.set(false);
                } catch(Exception e) { pending.set(false); }
                finally {
                    if(rotated!=null && rotated!=scaled && rotated!=pixels) rotated.recycle();
                    if(scaled!=null && scaled!=pixels) scaled.recycle();
                    pixels.recycle();
                }
            });
        } catch(Exception e) { pending.set(false); }
    }
    @Override public void onMessage(WebSocket ws,String message) {
        if(closed || ws!=socket) return;
        pending.set(false);
        try {
            JSONObject value=new JSONObject(message);
            if(value.has("labels")) listener.labels(value.getJSONArray("labels").join(", ").replace("\"",""));
        } catch(Exception ignored) { }
    }
    private void retry(WebSocket ws) {
        if(ws!=socket || closed) return;
        socket=null; ready=false; pending.set(false); listener.labels("");
        try { network.schedule(this::connect,2,TimeUnit.SECONDS); } catch(RejectedExecutionException ignored) { }
    }
    @Override public void onFailure(WebSocket ws,Throwable error,Response response) { retry(ws); }
    @Override public void onClosing(WebSocket ws,int code,String reason) { ws.close(code,reason); }
    @Override public void onClosed(WebSocket ws,int code,String reason) { retry(ws); }
    void close() {
        closed=true; ready=false;
        if(socket!=null) socket.cancel();
        encode.shutdown(); network.shutdownNow(); http.dispatcher().executorService().shutdown();
        http.connectionPool().evictAll();
    }
}
