@echo off
rem ClipForge launcher: the desktop / Start menu shortcut runs this.
rem It opens ClipForge in your browser. Closing this window stops ClipForge.
title ClipForge
cd /d "%~dp0..\.."
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo ClipForge is not installed yet. Run install.bat first.
  echo ClipForge henuz kurulmamis. Once install.bat dosyasini calistirin.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" backend\cli.py launch
if errorlevel 1 pause
