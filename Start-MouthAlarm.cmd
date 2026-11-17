@echo off
setlocal
cd /d "%~dp0"
if not exist "models\face_landmarker.task" goto setup
if not exist "models\hand_landmarker.task" goto setup
goto run

:setup
echo Downloading the face and hand models from Google MediaPipe...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-models.ps1"
if errorlevel 1 goto failed

:run
"%~dp0MouthAlarm.exe" %*
if errorlevel 1 goto failed
exit /b 0

:failed
pause
exit /b 1
