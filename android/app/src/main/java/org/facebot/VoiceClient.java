package org.facebot;

import android.content.Context;
import android.media.*;
import android.media.audiofx.AcousticEchoCanceler;
import android.util.Log;
import org.json.JSONObject;
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
    private final OkHttpClient http = new OkHttpClient.Builder().pingInterval(10, TimeUnit.SECONDS).build();
    private final ExecutorService control = Executors.newSingleThreadExecutor();
    private final PlaybackQueue output = new PlaybackQueue();
    private final AtomicBoolean closed = new AtomicBoolean(false);
    private final Object audioLock = new Object();
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
    VoiceClient(Context context, Listener listener) { this.context=context; this.listener=listener; }
    void connect(String url, String token) {
        // Plaintext is restricted to authorized USB reverse / simulator loopback.
        HttpUrl endpoint=HttpUrl.parse(url.replaceFirst("^ws", "http"));
        if (endpoint==null || (!endpoint.isHttps() && !endpoint.host().equals("127.0.0.1") && !endpoint.host().equals("localhost"))) {
            listener.state("Secure connection required", false); close(); return;
        }
        if (token.length()<24) { listener.state("Pairing required",false); close(); return; }
        listener.state("Connecting",false);
        socket=http.newWebSocket(new Request.Builder().url(url).header("Authorization","Bearer "+token).build(),this);
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
                listener.state("Listening",false);
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
                    listener.state("Listening",false); continue;
                }
                int offset=0;
                while(offset<p.pcm.length && !closed.get() && p.epoch==epoch) {
                    int n;
                    synchronized(audioLock) {
                        if(player==null || p.epoch!=epoch) break;
                        n=player.write(p.pcm,offset,Math.min(960,p.pcm.length-offset),AudioTrack.WRITE_NON_BLOCKING);
                    }
                    if(n<0) { fail(); return; }
                    offset+=n;
                    if(n==0) Thread.sleep(2);
                }
                if(p.epoch==epoch && !closed.get()) listener.state("Listening",true);
                observePlayback();
            }
        } catch(InterruptedException done) { Thread.currentThread().interrupt(); }
        catch(Exception error) { if(!closed.get()) fail(); }
    }
    private void observePlayback() {
        synchronized(audioLock) {
            if (!playbackObserved && player!=null && player.getPlaybackHeadPosition()!=0) {
                playbackObserved=true;
                Log.i("FacebotAudio", "Native playback head advanced; received server PCM consumed");
            }
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
            if(event.getString("type").equals("interrupt")) flush(event.getLong("epoch"));
        } catch(Exception error) { fail(); }
    }
    private void flush(long next) {
        synchronized(audioLock) {
            if(next<epoch) return;
            epoch=next; output.clear();
            if(player!=null) { player.pause(); player.flush(); if(!closed.get()) player.play(); }
        }
        listener.state("Listening",false);
    }
    @Override public void onFailure(WebSocket ws,Throwable error,Response response) { fail(); }
    @Override public void onClosed(WebSocket ws,int code,String reason) { fail(); }
    private void fail() { if(!closed.get()) { listener.state("Reconnecting",false); close(); } }
    void close() {
        if(!closed.compareAndSet(false,true)) return;
        if(socket!=null) socket.cancel();
        output.clear();
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
