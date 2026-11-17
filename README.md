# Mouth Alarm for Windows

A local Windows demo inspired by [Raul Engineer's Short](https://www.youtube.com/shorts/dYAdNCzWI3o). It uses your webcam and microphone. Audio and video are processed locally without recording, transcription, or uploads.

- The outline follows the outer lip contour. It is green while the mouth is closed and turns red when the mouth aspect ratio reaches 0.30. The ratio is measured from the inner lips.
- The app beeps when a tracked hand overlaps the center or most of the mouth for roughly a third of a second. It keeps the last clear lip position while the hand obscures the face.
- The microphone uses WebRTC voice activity detection with a stricter speech threshold and a short confirmation window. Very quiet sounds, isolated clicks, and steady tones are less likely to trigger it. The alarm panel marks this cause **MIC: SPEECH DETECTED**. The censor tone plays locally through Windows audio. Nearby voices and recordings can trigger it, and quiet or very brief speech can be missed.
- The console plays a continuous 1 kHz TV-style tone while an alarm is active and lists the reasons beside the live view. It flags a missing face or multiple faces after one second and a sustained sideways head turn after two seconds.
- The app requests 1080p and displays the resolution the camera actually delivers. The preview preserves the original aspect ratio.
- Holding an open-mouth pose for three seconds starts a movement check. You can also press **L**. Follow the open and closed prompts, holding each pose briefly. If the sequence times out, the alarm panel shows **CHEATING? CHECK FAILED** and sounds the tone.
- If a tracked face stays nearly still for five seconds, the app prompts for live mouth movement. If that check times out, the alarm panel shows **CHEATING? STATIC FACE**.
- Press **R** to clear the result and rearm the automatic check. Press **Esc** to quit.

The movement check can flag a static fake mouth if its shape triggers the check or you start it manually. Camera angle, tracking loss, lighting, and slow responses can also cause a timeout. A missing face can mean someone stepped away, covered the lens, or moved into poor lighting. A head turn is estimated from facial landmarks. These camera checks do not establish intent or reliably identify all props, moving overlays, or prerecorded inputs.

## Quick start

Install [64-bit Python 3.14](https://www.python.org/downloads/windows/), extract the full project ZIP, then double-click **Start-MouthAlarm.cmd**. Keep it in the same folder as the other project files. The first run installs dependencies and downloads the two models. After that, double-click the same file to reopen the app.

## Manual setup

From the source folder in PowerShell with 64-bit Python 3.14:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -NoProfile -File .\setup-models.ps1
.\.venv\Scripts\python.exe main.py
```

If you already set up an earlier version, rerun the dependency install command to add the speech detector. If the wrong camera opens, add `--camera 1`. Use `--mic INDEX` to select an input listed by `python -m sounddevice`, or `--no-mic` for webcam-only mode. Run with `--check-models` to check the models without opening the webcam.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```
