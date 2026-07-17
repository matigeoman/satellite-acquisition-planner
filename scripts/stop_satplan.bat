@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_satplan.ps1" %*
exit /b %ERRORLEVEL%
