# Mouth Alarm for Windows

A local Windows demo inspired by [Raul Engineer's Short](https://www.youtube.com/shorts/dYAdNCzWI3o). It uses your webcam and microphone. Audio and video are processed locally without recording, transcription, or uploads.

- A green outline marks closed lips. The outline turns red when the mouth aspect ratio reaches 0.30.
- The app beeps while a tracked hand covers most of the mouth. It requires roughly a third of a second of overlap.
- The microphone uses WebRTC voice activity detection to beep when it detects speech, including speech off camera. Nearby voices and recordings can also trigger it. Quiet speech and background noise can affect detection.
- Holding an open-mouth pose for three seconds starts a movement check. You can also press **L**. Follow the open and closed prompts, holding each pose briefly. If the sequence times out, the display says **CHEATING? | Mouth movement not verified**.
- Press **R** to clear the result and rearm the automatic check. Press **Esc** to quit.

The movement check can flag a static fake mouth if its shape triggers the check or you start it manually. Camera angle, tracking loss, lighting, and slow responses can also cause a timeout. A single webcam cannot establish intent or reliably identify all props, moving overlays, or prerecorded inputs. The covered-mouth beep specifically uses visible hand overlap.

## Run from source

From the source folder in PowerShell with 64-bit Python 3.14:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -NoProfile -File .\setup-models.ps1
.\.venv\Scripts\python.exe main.py
```

If you already set up an earlier version, rerun the dependency install command to add the speech detector. If the wrong camera opens, add `--camera 1`. Use `--mic INDEX` to select an input listed by `python -m sounddevice`, or `--no-mic` for webcam-only mode. Run with `--check-models` to check the models without opening the webcam.

After setup you can double-click `Start-MouthAlarm.cmd` to start it.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```
