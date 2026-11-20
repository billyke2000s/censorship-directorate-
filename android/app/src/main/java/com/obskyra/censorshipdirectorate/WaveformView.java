package com.obskyra.censorshipdirectorate;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.View;

public final class WaveformView extends View {
    private final float[] samples = new float[55];
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private float peak = 0.025f;

    public WaveformView(Context context) { super(context); }

    public void addLevel(float amplitude) {
        System.arraycopy(samples,1,samples,0,samples.length-1);
        peak = Math.max(Math.max(0.012f, amplitude), peak * 0.982f);
        float relative = Math.min(1f, Math.max(0f, amplitude / peak));
        samples[samples.length-1] = (float)Math.pow(relative, 0.70);
        invalidate();
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float middle = getHeight()/2f;
        paint.setStrokeWidth(1.3f);
        paint.setColor(Color.rgb(92, 28, 39));
        canvas.drawLine(0, middle, getWidth(), middle, paint);
        paint.setStrokeWidth(Math.max(2f,getResources().getDisplayMetrics().density*2f));
        paint.setColor(Color.rgb(252,54,63));
        float step = getWidth()/(float)samples.length;
        for(int i=0;i<samples.length;i++) {
            float x=(i+0.5f)*step;
            float h=2+samples[i]*(middle-9);
            canvas.drawLine(x,middle-h,x,middle+h,paint);
        }
    }
}
