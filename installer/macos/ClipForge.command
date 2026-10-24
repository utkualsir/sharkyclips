#!/bin/bash
# ClipForge launcher for macOS: opens ClipForge in your browser.
# ClipForge runs while this Terminal window is open; close it to stop ClipForge.
cd "$(dirname "$0")/../.." || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "ClipForge is not installed yet. Run: bash install.sh"
  echo "ClipForge henüz kurulmamış. Çalıştırın: bash install.sh"
  read -r -p "Press Enter to close" _
  exit 1
fi
printf '\033]0;ClipForge\007'
.venv/bin/python backend/cli.py launch || read -r -p "Press Enter to close" _
