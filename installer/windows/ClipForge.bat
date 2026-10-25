@echo off
rem ClipForge launcher (older shortcuts run this; new ones start pythonw directly).
rem Starts ClipForge without a console window: a tray icon opens or quits it.
title ClipForge
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo ClipForge is not installed yet. Run install.bat first.
  echo ClipForge henuz kurulmamis. Once install.bat dosyasini calistirin.
  pause
  exit /b 1
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" backend\cli.py launch --tray
  exit /b 0
)
".venv\Scripts\python.exe" backend\cli.py launch
if errorlevel 1 pause
