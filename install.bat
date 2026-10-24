@echo off
rem ClipForge setup for Windows 10/11: double-click this file.
rem Kurulum: bu dosyaya cift tiklayin.
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\windows\install.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%CLIPFORGE_NO_PAUSE%"=="1" (
  echo.
  pause
)
exit /b %RC%
