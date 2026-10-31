package org.facebot;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;

/** Speech-driven vector mouth. UI-thread only; input comes from the audio sample clock. */
final class MouthRenderer {
    // width, aperture, smile, roundness, upper teeth, tongue, lip bite, right lift
    private static final float[][] POSES = {
        {.31f,0f,.022f,0f,0f,0f,0f,.012f}, // resting, knowing half-smile
        {.27f,0f,.008f,0f,0f,0f,0f,.004f}, // M B P: actual seal
        {.28f,.108f,.009f,.25f,.72f,.25f,0f,.006f}, // A / open jaw
        {.35f,.047f,.019f,0f,1f,0f,0f,.009f}, // E / stretched corners
        {.18f,.100f,0f,1f,0f,0f,0f,.002f}, // O
        {.16f,.059f,0f,1f,0f,0f,0f,.002f}, // U / W
        {.28f,.027f,.010f,.10f,1f,0f,1f,.006f}, // F V: lower lip meets teeth
        {.28f,.053f,.010f,.15f,.75f,1f,0f,.005f}, // L / TH: raised tongue tip
        {.30f,.028f,.013f,0f,.90f,0f,0f,.007f} // S / consonant slot
    };
    private int MINT=Color.rgb(94,235,184), ICE=Color.rgb(206,255,238);
    void setColors(int mint, int ice) { MINT=mint; ICE=ice; }
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path outline=new Path(), detail=new Path();
    private final float[] pose=POSES[0].clone(), start=POSES[0].clone();
    private int current=0;
    private double changed=Double.NaN;

    void draw(Canvas canvas, String shape, double timeSeconds, boolean preview) {
        int next=index(shape);
        if (preview) {
            // Preview must not alter live interpolation state.
            render(canvas,POSES[next]);
            return;
        }
        if (!Double.isFinite(timeSeconds)) timeSeconds=0;
        if (Double.isNaN(changed) || timeSeconds<changed) changed=timeSeconds;
        update(timeSeconds);
        if(next!=current) {
            System.arraycopy(pose,0,start,0,pose.length);
            current=next;changed=timeSeconds;
        }
        render(canvas,pose);
    }

    private void update(double time) {
        // Finite transitions, not frame-rate-dependent exponential drift. Closures are faster.
        float u=(float)Math.max(0,Math.min(1,(time-changed)/(current<=1?.030:.045)));
        float blend=u*u*(3-2*u);
        for(int i=0;i<pose.length;i++) pose[i]=start[i]+(POSES[current][i]-start[i])*blend;
    }
    private static int index(String shape) {
        if(shape==null)return 0;
        switch(shape) {
            case "closed":return 1; case "open":return 2;case "wide":return 3;
            case "round":return 4;case "pucker":return 5;case "teeth":return 6;
            case "tongue":return 7;case "narrow":return 8;default:return 0;
        }
    }
    private void fill(int color,int alpha) {
        paint.setStyle(Paint.Style.FILL);paint.setColor(color);paint.setAlpha(alpha);
    }
    private void stroke(int color,float width,int alpha) {
        fill(color,alpha);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(width);
        paint.setStrokeJoin(Paint.Join.ROUND);paint.setStrokeCap(Paint.Cap.ROUND);
    }
    private void render(Canvas c,float[] p) {
        float w=p[0], a=p[1], smile=p[2], round=p[3], lift=p[7];
        float l=.5f-w*.5f,r=.5f+w*.5f, y=.574f, rightY=y-lift;
        float cornerY=y+a*.28f, rightCornerY=rightY+a*.28f;
        float midY=y-lift*.5f+smile*.75f;
        // Four cubic segments retain identical topology in every pose, including closure.
        // Rounded vowels move the handles toward vertical walls; smile corners taper.
        float edge=w*.10f*(1-round)*(1-Math.min(1,a/.070f));
        outline.reset();outline.moveTo(l,cornerY);
        outline.cubicTo(l+edge,y+smile*.45f-a*.12f,
            .5f-w*.18f,midY-a*.12f,.5f,midY-a*.12f);
        outline.cubicTo(.5f+w*.18f,midY-a*.12f,
            r-edge,rightY+smile*.45f-a*.12f,r,rightCornerY);
        outline.cubicTo(r-edge,rightY+smile*.45f+a*(.45f+.38f*round),
            .5f+w*.18f,midY+a*.94f,.5f,midY+a*.94f);
        outline.cubicTo(.5f-w*.18f,midY+a*.94f,
            l+edge,y+smile*.45f+a*(.45f+.38f*round),l,cornerY);
        outline.close();
        fill(Color.rgb(2,13,12),255);c.drawPath(outline,paint);
        int save=c.save();c.clipPath(outline);
        float visibility=Math.min(1,a/.018f);
        // Sculpted upper dental plate: small, following the arch, no grille or bright rectangle.
        float toothDepth=.012f*p[4];
        detail.reset();detail.moveTo(l+w*.10f,y-.025f);
        detail.lineTo(r-w*.10f,rightY-.025f);detail.lineTo(r-w*.10f,rightY+.007f);
        detail.cubicTo(r-w*.22f,rightY+smile+toothDepth,
            l+w*.22f,y+smile+toothDepth,l+w*.10f,y+.007f);detail.close();
        fill(ICE,(int)(255*visibility*Math.min(1,p[4]*2)));c.drawPath(detail,paint);
        // A shallow lower cushion for F/V, not a second disconnected oval.
        float bite=p[6];
        detail.reset();detail.moveTo(l,y+a+.025f);detail.lineTo(l,y+a*.85f);
        detail.cubicTo(l+w*.28f,y+a*.28f,r-w*.24f,rightY+a*.28f,r,rightY+a*.85f);
        detail.lineTo(r,rightY+a+.025f);detail.close();
        fill(Color.rgb(70,164,137),(int)(255*bite*visibility));c.drawPath(detail,paint);
        // Broad low tongue for vowels; a small lifted tip for lingual consonants.
        float tongue=p[5], base=y+a+smile*.5f;
        float tip=base-a*(.12f+.55f*tongue);
        detail.reset();detail.moveTo(.5f-w*.25f,base+.015f);
        detail.cubicTo(.5f-w*.23f,tip,.5f+w*.18f,tip-.005f,.5f+w*.22f,base+.015f);
        detail.close();fill(Color.rgb(66,137,117),(int)(210*tongue*visibility));c.drawPath(detail,paint);
        c.restoreToCount(save);
        // Thin outer ink, with an ice lower-lip catchlight rather than a neon ring.
        stroke(MINT,.0065f,255);c.drawPath(outline,paint);
        // Trace the actual lower contour: a detached decorative curve reads as a second lip.
        detail.reset();detail.moveTo(r,rightCornerY);
        detail.cubicTo(r-edge,rightY+smile*.45f+a*(.45f+.38f*round),
            .5f+w*.18f,midY+a*.94f,.5f,midY+a*.94f);
        detail.cubicTo(.5f-w*.18f,midY+a*.94f,
            l+edge,y+smile*.45f+a*(.45f+.38f*round),l,cornerY);
        stroke(ICE,.0025f,(int)(110*visibility*(1-round*.65f)));c.drawPath(detail,paint);
        // Closed mouth is drawn from exactly the same smile centerline, without a hollow slit.
        if(a<.003f) {
            detail.reset();detail.moveTo(l,cornerY);
            detail.cubicTo(l+edge,y+smile*.45f-a*.12f,
                .5f-w*.18f,midY-a*.12f,.5f,midY-a*.12f);
            detail.cubicTo(.5f+w*.18f,midY-a*.12f,
                r-edge,rightY+smile*.45f-a*.12f,r,rightCornerY);
            stroke(ICE,.008f,(int)(255*(1-a/.003f)));c.drawPath(detail,paint);
        }
        paint.setAlpha(255);
    }
}
