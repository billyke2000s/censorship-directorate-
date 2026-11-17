@echo off
call "%~dp0Start-MouthAlarm.cmd" --virtual-mic %*
exit /b %errorlevel%
