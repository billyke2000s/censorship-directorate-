package com.obskyra.censorshipdirectorate;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PointF;
import android.graphics.RectF;
import android.view.View;
import com.google.mlkit.vision.face.Face;
import com.google.mlkit.vision.face.FaceContour;
import java.util.ArrayList;
import java.util.List;

/** Real ML Kit tracking coordinates over CameraX's fill-centre preview. */
public class FaceOverlay extends View {
    private List<Face> faces = new ArrayList<>();
    private int imageWidth = 1, imageHeight = 1;
    private boolean mirror = false;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

    public FaceOverlay(Context context) { super(context); setLayerType(View.LAYER_TYPE_SOFTWARE, null); }

    public void setFaces(List<Face> faces, int width, int height, boolean mirrored) {
        this.faces = new ArrayList<>(faces);
        imageWidth = Math.max(1, width);
        imageHeight = Math.max(1, height);
        mirror = mirrored;
        invalidate();
    }

    private float sx(float x) {
        float s = Math.max(getWidth()/(float)imageWidth, getHeight()/(float)imageHeight);
        float xValue = mirror ? imageWidth-x : x;
        return (getWidth() - imageWidth*s)/2f + xValue*s;
    }
    private float sy(float y) {
        float s = Math.max(getWidth()/(float)imageWidth, getHeight()/(float)imageHeight);
        return (getHeight()-imageHeight*s)/2f + y*s;
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        // Keep the camera preview clear; do not draw dark scanlines over faces.

        paint.setColor(Color.rgb(255, 47, 53));
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(3.5f*getResources().getDisplayMetrics().density);
        paint.setShadowLayer(6f, 0f, 0f, Color.RED);
        for (Face face : faces) {
            android.graphics.Rect bounds = face.getBoundingBox();
            // Expand beyond landmarks: corners should surround the ENTIRE head.
            float marginX = bounds.width()*0.17f;
            float top = bounds.top - bounds.height()*0.20f;
            float bottom = bounds.bottom + bounds.height()*0.08f;
            float left = sx(bounds.left-marginX), right = sx(bounds.right+marginX);
            if (left > right) { float temp=left; left=right; right=temp; }
            float yTop = sy(top), yBottom=sy(bottom);
            float length = Math.min(right-left, yBottom-yTop)*0.18f;
            float[][] coords={{left,yTop,1,1},{right,yTop,-1,1},
                              {left,yBottom,1,-1},{right,yBottom,-1,-1}};
            for (float[] c : coords) {
                Path corner = new Path();
                corner.moveTo(c[0]+c[2]*length,c[1]);
                corner.lineTo(c[0],c[1]);
                corner.lineTo(c[0],c[1]+c[3]*length);
                canvas.drawPath(corner,paint);
            }
            // Use actual mouth contours, not a fixed oval or unrelated shape.
            drawContour(canvas,face.getContour(FaceContour.UPPER_LIP_TOP));
            drawContour(canvas,face.getContour(FaceContour.LOWER_LIP_BOTTOM));
        }
        paint.clearShadowLayer();
        paint.setStyle(Paint.Style.FILL);
    }

    private void drawContour(Canvas canvas, FaceContour contour) {
        if (contour == null || contour.getPoints().isEmpty()) return;
        Path path = new Path();
        List<PointF> points = contour.getPoints();
        path.moveTo(sx(points.get(0).x),sy(points.get(0).y));
        for (int i=1;i<points.size();i++) {
            path.lineTo(sx(points.get(i).x),sy(points.get(i).y));
        }
        canvas.drawPath(path,paint);
    }
}
