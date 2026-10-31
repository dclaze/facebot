package org.facebot;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;

/** Giant two-line captions occupy their own bottom band, below the mouth. */
final class CaptionRenderer {
    private final TextPaint paint=new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint background=new Paint();
    private String previous="";
    private float oldWidth,oldHeight,oldInset;
    private StaticLayout layout;
    void draw(Canvas canvas,String text,float width,float height,float bottomInset) {
        if(text.isEmpty()) return;
        float side=width*.04f, top=height*.74f;
        float bottom=height-Math.max(height*.025f,bottomInset+height*.008f);
        int availableWidth=Math.max(1,(int)(width-2*side));
        float availableHeight=Math.max(1,bottom-top);
        if(!text.equals(previous)||width!=oldWidth||height!=oldHeight||bottomInset!=oldInset) {
            previous=text;oldWidth=width;oldHeight=height;oldInset=bottomInset;
            paint.setColor(Color.WHITE);
            paint.setTypeface(Typeface.create("sans-serif",Typeface.BOLD));
            float size=Math.max(1,Math.min(width*.08f,availableHeight*.40f));
            do {
                paint.setTextSize(size);
                layout=StaticLayout.Builder.obtain(text,0,text.length(),paint,availableWidth)
                    .setAlignment(Layout.Alignment.ALIGN_CENTER).setIncludePad(false)
                    .setBreakStrategy(Layout.BREAK_STRATEGY_SIMPLE)
                    .setHyphenationFrequency(Layout.HYPHENATION_FREQUENCY_NONE).build();
                if(layout.getLineCount()<=2 && layout.getHeight()<=availableHeight) break;
                size*=.9f;
            } while(size>=1);
        }
        background.setColor(Color.BLACK);
        canvas.drawRect(0,top,width,height,background);
        canvas.save();canvas.translate(side,bottom-layout.getHeight());layout.draw(canvas);canvas.restore();
    }
}
