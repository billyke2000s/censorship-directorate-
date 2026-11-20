package com.obskyra.censorshipdirectorate;

import android.Manifest;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.media.AudioManager;
import android.content.Context;
import android.media.Image;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
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
import androidx.camera.core.Camera;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.CameraState;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.Preview;
import androidx.camera.core.ImageProxy;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.graphics.Insets;

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
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final List<String> cameraAlarms = new ArrayList<>();
    private boolean cameraStreaming = false;
    private boolean previewOnly = false;
    private int cameraAttempt = 0;
    private long manualBeepUntil = 0L;
    private final Map<String, Long> warningSince = new HashMap<>();
    private ProcessCameraProvider cameraProvider;
    private FaceDetector faceDetector;
    private PreviewView preview;
    private FaceOverlay faceOverlay;
    private WaveformView waveform;
    private TextView alarmTitle, alarmList, mouthLabel, faceLabel, micLabel, cameraLabel, audioLabel;
    private boolean lastAlarmActive = false;
    private float micNoiseFloor = 0.0025f;
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
        tone = new AlarmTone(this);
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

    private GradientDrawable rounded(int fill, int stroke, int radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill); d.setCornerRadius(dp(radius)); d.setStroke(dp(1), stroke);
        return d;
    }

    private TextView stat(String label, boolean muted) {
        TextView t = text(label, muted ? 13 : 15, muted ? MUTED : TEXT, !muted);
        t.setPadding(dp(10), dp(3), dp(4), dp(3));
        t.setMinHeight(dp(29));
        return t;
    }

    private Button control(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(12);
        button.setAllCaps(false);
        button.setTextColor(TEXT);
        button.setMinHeight(dp(42));
        button.setPadding(dp(5), 0, dp(5), 0);
        button.setBackground(rounded(Color.rgb(80, 12, 25), Color.rgb(160, 37, 48), 7));
        return button;
    }

    private View divider() {
        View line = new View(this);
        line.setBackgroundColor(Color.rgb(101, 40, 51));
        return line;
    }

    private void makeLayout() {
        boolean landscape = getResources().getConfiguration().orientation ==
            Configuration.ORIENTATION_LANDSCAPE;
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() |
                                          WindowInsetsCompat.Type.displayCutout());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(10), 0, dp(10), 0);
        header.setBackground(rounded(Color.rgb(37, 5, 12), RED, 7));
        LinearLayout.LayoutParams h = new LinearLayout.LayoutParams(-1, dp(62));
        h.setMargins(dp(6), dp(5), dp(6), dp(5));
        TextView eye = text("◉", 34, TEXT, true);
        header.addView(eye, new LinearLayout.LayoutParams(dp(40), -1));
        LinearLayout titleCol = new LinearLayout(this);
        titleCol.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("CENSORSHIP DIRECTORATE", landscape ? 20 : 15, TEXT, true);
        title.setSingleLine();
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        titleCol.addView(title);
        titleCol.addView(text("SPEECH · EXPRESSION · COMPLIANCE", landscape ? 10 : 8, MUTED, false));
        header.addView(titleCol, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView live = text(landscape ? "● LIVE SURVEILLANCE" : "● LIVE", landscape ? 11 : 10, TEXT, true);
        live.setPadding(dp(7), dp(6), dp(7), dp(6));
        live.setBackground(rounded(Color.rgb(84, 7, 18), RED, 7));
        header.addView(live);
        root.addView(header, h);

        FrameLayout cameraBox = new FrameLayout(this);
        cameraBox.setBackground(rounded(Color.rgb(30, 5, 11), RED, 6));
        cameraBox.setPadding(dp(2), dp(2), dp(2), dp(2));
        preview = new PreviewView(this);
        preview.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        preview.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        preview.getPreviewStreamState().observe(this, state -> {
            if (state == PreviewView.StreamState.STREAMING) {
                cameraStreaming = true;
                if (cameraLabel != null)
                    cameraLabel.setText("Camera: " + (frontCamera ? "Front" : "Back") +
                        " • LIVE" + (previewOnly ? " (preview only)" : ""));
            }
        });
        cameraBox.addView(preview, new FrameLayout.LayoutParams(-1, -1));
        faceOverlay = new FaceOverlay(this);
        cameraBox.addView(faceOverlay, new FrameLayout.LayoutParams(-1, -1));
        TextView camTag = text("CAM 01  ●  LIVE", 12, TEXT, true);
        camTag.setPadding(dp(9), dp(5), dp(9), dp(5));
        camTag.setBackground(rounded(Color.argb(220, 18, 5, 12), RED, 5));
        FrameLayout.LayoutParams ct = new FrameLayout.LayoutParams(-2, -2,
            Gravity.TOP | Gravity.LEFT);
        ct.setMargins(dp(8), dp(8), 0, 0);
        cameraBox.addView(camTag, ct);

        LinearLayout side = new LinearLayout(this);
        side.setOrientation(LinearLayout.VERTICAL);
        side.setPadding(dp(9), dp(9), dp(9), dp(12));
        side.setBackground(rounded(Color.rgb(10, 7, 11), Color.rgb(125, 53, 62), 6));
        alarmTitle = text("UNDER OBSERVATION", landscape ? 20 : 17, TEXT, true);
        alarmTitle.setGravity(Gravity.CENTER);
        alarmTitle.setPadding(dp(6), dp(5), dp(6), dp(5));
        alarmTitle.setBackground(rounded(Color.rgb(38, 11, 19), Color.rgb(127, 41, 55), 8));
        side.addView(alarmTitle, new LinearLayout.LayoutParams(-1, dp(landscape ? 65 : 54)));
        alarmList = text("No active alarms", landscape ? 16 : 14, MUTED, true);
        alarmList.setGravity(Gravity.TOP | Gravity.LEFT);
        alarmList.setPadding(dp(11), dp(13), dp(7), dp(12));
        alarmList.setMinHeight(dp(69));
        side.addView(alarmList, new LinearLayout.LayoutParams(-1, -2));
        side.addView(divider(), new LinearLayout.LayoutParams(-1, dp(1)));
        mouthLabel = stat("Mouth:  -- / 0.12", false);
        faceLabel = stat("Face:  Waiting for camera", false);
        micLabel = stat("Mic:  Off", false);
        cameraLabel = stat("Camera:  --", true);
        audioLabel = stat("Audio:  Ready", true);
        for (TextView t : new TextView[]{mouthLabel, faceLabel, micLabel, cameraLabel, audioLabel})
            side.addView(t, new LinearLayout.LayoutParams(-1, -2));
        LinearLayout.LayoutParams midline = new LinearLayout.LayoutParams(-1, dp(1));
        midline.setMargins(0, dp(6), 0, dp(7));
        side.addView(divider(), midline);
        waveform = new WaveformView(this);
        waveform.setBackground(rounded(Color.rgb(26, 3, 10), Color.rgb(143, 24, 39), 6));
        side.addView(waveform, new LinearLayout.LayoutParams(-1, dp(landscape ? 90 : 72)));

        Button switchButton = control("Switch camera");
        switchButton.setOnClickListener(v -> { frontCamera = !frontCamera; startCamera(); });
        LinearLayout.LayoutParams sc = new LinearLayout.LayoutParams(-1, dp(44));
        sc.setMargins(0, dp(8), 0, dp(4));
        side.addView(switchButton, sc);
        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        Button retry = control("Retry camera");
        retry.setOnClickListener(v -> {
            if (!granted(Manifest.permission.CAMERA)) requestNeededPermissions();
            else startCamera();
        });
        LinearLayout.LayoutParams rc = new LinearLayout.LayoutParams(0, dp(43), 1f);
        rc.rightMargin = dp(4);
        controls.addView(retry, rc);
        Button test = control("Test beep");
        test.setOnClickListener(v -> {
            micActiveUntil = 0L;
            manualBeepUntil = SystemClock.elapsedRealtime() + 1800L;
            updateAlarmOutput();
            mainHandler.postDelayed(this::updateAlarmOutput, 1900L);
        });
        controls.addView(test, new LinearLayout.LayoutParams(0, dp(43), 1f));
        side.addView(controls, new LinearLayout.LayoutParams(-1, -2));

        ScrollView sideScroll = new ScrollView(this);
        sideScroll.setVerticalScrollBarEnabled(false);
        sideScroll.addView(side, new ScrollView.LayoutParams(-1, -2));
        if (landscape) {
            LinearLayout content = new LinearLayout(this);
            content.setOrientation(LinearLayout.HORIZONTAL);
            content.setPadding(dp(8), dp(4), dp(8), dp(8));
            LinearLayout.LayoutParams cam = new LinearLayout.LayoutParams(0, -1, 2.2f);
            cam.rightMargin = dp(8);
            content.addView(cameraBox, cam);
            content.addView(sideScroll, new LinearLayout.LayoutParams(0, -1, 1f));
            root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1f));
        } else {
            ScrollView screen = new ScrollView(this);
            screen.setVerticalScrollBarEnabled(false);
            LinearLayout content = new LinearLayout(this);
            content.setOrientation(LinearLayout.VERTICAL);
            content.setPadding(dp(7), dp(4), dp(7), dp(10));
            float density = getResources().getDisplayMetrics().density;
            int w = Math.round(getResources().getDisplayMetrics().widthPixels / density);
            int hh = Math.round(getResources().getDisplayMetrics().heightPixels / density);
            int cameraHeight = Math.max(250, Math.min(Math.round(w * 1.16f),
                                                     Math.round(hh * 0.51f)));
            content.addView(cameraBox, new LinearLayout.LayoutParams(-1, dp(cameraHeight)));
            LinearLayout.LayoutParams sideParams = new LinearLayout.LayoutParams(-1, -2);
            sideParams.topMargin = dp(8);
            content.addView(sideScroll, sideParams);
            screen.addView(content, new ScrollView.LayoutParams(-1, -2));
            root.addView(screen, new LinearLayout.LayoutParams(-1, 0, 1f));
        }
        setContentView(root);
        ViewCompat.requestApplyInsets(root);
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
        else {
            faceLabel.setText("Camera permission required");
            cameraLabel.setText("Camera denied • tap Retry camera");
        }
        if (granted(Manifest.permission.RECORD_AUDIO) && microphone == null) {
            microphone = new AudioMonitor(level -> runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                waveform.addLevel(level);
                if (!tone.isPlaying()) {
                    float threshold = Math.max(0.009f, micNoiseFloor * 2.7f);
                    if (level > threshold) micActiveUntil = SystemClock.elapsedRealtime() + 700L;
                    micNoiseFloor = micNoiseFloor * 0.985f
                        + Math.min(level, micNoiseFloor * 1.8f) * 0.015f;
                }
                micLabel.setText("Mic: " +
                    (SystemClock.elapsedRealtime() < micActiveUntil ? "Sound detected" : "Listening")
                    + String.format(java.util.Locale.US, " • %.3f", level));
                // Mic alarms must work even when camera/ML Kit cannot deliver frames.
                updateAlarmOutput();
            }));
            microphone.start();
        } else if (!granted(Manifest.permission.RECORD_AUDIO)) {
            micLabel.setText("Mic:  Permission denied");
        }
    }

    private void startCamera() {
        if (!granted(Manifest.permission.CAMERA)) {
            requestNeededPermissions();
            return;
        }
        cameraLabel.setText("Camera: opening…");
        faceLabel.setText("Face: waiting for video");
        cameraAlarms.clear();
        updateAlarmOutput();

        ListenableFuture<ProcessCameraProvider> pending = ProcessCameraProvider.getInstance(this);
        pending.addListener(() -> {
            if (isFinishing() || isDestroyed()) return;
            try {
                cameraProvider = pending.get();
                bindCamera(false);
            } catch (Exception e) {
                cameraLabel.setText("Camera failed: " + e.getClass().getSimpleName());
                faceLabel.setText("Tap Retry camera • check permissions");
                Log.e(TAG, "Camera provider startup failed", e);
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void bindCamera(boolean previewOnlyMode) {
        if (cameraProvider == null || isFinishing() || isDestroyed()) return;
        final int attempt = ++cameraAttempt;
        cameraStreaming = false;
        previewOnly = previewOnlyMode;
        cameraProvider.unbindAll();

        try {
            CameraSelector requested = new CameraSelector.Builder()
                .requireLensFacing(frontCamera
                    ? CameraSelector.LENS_FACING_FRONT
                    : CameraSelector.LENS_FACING_BACK).build();
            if (!cameraProvider.hasCamera(requested)) {
                frontCamera = !frontCamera;
                requested = new CameraSelector.Builder()
                    .requireLensFacing(frontCamera
                        ? CameraSelector.LENS_FACING_FRONT
                        : CameraSelector.LENS_FACING_BACK).build();
            }
            if (!cameraProvider.hasCamera(requested)) {
                cameraLabel.setText("No camera reported by Android");
                faceLabel.setText("Check camera access • tap Retry camera");
                return;
            }

            Preview cameraPreview = new Preview.Builder().build();
            cameraPreview.setSurfaceProvider(preview.getSurfaceProvider());
            Camera bound;
            if (previewOnlyMode) {
                bound = cameraProvider.bindToLifecycle(this, requested, cameraPreview);
            } else {
                ImageAnalysis frames = new ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build();
                frames.setAnalyzer(analysis, this::analyze);
                try {
                    bound = cameraProvider.bindToLifecycle(this, requested, cameraPreview, frames);
                } catch (Exception combinedFailure) {
                    // Some devices cannot provide preview + analysis at once.
                    Log.w(TAG, "Combined preview/analysis failed; retrying preview alone",
                          combinedFailure);
                    bindCamera(true);
                    return;
                }
            }
            bound.getCameraInfo().getCameraState().observe(this, state -> {
                if (attempt != cameraAttempt) return;
                if (state.getError() != null) {
                    cameraLabel.setText("Camera error " + state.getError().getCode()
                        + " • tap Retry camera");
                    Log.e(TAG, "CameraX state error " + state.getError().getCode());
                }
            });
            cameraLabel.setText("Camera: " + (frontCamera ? "Front" : "Back")
                + " • opening" + (previewOnlyMode ? " (preview only)" : ""));
            mainHandler.postDelayed(() -> {
                if (attempt != cameraAttempt || cameraStreaming || isFinishing()
                    || isDestroyed()) return;
                if (!previewOnlyMode) {
                    Log.w(TAG, "Preview did not stream; trying preview-only fallback");
                    bindCamera(true);
                } else {
                    cameraLabel.setText("No camera preview • tap Retry camera");
                    faceLabel.setText("Check Android camera privacy switch and permissions");
                }
            }, 6000L);
        } catch (Exception e) {
            cameraLabel.setText("Camera failed: " + e.getClass().getSimpleName());
            faceLabel.setText("Tap Retry camera • check permissions");
            Log.e(TAG, "Camera binding failed", e);
        }
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
        try {
            faceDetector.process(input)
                .addOnSuccessListener(faces -> {
                    if (!isFinishing() && !isDestroyed()) {
                        frameWidth = rotatedW;
                        frameHeight = rotatedH;
                        evaluate(faces, luminance);
                        faceOverlay.setFaces(faces, rotatedW, rotatedH, frontCamera);
                    }
                })
                .addOnFailureListener(e -> {
                    Log.w(TAG, "Face detection failed; preview should remain available", e);
                    faceLabel.setText("Face detection unavailable");
                })
                .addOnCompleteListener(t -> imageProxy.close());
        } catch (RuntimeException e) {
            imageProxy.close();
            Log.e(TAG, "Face analysis failed", e);
        }
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
        else mouthOpen = ratio > (mouthOpen ? 0.075f : 0.12f);
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

        cameraAlarms.clear();
        cameraAlarms.addAll(alarms);
        updateAlarmOutput();
        mouthLabel.setText("Mouth:  " + (ratio < 0 ? "--" :
                            String.format(java.util.Locale.US, "%.2f", ratio)) +
                            "  /  0.12");
        faceLabel.setText("Face:  " + (primary == null ? "Not visible" :
                          faces.size() == 1 ? "Tracking" : faces.size()+" detected"));
        if (cameraStreaming) cameraLabel.setText("Camera: " +
            (frontCamera ? "Front" : "Back") + " • " +
            frameWidth + " × " + frameHeight + (previewOnly ? " (preview only)" : ""));
    }

    private void updateAlarmOutput() {
        if (isFinishing() || isDestroyed() || alarmList == null || tone == null) return;
        long now = SystemClock.elapsedRealtime();
        List<String> alarms = new ArrayList<>(cameraAlarms);
        if (now < micActiveUntil && now >= manualBeepUntil)
            alarms.add("MIC: SOUND DETECTED");
        if (now < manualBeepUntil) alarms.add("TEST BEEP");

        boolean active = !alarms.isEmpty();
        alarmTitle.setText(active ? "⚠ ALARM ACTIVE" : "UNDER OBSERVATION");
        if (active != lastAlarmActive) {
            alarmTitle.setBackground(rounded(
                active ? Color.rgb(97, 10, 22) : Color.rgb(38, 11, 19),
                active ? RED : Color.rgb(127, 41, 55), 8));
            lastAlarmActive = active;
        }
        alarmTitle.setTextColor(TEXT);
        if (!active) {
            alarmList.setText("No active alarms");
            alarmList.setTextColor(MUTED);
        } else {
            StringBuilder list = new StringBuilder();
            for (String reason : alarms) list.append("■  ").append(reason).append('\n');
            alarmList.setText(list.toString().trim());
            alarmList.setTextColor(RED);
        }
        boolean started = tone.setPlaying(active);
        AudioManager audio = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        int volume = audio == null ? -1 : audio.getStreamVolume(AudioManager.STREAM_MUSIC);
        if (volume == 0) {
            audioLabel.setText("Audio: MEDIA VOLUME 0 — raise volume");
            audioLabel.setTextColor(RED);
        } else if (!started) {
            audioLabel.setText("Audio error: " + tone.getLastError());
            audioLabel.setTextColor(RED);
        } else {
            audioLabel.setText(active ? "Audio: BEEP PLAYING • media " + volume
                                      : "Audio: Ready • media " + volume);
            audioLabel.setTextColor(MUTED);
        }
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
        cameraAttempt++;
        mainHandler.removeCallbacksAndMessages(null);
        if (cameraProvider != null) cameraProvider.unbindAll();
        if (microphone != null) microphone.close();
        if (tone != null) tone.close();
        if (faceDetector != null) faceDetector.close();
        analysis.shutdownNow();
        super.onDestroy();
    }
}
