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

## Camera / sound troubleshooting

1. Grant Camera and Microphone permissions when prompted (Android Settings → Apps → Censorship Directorate → Permissions).
2. Check Android's system-wide **Camera access** and **Microphone access** privacy switches.
3. If the camera area stays black, tap **Retry camera**. Try **Switch camera** if the front camera cannot be opened. The app will also fall back to a preview-only mode if the combined camera/face-analysis session never starts.
4. Tap **Test beep** to check audio without a working camera. The tone is sent to Android's **alarm** audio channel, so raise the phone's alarm volume if you cannot hear it.
5. If camera preview works but face tracking isn't available, the camera should still display video and its status panel should report the problem.

The APK is a debug-signed preview. Because signing keys are generated separately by GitHub Actions, you may need to **uninstall the previous preview before installing this update**. This clears that app's local data. Android cannot update a package signed with a different certificate.
