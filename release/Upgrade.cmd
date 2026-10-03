@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Upgrade.ps1" %*
if errorlevel 1 (echo Operation failed. & pause & exit /b 1)
pause
