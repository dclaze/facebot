package org.facebot;

import android.content.Context;
import android.graphics.Color;
import android.media.MediaPlayer;
import android.graphics.Matrix;
import android.graphics.SurfaceTexture;
import android.view.Surface;
import android.view.TextureView;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;
import okhttp3.Call;
import okhttp3.HttpUrl;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import org.json.JSONObject;

/** Download/verify ahead, then show muted video against the existing audio clock. */
final class PerformanceVideo {
    private static final long MAX_BYTES=64L*1024*1024;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService downloads=Executors.newSingleThreadExecutor();
    private final OkHttpClient http=new OkHttpClient.Builder().followRedirects(false)
        .followSslRedirects(false).callTimeout(30,TimeUnit.SECONDS).build();
    private final FrameLayout panel;
    private final TextureView texture;
    private MediaPlayer player;
    private Surface surface;
    private final String filePrefix="facebot-video-"+java.util.UUID.randomUUID()+"-";
    private final File cache;
    private final Supplier<VoiceClient.PlaybackPosition> clock;
    private PerformanceVideoCue cue;
    private Call request;
    private int generation;
    private boolean prepared, visible, started, completed;
    private long lastCorrection;
    private final Runnable tick=this::tick;

    PerformanceVideo(Context context,FrameLayout scene,Supplier<VoiceClient.PlaybackPosition> clock) {
        this.clock=clock;cache=context.getCacheDir();
        panel=new FrameLayout(context);panel.setBackgroundColor(Color.BLACK);
        texture=new TextureView(context);
        texture.setOnTouchListener((view,event)->true);
        texture.setSurfaceTextureListener(new TextureView.SurfaceTextureListener(){
            public void onSurfaceTextureAvailable(SurfaceTexture value,int width,int height){
                surface=new Surface(value);if(player!=null)player.setSurface(surface);fit();tick();
            }
            public void onSurfaceTextureSizeChanged(SurfaceTexture value,int width,int height){fit();}
            public boolean onSurfaceTextureDestroyed(SurfaceTexture value){
                if(player!=null)player.setSurface(null);if(surface!=null)surface.release();surface=null;return true;
            }
            public void onSurfaceTextureUpdated(SurfaceTexture value){}
        });
        panel.addView(texture,new FrameLayout.LayoutParams(-1,-1,Gravity.CENTER));
        scene.addView(panel,new FrameLayout.LayoutParams(-1,-1));
        panel.setVisibility(View.INVISIBLE);
    }
    void setTopInset(int pixels) {
        FrameLayout.LayoutParams layout=(FrameLayout.LayoutParams)panel.getLayoutParams();
        if(layout.topMargin==pixels) return;
        layout.topMargin=pixels;panel.setLayoutParams(layout);
    }
    boolean isVisible(){return visible;}
    void receive(JSONObject event,String voiceURL,String token,boolean allowPrivateLan) {
        final PerformanceVideoCue next;
        final HttpUrl origin;
        try {
            next=new PerformanceVideoCue(event.getString("id"),event.getString("path"),
                event.getLong("epoch"),event.getLong("offset"),event.getLong("duration_ms"));
            origin=HttpUrl.parse(voiceURL.replaceFirst("^ws","http"));
            if(!ConnectionPolicy.allows(voiceURL,allowPrivateLan)) throw new IllegalArgumentException();
        } catch(Exception error) { Log.w("FacebotVideo","event=error reason=invalid_cue");return; }
        VoiceClient.PlaybackPosition position=clock.get();
        if(position==null || next.epoch!=position.epoch) return;
        clear("replaced");cue=next;final int current=generation;
        // Resolve a validated absolute path on the paired origin; never follow redirects.
        request=http.newCall(new Request.Builder().url(origin.resolve(next.path))
            .header("Authorization","Bearer "+token).build());
        final Call call=request;
        downloads.execute(()->download(call,next,current));
        main.post(tick);
    }
    private void download(Call call,PerformanceVideoCue expected,int current) {
        File temporary=new File(cache,filePrefix+current+".part");
        File verified=new File(cache,filePrefix+current+".mp4");
        try(Response response=call.execute()) {
            if(response.code()!=200 || response.body()==null || response.body().contentLength()>MAX_BYTES)
                throw new IllegalArgumentException("Invalid media response");
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            long bytes=0;
            try(InputStream input=response.body().byteStream();FileOutputStream output=new FileOutputStream(temporary)) {
                byte[] block=new byte[32768];int count;
                while((count=input.read(block))!=-1) {
                    bytes+=count;if(bytes>MAX_BYTES || call.isCanceled()) throw new IllegalArgumentException("Media cancelled or too large");
                    digest.update(block,0,count);output.write(block,0,count);
                }
            }
            StringBuilder hash=new StringBuilder();for(byte b:digest.digest())hash.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
            if(bytes==0 || !hash.toString().equals(expected.sha256) || !temporary.renameTo(verified))
                throw new IllegalArgumentException("Media checksum mismatch");
            main.post(()->{
                if(current!=generation || cue!=expected){verified.delete();return;}
                request=null;
                Log.i("FacebotVideo","event=verified");
                player=new MediaPlayer();
                // MediaPlayer never requests audio focus. Only the PCM voice track is audible.
                player.setVolume(0,0);
                if(surface!=null)player.setSurface(surface);
                player.setOnPreparedListener(media->{
                    if(current!=generation)return;
                    media.setVolume(0,0);media.setLooping(false);prepared=true;fit();
                    // Duration is checked against the audio-owned presentation interval.
                    if(Math.abs(media.getDuration()-expected.durationMs)>1500){
                        Log.w("FacebotVideo","event=error reason=duration_mismatch");clear("error");return;
                    }
                    Log.i("FacebotVideo","event=prepared duration_ms="+media.getDuration());
                    tick();
                });
                player.setOnErrorListener((media,what,extra)->{
                    if(current==generation){
                        Log.w("FacebotVideo","event=error reason=decoder what="+what+" extra="+extra);
                        clear("error");
                    }
                    return true;
                });
                player.setOnCompletionListener(media->{if(current==generation)completed=true;});
                try {player.setDataSource(verified.getAbsolutePath());player.prepareAsync();}
                catch(Exception error){Log.w("FacebotVideo","event=error reason=prepare");clear("error");}
            });
        } catch(Exception error) {
            verified.delete();
            main.post(()->{if(current==generation){Log.w("FacebotVideo","event=error reason=download_or_verify");clear("error");}});
        } finally {temporary.delete();}
    }
    private void tick() {
        main.removeCallbacks(tick);
        if(cue==null)return;
        VoiceClient.PlaybackPosition position=clock.get();
        if(position==null){clear("clock_unavailable");return;}
        if(cue.ended(position.epoch,position.sample,position.playing)){
            clear(position.epoch!=cue.epoch?"epoch_changed":"audio_end");return;
        }
        if(prepared && cue.active(position.epoch,position.sample)) {
            int target=cue.positionMs(position.sample);
            visible=true;panel.bringToFront();panel.setVisibility(View.VISIBLE);
            if(surface==null){main.postDelayed(tick,33);return;}
            if(!started) {
                player.seekTo(target,MediaPlayer.SEEK_CLOSEST);player.start();started=true;
                Log.i("FacebotVideo","event=start audio_sample="+position.sample+" target_ms="+target);
            }
            if(!position.playing) { if(player.isPlaying())player.pause(); }
            else if(!completed && !player.isPlaying())player.start();
            long now=SystemClock.elapsedRealtime();
            if(!completed && now-lastCorrection>=200 && Math.abs(player.getCurrentPosition()-target)>150) {
                player.seekTo(target,MediaPlayer.SEEK_CLOSEST);lastCorrection=now;
            }
        }
        main.postDelayed(tick,33);
    }
    private void fit() {
        if(player==null || !prepared || texture.getWidth()==0 || texture.getHeight()==0)return;
        int w=player.getVideoWidth(),h=player.getVideoHeight();if(w<=0||h<=0)return;
        float scale=Math.min((float)texture.getWidth()/w,(float)texture.getHeight()/h);
        Matrix transform=new Matrix();
        transform.setScale(w*scale/texture.getWidth(),h*scale/texture.getHeight(),texture.getWidth()/2f,texture.getHeight()/2f);
        texture.setTransform(transform);
    }
    void clear(){clear("cleared");}
    private void clear(String reason) {
        if(cue!=null)Log.i("FacebotVideo","event=end reason="+reason);
        generation++;cue=null;prepared=false;visible=false;started=false;completed=false;lastCorrection=0;
        main.removeCallbacks(tick);
        if(request!=null){request.cancel();request=null;}
        if(player!=null){player.release();player=null;}panel.setVisibility(View.INVISIBLE);
        File[] files=cache.listFiles((dir,name)->name.startsWith(filePrefix)&&name.endsWith(".mp4"));
        if(files!=null)for(File file:files)file.delete();
    }
    void close(){clear();downloads.shutdownNow();http.dispatcher().executorService().shutdown();http.connectionPool().evictAll();}
}
