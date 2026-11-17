@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto failed
if not exist "requirements.txt" (
    echo Extract the entire project ZIP before opening this launcher.
    goto failed
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment...
    py -3.14 -m venv .venv
    if errorlevel 1 (
        echo Install 64-bit Python 3.14 from python.org, then reopen this launcher.
        goto failed
    )
)
fc /b "requirements.txt" ".venv\mouth-alarm-requirements.txt" >nul 2>&1
if errorlevel 1 (
    echo Installing the app dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
    copy /y "requirements.txt" ".venv\mouth-alarm-requirements.txt" >nul
    if errorlevel 1 goto failed
)
if not exist "models\" mkdir "models"
if not exist "models\" goto failed
call :model face_landmarker
if errorlevel 1 goto failed
call :model hand_landmarker
if errorlevel 1 goto failed
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 goto failed
exit /b 0

:model
if exist "models\%~1.task" exit /b 0
echo Downloading %~1 from Google MediaPipe...
curl.exe --fail --location --retry 2 --output "models\%~1.download" "https://storage.googleapis.com/mediapipe-models/%~1/%~1/float16/1/%~1.task"
if errorlevel 1 exit /b 1
move /y "models\%~1.download" "models\%~1.task" >nul
exit /b %errorlevel%

:failed
echo Mouth Alarm could not start. See the error above.
pause
exit /b 1
