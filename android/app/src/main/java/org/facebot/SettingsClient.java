package org.facebot;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import org.json.JSONObject;
import org.json.JSONArray;
import okhttp3.*;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

/** Owner settings over the existing authenticated transport. No media or visitor data. */
final class SettingsClient implements AutoCloseable {
    interface Listener { void apply(String name, int[] colors); }
    private final Handler main = new Handler(Looper.getMainLooper());
    private final OkHttpClient http = new OkHttpClient.Builder().callTimeout(3, TimeUnit.SECONDS)
        .followRedirects(false).followSslRedirects(false).build();
    private final Context context;
    private final Listener listener;
    private final Request request;
    private boolean closed;
    private Call pending, controlCall;
    private final Runnable refresh = this::fetch;

    SettingsClient(Context context, String endpoint, String token, boolean allowPrivateLan, Listener listener) {
        this.context=context; this.listener=listener;
        HttpUrl url=HttpUrl.get(endpoint.replaceFirst("^ws", "http"));
        if (!ConnectionPolicy.allows(endpoint,allowPrivateLan))
            throw new IllegalArgumentException("Secure settings transport required");
        request=new Request.Builder().url(url.newBuilder().encodedPath("/runtime-settings").query(null).build())
            .header("Authorization", "Bearer "+token).build();
        String saved=context.getSharedPreferences("runtime-settings",0).getString("snapshot",null);
        if(saved!=null) apply(saved);
        fetch();
    }
    private void apply(String raw) {
        try {
            if(raw.length()>2048) return;
            JSONObject data=new JSONObject(raw);
            String name=data.getString("character_name");
            if(!name.matches("[A-Za-z][A-Za-z -]{0,23}")) return;
            JSONArray values=data.getJSONArray("colors");
            if(values.length()!=5) return;
            int[] colors=new int[5];
            for(int i=0;i<5;i++) {
                String hex=values.getString(i);
                if(!hex.matches("#[0-9A-Fa-f]{6}")) return;
                colors[i]=android.graphics.Color.parseColor(hex);
            }
            listener.apply(name,colors);
            context.getSharedPreferences("runtime-settings",0).edit().putString("snapshot",raw).apply();
        } catch(Exception ignored) { /* Keep the last valid face on transient failure. */ }
    }
    private void fetch() {
        if(closed) return;
        pending=http.newCall(request);
        pending.enqueue(new Callback() {
            public void onFailure(Call call, IOException error) { complete(null); }
            public void onResponse(Call call, Response response) {
                String raw=null;
                try(Response r=response) {
                    if(r.isSuccessful() && r.body()!=null) {
                        r.body().source().request(2049);
                        byte[] bytes=r.body().source().readByteArray(Math.min(2049,r.body().source().getBuffer().size()));
                        if(bytes.length<=2048) raw=new String(bytes,java.nio.charset.StandardCharsets.UTF_8);
                    }
                } catch(Exception ignored) { }
                complete(raw);
            }
        });
    }
    private void complete(String raw) {
        main.post(() -> {
            if(closed) return;
            pending=null;
            if(raw!=null) apply(raw);
            main.postDelayed(refresh,2000);
        });
    }
    void setQuiet(boolean quiet, java.util.function.Consumer<Boolean> complete) {
        if(closed) { complete.accept(false); return; }
        Request command=request.newBuilder().url(request.url().newBuilder()
            .encodedPath(quiet ? "/owner/stop" : "/owner/resume").query(null).build())
            .post(RequestBody.create(new byte[0],null)).build();
        controlCall=http.newCall(command);
        controlCall.enqueue(new Callback() {
            public void onFailure(Call call,IOException error) { finish(false); }
            public void onResponse(Call call,Response response) {
                boolean accepted=false;
                try(Response r=response) {
                    if(r.isSuccessful() && r.body()!=null) {
                        r.body().source().request(257);
                        byte[] bytes=r.body().source().readByteArray(Math.min(257,r.body().source().getBuffer().size()));
                        if(bytes.length<=256) {
                            String status=new JSONObject(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).optString("status");
                            accepted=quiet ? status.equals("muted") : status.equals("unmuted") || status.equals("disconnected");
                        }
                    }
                } catch(Exception ignored) { }
                finish(accepted);
            }
            private void finish(boolean accepted) {
                main.post(() -> { if(!closed) { controlCall=null; complete.accept(accepted); } });
            }
        });
    }
    public void close() {
        closed=true; main.removeCallbacks(refresh);
        if(pending!=null) pending.cancel();
        if(controlCall!=null) controlCall.cancel();
        http.dispatcher().executorService().shutdown();
        http.connectionPool().evictAll();
    }
}
