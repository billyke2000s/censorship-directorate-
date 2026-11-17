@echo off
call "%~dp0Start-MouthAlarm.cmd" --obs %*
exit /b %errorlevel%
