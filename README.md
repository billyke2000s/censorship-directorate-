# Mouth Alarm for Windows

A local Windows demo inspired by [Raul Engineer's Short](https://www.youtube.com/shorts/dYAdNCzWI3o). It processes webcam video and recognizes English words locally. It does not save or upload audio, video, or recognized words.

- The outline follows the outer lip contour. The **MOUTH OPEN** alarm starts when the inner-lip aspect ratio reaches 0.30 and clears below 0.22.
- The app beeps when a tracked hand overlaps the center or most of the mouth for roughly a third of a second. It keeps the last clear lip position while the hand obscures the face.
- The microphone uses offline Vosk English recognition. The panel shows **MIC: WORD DETECTED** when the recognizer returns a new word. Recognition can miss words or mistake other sounds for speech, and the tone plays locally through Windows audio.
- The console plays a continuous 1 kHz TV-style tone while an alarm is active and lists the reasons beside the live view. It flags a missing face or multiple faces after one second and a sustained sideways head turn after two seconds.
- The app tries common camera modes up to 4K, processes the full received frame, and shows the actual capture resolution. The preview scales to the window without stretching. To request another mode, run `Start-MouthAlarm.cmd --resolution WIDTHxHEIGHT` from a terminal.
- Holding an open-mouth pose for three seconds starts a movement check. You can also press **L**. Follow the open and closed prompts, holding each pose briefly. If the sequence times out, the alarm panel shows **CHEATING? CHECK FAILED** and sounds the tone.
- If a tracked face stays nearly still for five seconds, the app prompts for live mouth movement. If that check times out, the alarm panel shows **CHEATING? STATIC FACE**.
- Press **R** to clear the result and rearm the automatic check. Press **Esc** to quit.

The movement check can flag a static fake mouth if its shape triggers the check or you start it manually. Camera angle, tracking loss, lighting, and slow responses can also cause a timeout. A missing face can mean someone stepped away, covered the lens, or moved into poor lighting. A head turn is estimated from facial landmarks. These camera checks do not establish intent or reliably identify all props, moving overlays, or prerecorded inputs.

## Quick start

Install [64-bit Python 3.14](https://www.python.org/downloads/windows/), extract the full project ZIP, then double-click **Start-MouthAlarm.cmd**. Keep it in the same folder as the other project files. The first run installs dependencies and downloads the camera models and the English speech model. After that, double-click the same file to reopen the app.

## Manual setup

From the source folder in PowerShell with 64-bit Python 3.14:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -NoProfile -File .\setup-models.ps1
.\Start-MouthAlarm.cmd
```

If you already set up an earlier version, rerun the dependency install command to add the speech detector. If the wrong camera opens, add `--camera 1`. Use `--mic INDEX` to select an input listed by `python -m sounddevice`, or `--no-mic` for webcam-only mode. Run with `--check-models` to check the models without opening the webcam.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```
