# Mouth Alarm for Windows

A local Windows demo inspired by [Raul Engineer's Short](https://www.youtube.com/shorts/dYAdNCzWI3o). It uses your webcam and microphone. Audio and video are processed locally without recording, transcription, or uploads.

- A green outline marks closed lips. The outline turns red when the mouth aspect ratio reaches 0.30.
- The app beeps while a tracked hand covers most of the mouth. It requires roughly a third of a second of overlap.
- The microphone uses WebRTC voice activity detection to beep when it detects speech, including speech off camera. Nearby voices and recordings can also trigger it. Quiet speech and background noise can affect detection.
- The console sounds a 1 kHz TV-style tone and lists active reasons alongside the live view. It flags a missing face or multiple faces after one second and a sustained sideways head turn after two seconds.
- Holding an open-mouth pose for three seconds starts a movement check. You can also press **L**. Follow the open and closed prompts, holding each pose briefly. If the sequence times out, the alarm panel shows **CHEATING? CHECK FAILED** and sounds the tone.
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
