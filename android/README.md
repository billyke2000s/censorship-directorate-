# Censorship Directorate for Android (preview)

Native Android adaptation of the Windows joke surveillance app, using CameraX and Google's on-device ML Kit face detector. The camera preview is live; the demo portrait is never shown in the APK.

- Face outline and four expanded head-tracking corners.
- Mouth-open detection from upper/lower lip contours.
- Face missing, multiple faces, head turned away, camera covered, and still-face warnings.
- Local microphone sound-activity meter and looping alarm tone.
- Front/rear camera switch.
- Red/black responsive layout for portrait and landscape.

## Differences from Windows

This is an **early preview**, not full feature parity:
- ML Kit's lip contour geometry differs from MediaPipe, so the Android mouth-open threshold is calibrated separately (0.15, 0.10 clear).
- Android sound activity is **not** WebRTC speech detection; it may trigger on non-speech noises.
- Hand-over-mouth detection is not yet implemented.
- Android apps cannot expose a system-wide virtual microphone using ordinary app privileges; the Windows VB-CABLE mode is not included.
- The beep uses the device media speaker. Keep your volume sensible.
- Video/audio are processed locally. No microphone recording, upload or speech transcript.

## Building

Install Android SDK Platform 36 and JDK 17. From this folder run:

```sh
gradle :app:assembleDebug
```

The debug APK is in `app/build/outputs/apk/debug/app-debug.apk`. CI publishes an installable (debug-signed) preview APK as a GitHub Release asset. Since debug signing keys are not persistent, future preview builds may require uninstalling earlier versions first.

Production releases should use a stable Android signing key and undergo on-device testing.
