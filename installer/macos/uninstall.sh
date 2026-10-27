#!/bin/bash
# Remove SharkyClips from this Mac. Asks before deleting your projects, settings and AI models
# (the default answer keeps them). Homebrew packages (python, ffmpeg, git, deno, ollama) stay.
#
#   bash installer/macos/uninstall.sh [--yes] [--delete-projects] [--lang tr|en] [--shortcut-dir DIR]

set -u
YES=0; DELETE_PROJECTS=0; LANG_CHOICE="auto"; SHORTCUT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --delete-projects) DELETE_PROJECTS=1 ;;
    --lang) LANG_CHOICE="$2"; shift ;;
    --shortcut-dir) SHORTCUT_DIR="$2"; shift ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
  shift
done
if [ "$LANG_CHOICE" = "auto" ]; then
  LANG_CHOICE="en"
  apple_lang="$(defaults read -g AppleLanguages 2>/dev/null | tr -d ' ",()\n' | cut -c1-2)"
  case "${apple_lang:-${LANG:-}}" in tr*) LANG_CHOICE="tr" ;; esac
fi
t() { if [ "$LANG_CHOICE" = "tr" ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
ok() { printf '  \033[32mOK\033[0m  %s\n' "$1"; }
ask() {
  if [ "$YES" = 1 ]; then [ "$2" = 1 ]; return; fi
  if [ "$2" = 1 ]; then hint="$(t '[E/h]' '[Y/n]')"; else hint="$(t '[e/H]' '[y/N]')"; fi
  printf '%s %s ' "$1" "$hint"
  read -r answer </dev/tty || answer=""
  answer="$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')"
  if [ -z "$answer" ]; then [ "$2" = 1 ]; return; fi
  case "$answer" in e|evet|y|yes) return 0 ;; *) return 1 ;; esac
}

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$APP_DIR/backend/cli.py" ] || { echo "$APP_DIR is not a SharkyClips folder."; exit 1; }
cd /tmp || exit 1

echo
echo "$(t 'SharkyClips kaldırılacak:' 'This removes SharkyClips:') $APP_DIR"
if [ "$YES" = 0 ]; then ask "$(t 'Devam edilsin mi?' 'Continue?')" 0 || { echo "$(t 'İptal edildi.' 'Cancelled.')"; exit 0; }; fi

CONFIG_DIR="${SHARKYCLIPS_HOME:-$HOME/.sharkyclips}"
WORKSPACE="$APP_DIR/workspace"
custom="$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("workspace_dir") or "")' "$CONFIG_DIR/config.json" 2>/dev/null)"
[ -n "$custom" ] && WORKSPACE="${custom/#\~/$HOME}"
projects=0
if [ -d "$WORKSPACE" ]; then projects="$(find "$WORKSPACE" -mindepth 1 -maxdepth 1 -type d ! -name '_*' ! -name '.*' | wc -l | tr -d ' ')"; fi
delete_ws=0
if [ "$projects" -gt 0 ]; then
  size="$(du -sh "$WORKSPACE" 2>/dev/null | cut -f1)"
  echo "$(t "Projeleriniz: $projects proje, $size ($WORKSPACE)" "Your projects: $projects projects, $size ($WORKSPACE)")"
  if [ "$YES" = 1 ]; then delete_ws=$DELETE_PROJECTS
  elif ask "$(t 'Projeler ve kesilmiş klipler de SİLİNSİN mi? (geri alınamaz)' 'Also DELETE these projects and rendered clips? (cannot be undone)')" 0; then delete_ws=1; fi
fi
delete_cfg=0
if [ -d "$CONFIG_DIR" ] && [ "$YES" = 0 ] && ask "$(t "Ayarlar ve öğrenilmiş başlık tarzınız ($CONFIG_DIR) silinsin mi?" "Delete your settings and learned title style ($CONFIG_DIR)?")" 0; then delete_cfg=1; fi
delete_models=0
if [ "$YES" = 0 ] && ask "$(t 'İndirilmiş yapay zekâ modelleri (Whisper, Qwen 3.5) silinsin mi?' 'Delete the downloaded AI models (Whisper, Qwen 3.5)?')" 0; then delete_models=1; fi

pkill -f "$APP_DIR/.venv/bin/python" 2>/dev/null
desk="${SHORTCUT_DIR:-$HOME/Desktop}"
# ClipForge = the name before 1.2.1 (launchers the app hasn't renamed yet)
for name in SharkyClips ClipForge; do
  if grep -q "$APP_DIR" "$desk/$name.command" 2>/dev/null; then rm -f "$desk/$name.command"; ok "$desk/$name.command"; fi
  app="${SHORTCUT_DIR:-$HOME/Applications}/$name.app"
  if grep -q "$APP_DIR" "$app/Contents/MacOS/$name" 2>/dev/null; then rm -rf "$app"; ok "$app"; fi
done
if [ "$delete_models" = 1 ]; then
  hub="${HF_HOME:-$HOME/.cache/huggingface}/hub"
  rm -rf "$hub"/models--*faster-whisper* "$hub"/models--mlx-community--whisper* 2>/dev/null
  if command -v ollama >/dev/null 2>&1; then
    for m in $(ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep '^qwen3.5:'); do ollama rm "$m" >/dev/null; done
  fi
  ok "$(t 'Modeller silindi' 'Models deleted')"
fi
[ "$delete_cfg" = 1 ] && rm -rf "$CONFIG_DIR" && ok "$CONFIG_DIR"
# the settings folder before 1.2.1, if the app never moved it
[ "$delete_cfg" = 1 ] && [ -z "${SHARKYCLIPS_HOME:-}" ] && [ -d "$HOME/.clipforge" ] && rm -rf "$HOME/.clipforge"
[ "$delete_ws" = 1 ] && rm -rf "$WORKSPACE" && ok "$(t 'Projeler silindi' 'Projects deleted')"
if [ -d "$WORKSPACE" ] && [ "$projects" -gt 0 ] && [ "${WORKSPACE#"$APP_DIR"/}" != "$WORKSPACE" ]; then
  find "$APP_DIR" -mindepth 1 -maxdepth 1 ! -path "$WORKSPACE" -exec rm -rf {} +
  echo "$(t "Projeleriniz duruyor: $WORKSPACE" "Your projects are still here: $WORKSPACE")"
else
  rm -rf "$APP_DIR"
fi
ok "$(t 'SharkyClips kaldırıldı.' 'SharkyClips removed.')"
echo "$(t 'Homebrew paketleri yerinde bırakıldı (brew uninstall ile kaldırabilirsiniz).' 'Homebrew packages were left installed (remove them with brew uninstall).')"
