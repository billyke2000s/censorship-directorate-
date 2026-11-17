@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Set up the Python environment first. See the Run from source section in README.md.
    goto failed
)
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 goto failed
exit /b 0

:failed
pause
exit /b 1
