package org.facebot;
public final class ConnectionPolicyTest {
    private static void check(boolean ok) { if(!ok) throw new AssertionError(); }
    public static void main(String[] args) {
        for(String url:new String[]{"ws://192.168.1.2:8765/voice","ws://10.0.0.2:8765/voice","ws://172.16.0.2/voice","ws://172.31.255.254/voice"}) {
            check(ConnectionPolicy.allows(url,true)); check(!ConnectionPolicy.allows(url,false));
        }
        for(String url:new String[]{"ws://8.8.8.8/voice","ws://172.32.0.2/voice","ws://192.169.1.2/voice","ws://router.local/voice","ws://192.168.1.999/voice","ws://192.168.01.2/voice","ws://user:pass@10.0.0.2/voice","wss://example.com/voice?token=secret","https://example.com/voice","wss://example.com/other"}) check(!ConnectionPolicy.allows(url,true));
        check(ConnectionPolicy.allows("wss://example.com/voice",false));
        check(ConnectionPolicy.allows("ws://127.0.0.1:8765/voice",false));
        check(ConnectionPolicy.retryDelay(1)==1000); check(ConnectionPolicy.retryDelay(4)==5000); check(ConnectionPolicy.retryDelay(100)==5000);
        System.out.println("ConnectionPolicyTest passed: private opt-in, public rejection, retry cap");
    }
}
