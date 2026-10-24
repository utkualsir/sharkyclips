@echo off
rem Remove ClipForge (asks before deleting your projects).
rem ClipForge'u kaldirir (projelerinizi silmeden once sorar).
cd /d "%TEMP%"
rem "(goto)" ends this batch file first, so cmd does not look for it after it was deleted.
(goto) 2>nul & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
