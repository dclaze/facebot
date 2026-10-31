package org.facebot;

import java.net.URI;

/** Pure policy: never resolve hostnames to decide whether cleartext is private. */
final class ConnectionPolicy {
    static boolean allows(String endpoint, boolean allowPrivateLan) {
        try {
            URI uri=new URI(endpoint);
            String scheme=uri.getScheme(), host=uri.getHost();
            if(host==null || uri.getUserInfo()!=null || uri.getFragment()!=null || uri.getRawQuery()!=null) return false;
            if(!"ws".equals(scheme) && !"wss".equals(scheme)) return false;
            if(!"/voice".equals(uri.getPath())) return false;
            if("wss".equals(scheme)) return true;
            if(host.equals("127.0.0.1") || host.equals("localhost")) return true;
            if(!allowPrivateLan || !host.matches("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+")) return false;
            String[] parts=host.split("\\."); int[] octets=new int[4];
            for(int i=0;i<4;i++) {
                octets[i]=Integer.parseInt(parts[i]);
                if(octets[i]>255 || !Integer.toString(octets[i]).equals(parts[i])) return false;
            }
            return octets[0]==10 || (octets[0]==172 && octets[1]>=16 && octets[1]<=31) || (octets[0]==192 && octets[1]==168);
        } catch(Exception ignored) { return false; }
    }
    static long retryDelay(int failures) {
        return Math.min(15000L, 1000L << Math.min(4,Math.max(0,failures-1)));
    }
}
