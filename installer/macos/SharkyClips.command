#!/bin/bash
# SharkyClips launcher for macOS: opens SharkyClips in your browser.
# SharkyClips runs while this Terminal window is open; close it to stop SharkyClips.
cd "$(dirname "$0")/../.." || exit 1
APP_DIR="$(pwd)"
# A new Terminal window doesn't always have Homebrew on its PATH (fresh Apple Silicon Macs):
# without this, FFmpeg, Git and Deno from the installer wouldn't be found.
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  if [ -x "$b" ]; then eval "$("$b" shellenv)"; break; fi
done
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  echo "SharkyClips is not installed yet. Run: bash install.sh"
  echo "SharkyClips henüz kurulmamış. Çalıştırın: bash install.sh"
  read -r -p "Press Enter to close" _
  exit 1
fi
printf '\033]0;SharkyClips\007'
# Absolute paths: the uninstaller finds (and stops) this process by its command line.
"$APP_DIR/.venv/bin/python" "$APP_DIR/backend/cli.py" launch || read -r -p "Press Enter to close" _
