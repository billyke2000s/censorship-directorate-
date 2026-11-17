# Mouth Alarm for Windows

A local webcam demo inspired by [Raul Engineer's Short](https://www.youtube.com/shorts/dYAdNCzWI3o). The app uses your webcam and Windows audio. It does not need Arduino hardware, record video, or send frames over the network.

- A green outline marks closed lips. The outline turns red when the mouth aspect ratio reaches 0.30.
- The app beeps while a tracked hand covers most of the mouth. It requires roughly a third of a second of overlap.
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

If the wrong camera opens, add `--camera 1`. Run with `--check-models` to verify that both Google MediaPipe models load without turning on the webcam.

## Build

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
.\.venv\Scripts\python.exe -m PyInstaller --onedir --name MouthAlarm --collect-all mediapipe main.py
Copy-Item setup-models.ps1,Start-MouthAlarm.cmd,README.md dist/MouthAlarm
```

Keep the executable alongside its `_internal` folder. Open `Start-MouthAlarm.cmd`. On first launch it downloads the two models from Google.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```
