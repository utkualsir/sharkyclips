#!/bin/bash
# ClipForge installer for macOS (Apple Silicon and Intel).
#
#   bash install.sh            (from the ClipForge folder, or on its own: it then downloads
#                               ClipForge into ~/ClipForge first)
#
# Lists what will be installed, asks once, then installs Homebrew packages (python@3.12,
# ffmpeg, git, deno, ollama), the Python packages (in ClipForge/.venv), the AI models, a
# ClipForge.command on the Desktop and ClipForge.app in ~/Applications.
#
# Options: --yes (don't ask)  --dry-run  --lang tr|en  --install-dir DIR  --no-models
#          --no-shortcuts  --shortcut-dir DIR (testing)  --no-launch

set -u
REPO_URL="https://github.com/utkualsir/clipforge.git"

YES=0; DRY=0; LANG_CHOICE="auto"; INSTALL_DIR=""; NO_MODELS=0; NO_SHORTCUTS=0; SHORTCUT_DIR=""; NO_LAUNCH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --dry-run) DRY=1 ;;
    --lang) LANG_CHOICE="$2"; shift ;;
    --install-dir) INSTALL_DIR="$2"; shift ;;
    --no-models) NO_MODELS=1 ;;
    --no-shortcuts) NO_SHORTCUTS=1 ;;
    --shortcut-dir) SHORTCUT_DIR="$2"; shift ;;
    --no-launch) NO_LAUNCH=1 ;;
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

c_cyan=$'\033[36m'; c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_red=$'\033[31m'; c_dim=$'\033[2m'; c_off=$'\033[0m'
step() { printf '\n%s[%s/%s] %s%s\n' "$c_cyan" "$1" "$2" "$3" "$c_off"; }
ok() { printf '  %sOK%s  %s\n' "$c_green" "$c_off" "$1"; }
warn() { printf '  %s!%s   %s\n' "$c_yellow" "$c_off" "$1"; }
fail() { printf '\n%s%s%s\n  %s\n' "$c_red" "$(t 'Kurulum tamamlanamadı:' 'Setup could not finish:')" "$c_off" "$1"; exit 1; }
ask() {  # ask "question" default(1=yes)
  if [ "$YES" = 1 ]; then return 0; fi
  if [ "$2" = 1 ]; then hint="$(t '[E/h]' '[Y/n]')"; else hint="$(t '[e/H]' '[y/N]')"; fi
  printf '%s %s ' "$1" "$hint"
  read -r answer </dev/tty || answer=""
  answer="$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')"
  if [ -z "$answer" ]; then [ "$2" = 1 ]; return; fi
  case "$answer" in e|evet|y|yes) return 0 ;; *) return 1 ;; esac
}

[ "$(uname -s)" = "Darwin" ] || fail "$(t 'Bu betik macOS içindir. Windows: install.bat' 'This script is for macOS. Windows: install.bat')"

# ------------------------------------------------------------------ where is ClipForge?
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
BOOTSTRAP=0
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/backend/cli.py" ]; then
  APP_DIR="$SCRIPT_DIR"
else
  BOOTSTRAP=1
  APP_DIR="${INSTALL_DIR:-$HOME/ClipForge}"
fi
VENV="$APP_DIR/.venv"
VPY="$VENV/bin/python"

printf '\n  %sClipForge%s  -  %s\n' "$c_yellow" "$c_off" "$(t 'Yayıncılar için ücretsiz, yerel, yapay zekâlı Shorts kesici' 'Free, local, AI-powered Shorts clipper for streamers')"
printf '  %s%s%s%s\n\n' "$c_dim" "$(t 'Kurulum klasörü: ' 'Install folder: ')" "$APP_DIR" "$c_off"

# ------------------------------------------------------------------ detection
echo "$(t 'Bilgisayarınız kontrol ediliyor...' 'Checking your computer...')"
BREW=""
for b in /opt/homebrew/bin/brew /usr/local/bin/brew "$(command -v brew 2>/dev/null)"; do
  if [ -n "$b" ] && [ -x "$b" ]; then BREW="$b"; break; fi
done
if [ -n "$BREW" ]; then eval "$("$BREW" shellenv)"; fi

py_ok() {  # prints the version if $1 is Python 3.11-3.13
  v="$("$1" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)" || return 1
  case "$v" in 3.11.*|3.12.*|3.13.*) echo "$v"; return 0 ;; esac
  return 1
}
VENV_VERSION=""
if [ -x "$VPY" ]; then VENV_VERSION="$(py_ok "$VPY")" || VENV_VERSION=""; fi
PYTHON=""
if [ -z "$VENV_VERSION" ]; then
  for p in python3.12 python3.11 python3.13 python3; do
    c="$(command -v "$p" 2>/dev/null)" || continue
    if py_ok "$c" >/dev/null; then PYTHON="$c"; break; fi
  done
fi
have() { command -v "$1" >/dev/null 2>&1; }
ARCH="$(uname -m)"

TO_INSTALL=""   # brew formulae
list_line() {  # status label detail
  if [ "$1" = found ]; then printf '  %s[%s]%s %s  %s%s%s\n' "$c_green" "$(t 'var  ' 'found')" "$c_off" "$2" "$c_dim" "$3" "$c_off"
  else printf '  %s[%s]%s %s - %s  %s%s%s\n' "$c_yellow" "$(t 'kur  ' 'new  ')" "$c_off" "$2" "$3" "$c_dim" "$4" "$c_off"; fi
}
echo
echo "$(t 'ClipForge şunları kuracak:' 'ClipForge will set up:')"
if [ -z "$BREW" ]; then list_line new Homebrew "$(t 'macOS paket yöneticisi (yönetici parolası ister)' 'macOS package manager (asks for your password)')" "~300 MB"; fi
if [ -n "$VENV_VERSION" ]; then list_line found Python "$VENV_VERSION (ClipForge/.venv)"
elif [ -n "$PYTHON" ]; then list_line found Python "$(py_ok "$PYTHON")"
else list_line new "Python 3.12" "$(t 'ClipForge onunla çalışır' 'runs ClipForge')" "~70 MB"; TO_INSTALL="$TO_INSTALL python@3.12"; fi
if have ffmpeg && have ffprobe; then list_line found FFmpeg "$(command -v ffmpeg)"
else list_line new FFmpeg "$(t 'video ve ses işleme' 'video and audio processing')" "~100 MB"; TO_INSTALL="$TO_INSTALL ffmpeg"; fi
if have git; then list_line found Git "$(command -v git)"
else list_line new Git "$(t "ClipForge'u indirir ve günceller" 'downloads and updates ClipForge')" "~50 MB"; TO_INSTALL="$TO_INSTALL git"; fi
if have deno || have node; then list_line found "JavaScript runtime" "$(command -v deno || command -v node)"
else list_line new Deno "$(t 'YouTube indirmeleri için gerekli' 'needed for YouTube downloads')" "~40 MB"; TO_INSTALL="$TO_INSTALL deno"; fi
if have ollama || [ -x /Applications/Ollama.app/Contents/Resources/ollama ]; then list_line found Ollama "$(command -v ollama || echo /Applications/Ollama.app)"
else list_line new Ollama "$(t 'yerel yapay zekâ (başlıklar, viral puan)' 'local AI (titles, viral score)')" "~200 MB"; TO_INSTALL="$TO_INSTALL ollama"; fi
list_line new "$(t 'Python paketleri' 'Python packages')" "$(t 'ClipForge/.venv içine' 'inside ClipForge/.venv')" "~1 GB"
if [ "$NO_MODELS" = 0 ]; then
  list_line new "$(t 'Yapay zekâ modelleri' 'AI models')" "Whisper + Qwen 3.5" "$(t '~2-8 GB, donanıma göre' '~2-8 GB, depends on your Mac')"
fi
if [ "$NO_SHORTCUTS" = 0 ]; then
  printf '  %s[%s]%s %s\n' "$c_yellow" "$(t 'oluştur' 'create')" "$c_off" "$(t 'Masaüstünde ClipForge.command + Uygulamalar klasöründe ClipForge.app' 'ClipForge.command on the Desktop + ClipForge.app in Applications')"
fi
if [ "$BOOTSTRAP" = 1 ]; then printf '  %s[%s]%s ClipForge -> %s\n' "$c_yellow" "$(t 'indir ' 'get  ')" "$c_off" "$APP_DIR"; fi
free_gb="$(df -g "$(dirname "$APP_DIR")" 2>/dev/null | awk 'NR==2 {print $4}')"
echo
printf '%s%s%s\n' "$c_dim" "$(t "Gereken yer: en fazla ~12 GB. Boş yer: ${free_gb:-?} GB" "Space needed: up to ~12 GB. Free space: ${free_gb:-?} GB")" "$c_off"
if [ "$ARCH" != "arm64" ]; then warn "$(t 'Intel Mac: yazıya dökme işlemcide çalışır (daha yavaş).' 'Intel Mac: transcription runs on the CPU (slower).')"; fi
printf '%s%s%s\n\n' "$c_dim" "$(t 'Her şey bu bilgisayarda çalışır. Hiçbir videonuz internete yüklenmez.' 'Everything runs on this computer. None of your videos are uploaded anywhere.')" "$c_off"

if [ "$DRY" = 1 ]; then echo "$(t 'Deneme modu (--dry-run): hiçbir şey kurulmadı.' 'Dry run (--dry-run): nothing was installed.')"; exit 0; fi
ask "$(t 'Kuruluma başlansın mı?' 'Start the installation?')" 1 || { echo "$(t 'İptal edildi. Hiçbir şey değiştirilmedi.' 'Cancelled. Nothing was changed.')"; exit 0; }

TOTAL=6

# 1. System tools
step 1 $TOTAL "$(t 'Sistem araçları (Homebrew)' 'System tools (Homebrew)')"
if [ -z "$BREW" ]; then
  echo "$(t 'Homebrew kuruluyor (Mac parolanız istenecek)...' 'Installing Homebrew (it asks for your Mac password)...')"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty || fail "$(t 'Homebrew kurulamadı: https://brew.sh' 'Homebrew could not be installed: https://brew.sh')"
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do if [ -x "$b" ]; then BREW="$b"; fi; done
  [ -n "$BREW" ] || fail "Homebrew"
  eval "$("$BREW" shellenv)"
fi
if [ -n "$TO_INSTALL" ]; then
  # shellcheck disable=SC2086
  "$BREW" install $TO_INSTALL || warn "$(t 'Bazı paketler kurulamadı.' 'Some packages failed to install.')"
fi
if [ -z "$VENV_VERSION" ]; then
  PYTHON=""
  for p in "$("$BREW" --prefix)/bin/python3.12" python3.12 python3.11 python3.13 python3; do
    c="$(command -v "$p" 2>/dev/null)" || continue
    if py_ok "$c" >/dev/null; then PYTHON="$c"; break; fi
  done
  [ -n "$PYTHON" ] || fail "$(t 'Python 3.12 bulunamadı.' 'Python 3.12 was not found.')"
  ok "Python $(py_ok "$PYTHON")"
else ok "Python $VENV_VERSION"; fi
have ffmpeg && ok FFmpeg || warn "$(t 'FFmpeg bulunamadı.' 'FFmpeg not found.')"
have git && ok Git || warn "$(t 'Git bulunamadı: otomatik güncelleme çalışmaz.' "Git not found: automatic updates won't work.")"

# 2. ClipForge itself
step 2 $TOTAL ClipForge
if [ "$BOOTSTRAP" = 1 ]; then
  have git || fail "$(t "ClipForge'u indirmek için Git gerekli." 'Git is needed to download ClipForge.')"
  if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull --ff-only --quiet || warn "$(t 'Güncelleme alınamadı.' 'Could not pull updates.')"
  elif [ -d "$APP_DIR" ] && [ -n "$(ls -A "$APP_DIR" 2>/dev/null)" ]; then
    fail "$(t "$APP_DIR klasörü dolu. Başka bir klasör seçin: --install-dir <klasör>" "The folder $APP_DIR is not empty. Pick another one: --install-dir <folder>")"
  else
    git clone --quiet "$REPO_URL" "$APP_DIR" || fail "$(t 'ClipForge indirilemedi (git clone).' 'Could not download ClipForge (git clone).')"
  fi
  ok "$APP_DIR"
  args=(--yes --lang "$LANG_CHOICE")
  [ "$NO_MODELS" = 1 ] && args+=(--no-models)
  [ "$NO_SHORTCUTS" = 1 ] && args+=(--no-shortcuts)
  [ -n "$SHORTCUT_DIR" ] && args+=(--shortcut-dir "$SHORTCUT_DIR")
  [ "$NO_LAUNCH" = 1 ] && args+=(--no-launch)
  exec /bin/bash "$APP_DIR/install.sh" "${args[@]}"
fi
ok "$APP_DIR"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$APP_DIR/backend/clipforge/__init__.py")"

# 3. Python environment
step 3 $TOTAL "$(t 'Python ortamı (.venv)' 'Python environment (.venv)')"
if [ -z "$VENV_VERSION" ]; then
  rm -rf "$VENV"
  "$PYTHON" -m venv "$VENV" || fail "$(t 'Python ortamı oluşturulamadı.' 'Could not create the Python environment.')"
fi
ok "$VENV"

# 4. Python packages
step 4 $TOTAL "$(t 'Python paketleri (birkaç dakika sürebilir)' 'Python packages (this can take a few minutes)')"
"$VPY" -m pip install --upgrade --quiet --disable-pip-version-check pip
if ! "$VPY" -m pip install --upgrade --disable-pip-version-check -r "$APP_DIR/backend/requirements.txt"; then
  warn "$(t 'Bir kez daha deneniyor...' 'Trying once more...')"
  "$VPY" -m pip install --upgrade --disable-pip-version-check -r "$APP_DIR/backend/requirements.txt" \
    || fail "$(t 'Python paketleri kurulamadı.' 'Python packages could not be installed.')"
fi
ok "$(t 'Paketler kuruldu' 'Packages installed')"

# 5. Checks + AI models
step 5 $TOTAL "$(t 'Kontrol ve yapay zekâ modelleri (ilk seferde uzun sürebilir)' 'Checks and AI models (the first time can take a while)')"
if [ "$NO_MODELS" = 1 ]; then doctor_flag="--no-fix"; else doctor_flag="--download-models"; fi
"$VPY" "$APP_DIR/backend/cli.py" doctor "$doctor_flag" \
  || warn "$(t 'Kontrolde eksikler var (tabloya bakın). Kurulumu tekrar çalıştırabilirsiniz.' 'Some checks failed (see the table). You can run the installer again.')"

# 6. Shortcuts
step 6 $TOTAL "$(t 'Kısayollar' 'Shortcuts')"
LAUNCHER="$APP_DIR/installer/macos/ClipForge.command"
chmod +x "$LAUNCHER" "$APP_DIR/installer/macos/uninstall.sh" 2>/dev/null
if [ "$NO_SHORTCUTS" = 1 ]; then
  echo "  $(t 'Atlandı.' 'Skipped.')"
else
  desk="${SHORTCUT_DIR:-$HOME/Desktop}"
  apps="${SHORTCUT_DIR:-$HOME/Applications}"
  mkdir -p "$desk" "$apps"
  printf '#!/bin/bash\n# ClipForge: opens in your browser. Close this window to stop ClipForge.\nexec "%s"\n' "$LAUNCHER" > "$desk/ClipForge.command"
  chmod +x "$desk/ClipForge.command"
  ok "$desk/ClipForge.command"
  app="$apps/ClipForge.app"
  rm -rf "$app"
  mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
  cp "$APP_DIR/assets/icon/clipforge.icns" "$app/Contents/Resources/clipforge.icns"
  cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>ClipForge</string>
  <key>CFBundleDisplayName</key><string>ClipForge</string>
  <key>CFBundleIdentifier</key><string>io.github.utkualsir.clipforge</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>ClipForge</string>
  <key>CFBundleIconFile</key><string>clipforge</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PLIST
  # The app opens the launcher in Terminal (the window keeps the server running).
  printf '#!/bin/bash\nopen -a Terminal "%s"\n' "$LAUNCHER" > "$app/Contents/MacOS/ClipForge"
  chmod +x "$app/Contents/MacOS/ClipForge"
  touch "$app"
  ok "$app"
fi

printf '{"version": "%s", "installed_tools": "%s"}\n' "$VERSION" "$(echo $TO_INSTALL)" > "$APP_DIR/.install-state.json"

printf '\n%s%s%s\n' "$c_green" "$(t "ClipForge $VERSION hazır!" "ClipForge $VERSION is ready!")" "$c_off"
echo "$(t "Masaüstündeki ClipForge.command dosyasına veya Uygulamalar'daki ClipForge'a çift tıklayın: tarayıcıda açılır. Terminal penceresi açık kaldığı sürece çalışır." 'Double-click ClipForge.command on your Desktop or ClipForge in Applications: it opens in your browser and runs while its Terminal window is open.')"
if [ "$NO_LAUNCH" = 0 ] && [ "$YES" = 0 ]; then
  if ask "$(t 'ClipForge şimdi açılsın mı?' 'Open ClipForge now?')" 1; then open -a Terminal "$LAUNCHER"; fi
fi
exit 0
