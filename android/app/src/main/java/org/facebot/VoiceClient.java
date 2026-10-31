package org.facebot;

import android.content.Context;
import android.media.*;
import android.media.audiofx.AcousticEchoCanceler;
import android.util.Log;
import org.json.JSONObject;
import org.json.JSONArray;
import java.util.ArrayDeque;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import okhttp3.*;
import okio.ByteString;

/** Continuous native capture/playback. No recordings or transcript storage. */
final class VoiceClient extends WebSocketListener {
    interface Listener { void state(String state, boolean speaking); }
    private final Context context;
    private final Listener listener;
    private final OkHttpClient http = new OkHttpClient.Builder().connectTimeout(5, TimeUnit.SECONDS).pingInterval(5, TimeUnit.SECONDS).followRedirects(false).followSslRedirects(false).build();
    private final ExecutorService control = Executors.newSingleThreadExecutor();
    private final PlaybackQueue output = new PlaybackQueue();
    private final AtomicBoolean closed = new AtomicBoolean(false);
    private final Object audioLock = new Object();
    private final ArrayDeque<MouthCue> mouthCues = new ArrayDeque<>();
    private final CaptionTimeline captions = new CaptionTimeline();
    private final PlaybackProbe playbackProbe=new PlaybackProbe();
    private final KioskStatus kioskStatus=new KioskStatus();
    private long writtenSamples;
    private java.util.function.Consumer<JSONObject> videoListener=event -> {};
    void setVideoListener(java.util.function.Consumer<JSONObject> listener){videoListener=listener;}
    static final class PlaybackPosition {
        final long epoch,sample;final boolean playing;
        PlaybackPosition(long epoch,long sample,boolean playing){this.epoch=epoch;this.sample=sample;this.playing=playing;}
    }
    PlaybackPosition playbackPosition(){
        synchronized(audioLock){
            if(player==null || closed.get())return null;
            long sample=Integer.toUnsignedLong(player.getPlaybackHeadPosition());
            return new PlaybackPosition(epoch,sample,sample<writtenSamples);
        }
    }
    private static final class MouthCue {
        final long start, end; final String shape;
        MouthCue(long start,long end,String shape) { this.start=start;this.end=end;this.shape=shape; }
    }
    private volatile WebSocket socket;
    private volatile long epoch = 0;
    private AudioRecord recorder;
    private AudioTrack player;
    private AcousticEchoCanceler echo;
    private Thread captureThread, playbackThread;
    private AudioManager manager;
    private int oldMode;
    private boolean oldSpeaker;
    private boolean captureObserved, playbackObserved;
    private long lastSceneSent;
    private int lastFaceCount = -1;
    private final PerformanceFaceCue performanceFace=new PerformanceFaceCue();
    private volatile String expression = "neutral";
    private volatile long expressionUntil;
    String expression() {
        synchronized(audioLock) {
            if(player!=null && !closed.get()) {
                String cue=performanceFace.at(epoch,Integer.toUnsignedLong(player.getPlaybackHeadPosition()),writtenSamples);
                if(!cue.isEmpty()) return cue;
            }
        }
        return android.os.SystemClock.elapsedRealtime()<expressionUntil ? expression : "neutral";
    }
    VoiceClient(Context context, Listener listener) { this.context=context; this.listener=listener; }
    String mouthShape() {
        synchronized(audioLock) {
            if (player==null || closed.get()) return "rest";
            long sample=Integer.toUnsignedLong(player.getPlaybackHeadPosition());
            while(!mouthCues.isEmpty() && mouthCues.peekFirst().end<=sample) mouthCues.removeFirst();
            MouthCue cue=mouthCues.peekFirst();
            return cue!=null && cue.start<=sample ? cue.shape : "rest";
        }
    }
    String captionText() {
        synchronized(audioLock) {
            if(player==null || closed.get()) return "";
            long sample=Integer.toUnsignedLong(player.getPlaybackHeadPosition());
            String text=captions.textAt(sample);
            return sample<writtenSamples ? text : "";
        }
    }
    /** Called on the main camera-result executor; drops updates behind audio. */
    void observeScene(int faces, long analysisMs, int faceFill) {
        long now=android.os.SystemClock.elapsedRealtime();
        if (closed.get() || socket==null || analysisMs<0 || analysisMs>500 || faces<0 || socket.queueSize()>1280) return;
        if (now-lastSceneSent<100 || (faces==lastFaceCount && now-lastSceneSent<250)) return;
        try {
            JSONObject event=new JSONObject();
            event.put("type","scene"); event.put("visible_faces",Math.min(32,faces)); event.put("overflow",faces>32); event.put("age_ms",analysisMs);
            event.put("face_fill",Math.max(0,Math.min(1000,faceFill)));
            if (socket.send(event.toString())) { lastSceneSent=now; lastFaceCount=faces; }
        } catch(Exception ignored) { /* Vision must not block or tear down audio. */ }
    }
    void connect(String url, String token, boolean allowPrivateLan) {
        if (!ConnectionPolicy.allows(url,allowPrivateLan)) {
            listener.state("Check owner connection settings", false); close(); return;
        }
        if (token==null || token.length()<24) { listener.state("Pairing required",false); close(); return; }
        listener.state("Connecting",false);
        socket=http.newWebSocket(new Request.Builder().url(url).header("Authorization","Bearer "+token)
            .header("X-Facebot-Capabilities","performance-video-v1,performance-face-v1,playback-probe-v1").build(),this);
    }
    @Override public void onOpen(WebSocket ws, Response response) {
        if (closed.get()) { ws.cancel(); return; }
        control.execute(() -> {
            try {
                if (closed.get()) return;
                manager=(AudioManager)context.getSystemService(Context.AUDIO_SERVICE);
                oldMode=manager.getMode(); oldSpeaker=manager.isSpeakerphoneOn();
                manager.setMode(AudioManager.MODE_IN_COMMUNICATION); manager.setSpeakerphoneOn(true);
                int inSize=AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);
                recorder=new AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION,16000,AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,Math.max(3200,inSize));
                if (recorder.getState()!=AudioRecord.STATE_INITIALIZED) throw new IllegalStateException();
                if (AcousticEchoCanceler.isAvailable()) {
                    echo=AcousticEchoCanceler.create(recorder.getAudioSessionId());
                    if (echo!=null) echo.setEnabled(true);
                }
                Log.i("FacebotAudio", "Native capture initialized; platform AEC enabled=" + (echo!=null && echo.getEnabled()));
                int outSize=AudioTrack.getMinBufferSize(24000,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT);
                synchronized(audioLock) {
                    player=new AudioTrack.Builder().setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                        .setAudioFormat(new AudioFormat.Builder().setSampleRate(24000).setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build()).setBufferSizeInBytes(Math.max(1920,outSize))
                        .setTransferMode(AudioTrack.MODE_STREAM).build();
                    if (player.getState()!=AudioTrack.STATE_INITIALIZED) throw new IllegalStateException();
                    player.play();
                }
                recorder.startRecording();
                captureThread=new Thread(this::capture,"facebot-capture");
                playbackThread=new Thread(this::playback,"facebot-playback");
                captureThread.start(); playbackThread.start();
                listener.state(kioskStatus.readyText(),false);
            } catch(Exception error) { fail(); }
        });
    }
    private void capture() {
        android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_AUDIO);
        byte[] pcm=new byte[640];
        try {
            while(!closed.get()) {
                int n=recorder.read(pcm,0,pcm.length,AudioRecord.READ_BLOCKING);
                if (n<=0) { if(!closed.get()) fail(); break; }
                if (!captureObserved) {
                    captureObserved=true;
                    Log.i("FacebotAudio", "Native microphone PCM received");
                }
                WebSocket ws=socket;
                if(ws==null || ws.queueSize()>6400 || !ws.send(ByteString.of(pcm,0,n))) { fail(); break; }
            }
        } catch(Exception error) { if(!closed.get()) fail(); }
    }
    private void playback() {
        android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_AUDIO);
        try {
            while(!closed.get()) {
                PlaybackQueue.Packet p=output.poll();
                if(p==null) {
                    observePlayback();
                    listener.state(kioskStatus.readyText(),false); continue;
                }
                int offset=0;
                while(offset<p.pcm.length && !closed.get() && p.epoch==epoch) {
                    int n;
                    synchronized(audioLock) {
                        if(player==null || p.epoch!=epoch) break;
                        n=player.write(p.pcm,offset,Math.min(960,p.pcm.length-offset),AudioTrack.WRITE_NON_BLOCKING);
                        if(n>0) writtenSamples+=n/2;
                    }
                    if(n<0) { fail(); return; }
                    offset+=n;
                    if(n==0) Thread.sleep(2);
                }
                if(p.epoch==epoch && !closed.get()) listener.state(kioskStatus.readyText(),true);
                observePlayback();
            }
        } catch(InterruptedException done) { Thread.currentThread().interrupt(); }
        catch(Exception error) { if(!closed.get()) fail(); }
    }
    private void observePlayback() {
        PlaybackProbe.Receipt receipt=null;
        synchronized(audioLock) {
            if(player!=null && !closed.get()) receipt=playbackProbe.observed(epoch,
                Integer.toUnsignedLong(player.getPlaybackHeadPosition()),android.os.SystemClock.elapsedRealtime());
            if (!playbackObserved && player!=null && player.getPlaybackHeadPosition()!=0) {
                playbackObserved=true;
                Log.i("FacebotAudio", "Native playback head advanced; received server PCM consumed");
            }
        }
        if(receipt!=null && !closed.get()) {
            try {
                JSONObject event=new JSONObject();event.put("type","playback_receipt");event.put("id",receipt.id);
                event.put("epoch",receipt.epoch);event.put("sample",receipt.sample);
                WebSocket ws=socket;
                if(ws!=null) ws.send(event.toString());
            } catch(Exception ignored) { /* Diagnostic receipts never affect audio. */ }
        }
    }
    @Override public void onMessage(WebSocket ws, ByteString bytes) {
        if(closed.get()) return;
        byte[] message=bytes.toByteArray();
        if(message.length<=8 || message.length>8+PlaybackQueue.MAX_PCM_BYTES || (message.length-8)%2!=0) { fail(); return; }
        long incoming=ByteBuffer.wrap(message,0,8).order(ByteOrder.BIG_ENDIAN).getLong();
        if(incoming<epoch) return;
        if(incoming>epoch) flush(incoming);
        if(!output.offer(incoming,Arrays.copyOfRange(message,8,message.length)))
            fail(); // Atomic rejection on overrun; never accumulate unbounded stale speech.
    }
    @Override public void onMessage(WebSocket ws,String message) {
        if(closed.get()) return;
        try {
            JSONObject event=new JSONObject(message);
            if(event.getString("type").equals("interrupt")) { expressionUntil=0; flush(event.getLong("epoch")); }
            else if(event.getString("type").equals("performance_video")) {
                long incoming=event.getLong("epoch");
                if(incoming<epoch)return;
                if(incoming>epoch)flush(incoming);
                videoListener.accept(event);
            }
            else if(event.getString("type").equals("kiosk_state")) {
                long incoming=event.getLong("epoch");
                if(incoming<epoch) return;
                if(!(event.get("muted") instanceof Boolean)) return;
                if(incoming>epoch) flush(incoming);
                synchronized(audioLock) {
                    kioskStatus.apply(incoming,epoch,event.getBoolean("muted"));
                }
                listener.state(kioskStatus.readyText(),false);
            }
            else if(event.getString("type").equals("playback_probe")) {
                synchronized(audioLock) {
                    playbackProbe.arm(event.getString("id"),event.getLong("epoch"),epoch,
                        event.getLong("offset"),android.os.SystemClock.elapsedRealtime());
                }
            }
            else if(event.getString("type").equals("performance_face")) {
                long incoming=event.getLong("epoch");
                if(incoming<epoch) return;
                if(incoming>epoch) flush(incoming);
                synchronized(audioLock) {
                    performanceFace.set(incoming,event.getLong("offset"),event.getLong("duration_samples"),event.getString("name"));
                }
            }
            else if(event.getString("type").equals("expression")) {
                String name=event.getString("name"); int duration=event.getInt("duration_ms");
                if(event.getLong("epoch")==epoch && duration>=100 && duration<=2500 &&
                    Arrays.asList("neutral","skeptical","surprised","scared","pleased").contains(name)) {
                    expression=name; expressionUntil=android.os.SystemClock.elapsedRealtime()+duration;
                }
            }
            else if(event.getString("type").equals("visemes")) {
                long incoming=event.getLong("epoch");
                if(incoming<epoch) return;
                if(incoming>epoch) flush(incoming);
                long offset=event.getLong("offset");
                JSONArray cues=event.getJSONArray("cues");
                if(cues.length()>1024 || offset<0) { fail(); return; }
                synchronized(audioLock) {
                    if(event.has("captions")) {
                        JSONArray values=event.getJSONArray("captions");
                        java.util.ArrayList<CaptionTimeline.Cue> batch=new java.util.ArrayList<>();
                        if(values.length()>512) throw new IllegalArgumentException();
                        for(int i=0;i<values.length();i++) {
                            JSONArray cue=values.getJSONArray(i);
                            if(cue.length()!=3) throw new IllegalArgumentException();
                            batch.add(new CaptionTimeline.Cue(cue.getLong(0),cue.getLong(1),cue.getString(2)));
                        }
                        captions.append(incoming,offset,batch);
                    }
                    if(mouthCues.size()+cues.length()>2048) throw new IllegalArgumentException();
                    long previous=-1;
                    for(int i=0;i<cues.length();i++) {
                        JSONArray cue=cues.getJSONArray(i);
                        long start=cue.getLong(0), end=cue.getLong(1);
                        String shape=cue.getString(2);
                        if(start<previous || end<=start || end>24000*30 ||
                           !Arrays.asList("rest","closed","teeth","tongue","pucker","round","open","wide","narrow").contains(shape))
                            throw new IllegalArgumentException();
                        mouthCues.addLast(new MouthCue(offset+start,offset+end,shape)); previous=end;
                    }
                }
            }
        } catch(Exception error) { fail(); }
    }
    private void flush(long next) {
        synchronized(audioLock) {
            if(next<epoch) return;
            epoch=next; playbackProbe.reset(); performanceFace.reset(); output.clear(); mouthCues.clear(); captions.reset(next); writtenSamples=0;
            if(player!=null) { player.pause(); player.flush(); if(!closed.get()) player.play(); }
        }
        listener.state(kioskStatus.readyText(),false);
    }
    @Override public void onFailure(WebSocket ws,Throwable error,Response response) { fail(); }
    @Override public void onClosed(WebSocket ws,int code,String reason) { fail(); }
    private void fail() {
        if(closed.get()) return;
        close();
        listener.state("Reconnecting",false);
    }
    void close() {
        if(!closed.compareAndSet(false,true)) return;
        if(socket!=null) socket.cancel();
        output.clear();
        kioskStatus.reset();
        synchronized(audioLock) {
            mouthCues.clear(); captions.reset(epoch); playbackProbe.reset(); performanceFace.reset();
            if(player!=null) { try { player.pause(); player.flush(); } catch(IllegalStateException ignored) { } }
        }
        control.execute(() -> {
            try {
                if(recorder!=null) recorder.stop();
                if(captureThread!=null) captureThread.join(500);
                if(playbackThread!=null) { playbackThread.interrupt(); playbackThread.join(500); }
            } catch(Exception ignored) { }
            synchronized(audioLock) { if(player!=null) { player.pause(); player.flush(); player.release(); player=null; } }
            if(echo!=null) echo.release();
            if(recorder!=null) recorder.release();
            if(manager!=null) { manager.setSpeakerphoneOn(oldSpeaker); manager.setMode(oldMode); }
            http.dispatcher().executorService().shutdown(); http.connectionPool().evictAll();
            control.shutdown();
        });
    }
}
