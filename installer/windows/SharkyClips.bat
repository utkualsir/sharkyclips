@echo off
rem SharkyClips launcher (older shortcuts run this; new ones start pythonw directly).
rem Starts SharkyClips without a console window: a tray icon opens or quits it.
title SharkyClips
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo SharkyClips is not installed yet. Run install.bat first.
  echo SharkyClips henuz kurulmamis. Once install.bat dosyasini calistirin.
  pause
  exit /b 1
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" backend\cli.py launch --tray
  exit /b 0
)
".venv\Scripts\python.exe" backend\cli.py launch
if errorlevel 1 pause
