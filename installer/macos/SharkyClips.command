#!/bin/bash
# SharkyClips launcher for macOS: opens SharkyClips in your browser.
# SharkyClips runs while this Terminal window is open; close it to stop SharkyClips.
cd "$(dirname "$0")/../.." || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "SharkyClips is not installed yet. Run: bash install.sh"
  echo "SharkyClips henüz kurulmamış. Çalıştırın: bash install.sh"
  read -r -p "Press Enter to close" _
  exit 1
fi
printf '\033]0;SharkyClips\007'
.venv/bin/python backend/cli.py launch || read -r -p "Press Enter to close" _
