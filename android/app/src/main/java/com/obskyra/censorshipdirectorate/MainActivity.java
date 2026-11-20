package com.obskyra.censorshipdirectorate;

import android.Manifest;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Color;
import android.media.Image;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.Preview;
import androidx.camera.core.ImageProxy;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.face.Face;
import com.google.mlkit.vision.face.FaceContour;
import com.google.mlkit.vision.face.FaceDetection;
import com.google.mlkit.vision.face.FaceDetector;
import com.google.mlkit.vision.face.FaceDetectorOptions;

import android.graphics.PointF;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends ComponentActivity {
    private static final String TAG = "CensorshipDirectorate";
    private static final int REQUEST_PERMISSIONS = 40;
    private static final int RED = Color.rgb(255, 47, 53);
    private static final int BG = Color.rgb(12, 8, 12);
    private static final int PANEL = Color.rgb(24, 16, 23);
    private static final int TEXT = Color.rgb(239, 232, 238);
    private static final int MUTED = Color.rgb(190, 173, 187);

    private final ExecutorService analysis = Executors.newSingleThreadExecutor();
    private final Map<String, Long> warningSince = new HashMap<>();
    private ProcessCameraProvider cameraProvider;
    private FaceDetector faceDetector;
    private PreviewView preview;
    private FaceOverlay faceOverlay;
    private WaveformView waveform;
    private TextView alarmTitle, alarmList, mouthLabel, faceLabel, micLabel, cameraLabel;
    private AlarmTone tone;
    private AudioMonitor microphone;
    private boolean frontCamera = true;
    private boolean mouthOpen = false;
    private long stillSince = 0L;
    private float lastFaceX = Float.NaN, lastFaceY = Float.NaN;
    private long micActiveUntil = 0L;
    private int frameWidth = 0, frameHeight = 0;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        tone = new AlarmTone();
        faceDetector = FaceDetection.getClient(
            new FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
                .setContourMode(FaceDetectorOptions.CONTOUR_MODE_ALL)
                .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
                .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
                .setMinFaceSize(0.12f)
                .build()
        );
        makeLayout();
        requestNeededPermissions();
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextColor(color);
        v.setTextSize(size);
        v.setGravity(Gravity.CENTER_VERTICAL);
        if (bold) v.setTypeface(null, android.graphics.Typeface.BOLD);
        return v;
    }

    private void makeLayout() {
        boolean landscape = getResources().getConfiguration().orientation ==
            Configuration.ORIENTATION_LANDSCAPE;
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(14), 0, dp(12), 0);
        header.setBackgroundColor(Color.rgb(35, 10, 16));
        TextView brand = text("◉  CENSORSHIP DIRECTORATE", landscape ? 22 : 15, TEXT, true);
        header.addView(brand, new LinearLayout.LayoutParams(0, dp(62), 1f));
        TextView live = text("● LIVE", 12, RED, true);
        header.addView(live);
        root.addView(header);

        LinearLayout content = new LinearLayout(this);
        content.setPadding(dp(8), dp(8), dp(8), dp(8));
        content.setOrientation(landscape ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);

        FrameLayout cameraBox = new FrameLayout(this);
        cameraBox.setBackgroundColor(Color.BLACK);
        preview = new PreviewView(this);
        preview.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        cameraBox.addView(preview, new FrameLayout.LayoutParams(-1, -1));
        faceOverlay = new FaceOverlay(this);
        cameraBox.addView(faceOverlay, new FrameLayout.LayoutParams(-1, -1));
        TextView camTag = text("CAM 01  ●  LIVE", 12, RED, true);
        camTag.setPadding(dp(10), dp(4), dp(10), dp(4));
        camTag.setBackgroundColor(Color.argb(200, 12, 5, 9));
        FrameLayout.LayoutParams camTagLp = new FrameLayout.LayoutParams(-2, -2,
                                                                       Gravity.TOP | Gravity.LEFT);
        camTagLp.setMargins(dp(8), dp(8), 0, 0);
        cameraBox.addView(camTag, camTagLp);

        LinearLayout side = new LinearLayout(this);
        side.setOrientation(LinearLayout.VERTICAL);
        side.setPadding(dp(12), dp(12), dp(12), dp(12));
        side.setBackgroundColor(PANEL);
        alarmTitle = text("UNDER OBSERVATION", landscape ? 22 : 19, TEXT, true);
        alarmTitle.setPadding(dp(10), dp(7), dp(10), dp(7));
        alarmTitle.setBackgroundColor(Color.rgb(76, 22, 29));
        side.addView(alarmTitle, new LinearLayout.LayoutParams(-1, dp(52)));

        ScrollView alarmsScroll = new ScrollView(this);
        alarmList = text("No active alarms", landscape ? 16 : 14, MUTED, false);
        alarmList.setGravity(Gravity.TOP);
        alarmList.setPadding(dp(8), dp(12), dp(8), dp(8));
        alarmsScroll.addView(alarmList);
        side.addView(alarmsScroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        View divider = new View(this);
        divider.setBackgroundColor(Color.rgb(93, 38, 48));
        side.addView(divider, new LinearLayout.LayoutParams(-1, dp(1)));

        mouthLabel = text("Mouth:  --", 15, TEXT, false);
        faceLabel = text("Face:  Waiting for camera", 15, TEXT, false);
        micLabel = text("Mic:  Off", 15, TEXT, false);
        cameraLabel = text("Camera:  --", 14, MUTED, false);
        for (TextView t : new TextView[]{mouthLabel, faceLabel, micLabel, cameraLabel}) {
            t.setPadding(dp(5), dp(6), 0, dp(3));
            side.addView(t);
        }
        waveform = new WaveformView(this);
        side.addView(waveform, new LinearLayout.LayoutParams(-1, dp(76)));
        Button switchCamera = new Button(this);
        switchCamera.setText("Switch camera");
        switchCamera.setTextColor(TEXT);
        switchCamera.setBackgroundTintList(android.content.res.ColorStateList.valueOf(
            Color.rgb(108, 21, 35)));
        switchCamera.setOnClickListener(v -> {
            frontCamera = !frontCamera;
            startCamera();
        });
        side.addView(switchCamera, new LinearLayout.LayoutParams(-1, dp(47)));

        if (landscape) {
            LinearLayout.LayoutParams camParams = new LinearLayout.LayoutParams(
                0, -1, 2.2f);
            camParams.rightMargin = dp(8);
            content.addView(cameraBox, camParams);
            content.addView(side, new LinearLayout.LayoutParams(0, -1, 1f));
        } else {
            LinearLayout.LayoutParams camParams = new LinearLayout.LayoutParams(
                -1, 0, 1.2f);
            camParams.bottomMargin = dp(8);
            content.addView(cameraBox, camParams);
            content.addView(side, new LinearLayout.LayoutParams(-1, 0, 1f));
        }
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);
    }

    private boolean granted(String permission) {
        return checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestNeededPermissions() {
        ArrayList<String> needed = new ArrayList<>();
        if (!granted(Manifest.permission.CAMERA)) needed.add(Manifest.permission.CAMERA);
        if (!granted(Manifest.permission.RECORD_AUDIO)) needed.add(Manifest.permission.RECORD_AUDIO);
        if (needed.isEmpty()) startServices();
        else requestPermissions(needed.toArray(new String[0]), REQUEST_PERMISSIONS);
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] perms,
                                                      int[] results) {
        super.onRequestPermissionsResult(requestCode, perms, results);
        if (requestCode == REQUEST_PERMISSIONS) startServices();
    }

    private void startServices() {
        if (granted(Manifest.permission.CAMERA)) startCamera();
        else faceLabel.setText("Camera permission required");
        if (granted(Manifest.permission.RECORD_AUDIO) && microphone == null) {
            microphone = new AudioMonitor(level -> runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                waveform.addLevel(level);
                if (!tone.isPlaying() && level > 0.04f) {
                    micActiveUntil = SystemClock.elapsedRealtime() + 300L;
                }
                micLabel.setText("Mic:  " +
                    (SystemClock.elapsedRealtime() < micActiveUntil ? "Sound detected" : "Listening"));
            }));
            microphone.start();
        } else if (!granted(Manifest.permission.RECORD_AUDIO)) {
            micLabel.setText("Mic:  Permission denied");
        }
    }

    private void startCamera() {
        if (!granted(Manifest.permission.CAMERA)) return;
        ListenableFuture<ProcessCameraProvider> pending = ProcessCameraProvider.getInstance(this);
        pending.addListener(() -> {
            if (isFinishing() || isDestroyed()) return;
            try {
                cameraProvider = pending.get();
                cameraProvider.unbindAll();
                int requested = frontCamera ? CameraSelector.LENS_FACING_FRONT
                                            : CameraSelector.LENS_FACING_BACK;
                CameraSelector selector = new CameraSelector.Builder()
                    .requireLensFacing(requested).build();
                if (!cameraProvider.hasCamera(selector)) {
                    frontCamera = !frontCamera;
                    selector = new CameraSelector.Builder()
                        .requireLensFacing(frontCamera ? CameraSelector.LENS_FACING_FRONT
                                                       : CameraSelector.LENS_FACING_BACK).build();
                }
                Preview cameraPreview = new Preview.Builder().build();
                cameraPreview.setSurfaceProvider(preview.getSurfaceProvider());
                ImageAnalysis frames = new ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build();
                frames.setAnalyzer(analysis, this::analyze);
                cameraProvider.bindToLifecycle(this, selector, cameraPreview, frames);
                cameraLabel.setText("Camera:  " + (frontCamera ? "Front" : "Back"));
            } catch (Exception e) {
                faceLabel.setText("Camera error: " + e.getMessage());
                Log.e(TAG, "Camera failed", e);
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void analyze(ImageProxy imageProxy) {
        Image image = imageProxy.getImage();
        if (image == null) {
            imageProxy.close();
            return;
        }
        int rotation = imageProxy.getImageInfo().getRotationDegrees();
        int w = imageProxy.getWidth(), h = imageProxy.getHeight();
        final int rotatedW = rotation == 90 || rotation == 270 ? h : w;
        final int rotatedH = rotation == 90 || rotation == 270 ? w : h;
        final float luminance = sampleLuma(imageProxy);
        final InputImage input = InputImage.fromMediaImage(image, rotation);
        faceDetector.process(input)
            .addOnSuccessListener(faces -> {
                if (!isFinishing() && !isDestroyed()) {
                    frameWidth = rotatedW;
                    frameHeight = rotatedH;
                    evaluate(faces, luminance);
                    faceOverlay.setFaces(faces, rotatedW, rotatedH, frontCamera);
                }
            })
            .addOnFailureListener(e -> Log.w(TAG, "Face detection failed", e))
            .addOnCompleteListener(t -> imageProxy.close());
    }

    private float sampleLuma(ImageProxy proxy) {
        ByteBuffer bytes = proxy.getPlanes()[0].getBuffer().duplicate();
        int count = 0;
        long total = 0;
        int step = Math.max(1, bytes.remaining() / 1200);
        for (int i = 0; i < bytes.limit(); i += step) {
            total += bytes.get(i) & 255;
            count++;
        }
        return count == 0 ? 127f : total / (float)count;
    }

    private boolean delayed(String name, boolean condition, long millis, long now) {
        if (!condition) {
            warningSince.remove(name);
            return false;
        }
        if (!warningSince.containsKey(name)) warningSince.put(name, now);
        return now - warningSince.get(name) >= millis;
    }

    private void evaluate(List<Face> faces, float luminance) {
        long now = SystemClock.elapsedRealtime();
        Face primary = faces.isEmpty() ? null : faces.get(0);
        List<String> alarms = new ArrayList<>();
        boolean coveredCamera = faces.isEmpty() && luminance < 24;
        if (delayed("CAMERA COVERED", coveredCamera, 600, now))
            alarms.add("CAMERA COVERED");
        if (delayed("FACE NOT VISIBLE", primary == null && !coveredCamera, 1000, now))
            alarms.add("FACE NOT VISIBLE");
        if (delayed("MULTIPLE FACES", faces.size() > 1, 1000, now))
            alarms.add("MULTIPLE FACES");

        float ratio = primary == null ? -1f : mouthRatio(primary);
        if (ratio < 0) mouthOpen = false;
        else mouthOpen = ratio > (mouthOpen ? 0.10f : 0.15f);
        if (mouthOpen) alarms.add("MOUTH OPEN");
        if (delayed("HEAD TURNED AWAY",
                    primary != null && Math.abs(primary.getHeadEulerAngleY()) > 25f,
                    650, now)) alarms.add("HEAD TURNED AWAY");
        if (primary != null) {
            android.graphics.Rect box = primary.getBoundingBox();
            float centerX = box.exactCenterX(), centerY = box.exactCenterY();
            if (Float.isNaN(lastFaceX) || Math.abs(centerX-lastFaceX) > 3.0f ||
                Math.abs(centerY-lastFaceY) > 3.0f) {
                lastFaceX = centerX;
                lastFaceY = centerY;
                stillSince = now;
            } else if (now-stillSince > 5000) {
                alarms.add("FACE IMAGE STILL");
            }
        } else {
            stillSince = 0;
            lastFaceX = lastFaceY = Float.NaN;
        }

        // Detect acoustic activity, not speech transcripts or words.
        if (now < micActiveUntil && !tone.isPlaying()) alarms.add("MIC: SOUND DETECTED");

        alarmTitle.setText(alarms.isEmpty() ? "UNDER OBSERVATION" : "⚠ ALARM ACTIVE");
        alarmTitle.setBackgroundColor(alarms.isEmpty() ?
            Color.rgb(76, 22, 29) : RED);
        alarmTitle.setTextColor(alarms.isEmpty() ? TEXT : Color.BLACK);
        if (alarms.isEmpty()) alarmList.setText("No active alarms");
        else {
            StringBuilder list = new StringBuilder();
            for (String reason : alarms) list.append("■  ").append(reason).append('\n');
            alarmList.setText(list.toString().trim());
        }
        alarmList.setTextColor(alarms.isEmpty() ? MUTED : RED);
        mouthLabel.setText("Mouth:  " + (ratio < 0 ? "--" :
                            String.format(java.util.Locale.US, "%.2f", ratio)) +
                            "  /  0.15");
        faceLabel.setText("Face:  " + (primary == null ? "Not visible" :
                          faces.size() == 1 ? "Tracking" : faces.size()+" detected"));
        cameraLabel.setText("Camera:  " + (frontCamera ? "Front" : "Back") + " • " +
                            frameWidth + " × " + frameHeight);
        // Don't play at full volume and don't create a microphone feedback loop.
        tone.setPlaying(!alarms.isEmpty());
    }

    private float mouthRatio(Face face) {
        FaceContour upper = face.getContour(FaceContour.UPPER_LIP_BOTTOM);
        FaceContour lower = face.getContour(FaceContour.LOWER_LIP_TOP);
        FaceContour outer = face.getContour(FaceContour.UPPER_LIP_TOP);
        if (upper == null || lower == null || outer == null ||
            upper.getPoints().isEmpty() || lower.getPoints().isEmpty() ||
            outer.getPoints().isEmpty()) return -1f;
        float minX = Float.MAX_VALUE, maxX = -Float.MAX_VALUE;
        for (PointF point : outer.getPoints()) {
            minX = Math.min(minX, point.x);
            maxX = Math.max(maxX, point.x);
        }
        float centerX = (minX + maxX) / 2f;
        float upperY = nearCenterY(upper.getPoints(), centerX, maxX - minX);
        float lowerY = nearCenterY(lower.getPoints(), centerX, maxX - minX);
        return Math.max(0f, lowerY - upperY) / Math.max(1f, maxX-minX);
    }

    private float nearCenterY(List<PointF> points, float center, float width) {
        float y = 0; int count = 0;
        for (PointF p : points) {
            if (Math.abs(p.x-center) < width * 0.18f) { y += p.y; count++; }
        }
        if (count > 0) return y/count;
        return points.get(points.size()/2).y;
    }

    @Override protected void onDestroy() {
        if (cameraProvider != null) cameraProvider.unbindAll();
        if (microphone != null) microphone.close();
        if (tone != null) tone.close();
        if (faceDetector != null) faceDetector.close();
        analysis.shutdownNow();
        super.onDestroy();
    }
}
