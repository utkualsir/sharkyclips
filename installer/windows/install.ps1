<#
SharkyClips installer for Windows 10 / 11.

Double-click install.bat (it runs this script). It lists what will be installed, asks once,
then installs Python, FFmpeg, Git, Deno, Ollama (with winget), the Python packages (in
SharkyClips\.venv), the AI models, and creates a "SharkyClips" desktop shortcut + Start menu entry.

Run outside a SharkyClips folder (e.g. as the downloaded SharkyClips-Setup.bat), it first downloads
SharkyClips with git into %USERPROFILE%\SharkyClips (or -InstallDir).

Options:
  -Yes            don't ask, install everything (unattended)
  -DryRun         only show what would be installed
  -Lang tr|en     message language (default: the Windows display language)
  -InstallDir D   where to download SharkyClips when the script runs on its own
  -NoModels       don't download the AI models now (they download on first use)
  -NoShortcuts    don't create shortcuts or the "Apps & features" entry
  -ShortcutDir D  put the shortcuts in folder D instead (for testing; no Apps entry)
  -NoLaunch       don't offer to start SharkyClips at the end
#>
[CmdletBinding()]
param(
    [switch]$Yes,
    [switch]$DryRun,
    [ValidateSet('auto', 'tr', 'en')][string]$Lang = 'auto',
    [string]$InstallDir,
    [switch]$NoModels,
    [switch]$NoShortcuts,
    [string]$ShortcutDir,
    [switch]$NoLaunch,
    # Internal: set when the downloaded setup hands over to the installer of the new copy.
    [switch]$Confirmed,
    [string]$PreInstalled = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$RepoUrl = 'https://github.com/utkualsir/sharkyclips.git'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# ------------------------------------------------------------------ messages

if ($Lang -eq 'auto') {
    $Lang = 'en'
    try { if ((Get-UICulture).TwoLetterISOLanguageName -eq 'tr') { $Lang = 'tr' } } catch { }
}
function T([string]$tr, [string]$en) { if ($Lang -eq 'tr') { return $tr } return $en }

function Say([string]$text, [string]$color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Step([int]$n, [int]$total, [string]$text) { Write-Host ''; Write-Host "[$n/$total] $text" -ForegroundColor Cyan }
function Ok([string]$text) { Write-Host "  OK  $text" -ForegroundColor Green }
function Warn([string]$text) { Write-Host "  !   $text" -ForegroundColor Yellow }
function Fail([string]$text) {
    Write-Host ''
    Write-Host (T 'Kurulum tamamlanamadı:' 'Setup could not finish:') -ForegroundColor Red
    Write-Host "  $text" -ForegroundColor Red
    exit 1
}

function Ask([string]$question, [bool]$default = $true) {
    if ($Yes) { return $true }
    $hint = if ($default) { (T '[E/h]' '[Y/n]') } else { (T '[e/H]' '[y/N]') }
    $answer = Read-Host "$question $hint"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $default }
    return $answer.Trim().ToLower() -match '^(e|evet|y|yes)$'
}

# ------------------------------------------------------------------ detection helpers

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Find-Exe([string]$name, [string[]]$extra = @()) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source -notlike '*\WindowsApps\*') { return $cmd.Source }
    foreach ($p in $extra) { if ($p -and (Test-Path -LiteralPath $p)) { return $p } }
    return $null
}

function Python-Version([string]$exe, [string[]]$pre = @()) {
    try {
        $v = & $exe @pre -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { return "$v".Trim() }
    } catch { }
    return $null
}

function Python-Ok([string]$version) {
    if (-not $version) { return $false }
    $p = $version.Split('.')
    return ([int]$p[0] -eq 3 -and [int]$p[1] -ge 11 -and [int]$p[1] -le 13)
}

# Returns the full path of a Python 3.11-3.13 (3.12 preferred), or $null.
function Find-Python {
    $py = Find-Exe 'py' @("$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe", "$env:WINDIR\py.exe")
    if ($py) {
        foreach ($minor in '3.12', '3.11', '3.13') {
            if (Python-Ok (Python-Version $py @("-$minor"))) {
                try { $exe = & $py "-$minor" -c "import sys; print(sys.executable)" 2>$null } catch { $exe = $null }
                if ($exe) { return "$exe".Trim() }
            }
        }
    }
    $candidates = @()
    $cmd = Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*\WindowsApps\*' }
    if ($cmd) { $candidates += $cmd.Source }
    foreach ($v in '312', '311', '313') {
        $candidates += "$env:LOCALAPPDATA\Programs\Python\Python$v\python.exe"
        $candidates += "$env:ProgramFiles\Python$v\python.exe"
    }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c) -and (Python-Ok (Python-Version $c))) { return $c }
    }
    return $null
}

function Winget-Install([string]$id, [string]$label) {
    Say ("  winget install $id ...") 'DarkGray'
    & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Host
    # winget's exit codes are not reliable ("already installed" is an error), so callers re-detect.
    Refresh-Path
}

function Ollama-Path {
    return Find-Exe 'ollama' @("$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")
}

# ------------------------------------------------------------------ where is SharkyClips?

$ScriptDir = $PSScriptRoot
$Bootstrap = $false
$AppDir = $null
if ($ScriptDir) {
    $candidate = [IO.Path]::GetFullPath((Join-Path $ScriptDir '..\..'))
    if (Test-Path -LiteralPath (Join-Path $candidate 'backend\cli.py')) { $AppDir = $candidate }
}
if (-not $AppDir) {
    $Bootstrap = $true
    if ($InstallDir) { $AppDir = [IO.Path]::GetFullPath($InstallDir) } else { $AppDir = Join-Path $env:USERPROFILE 'SharkyClips' }
}
$Venv = Join-Path $AppDir '.venv'
$VenvPy = Join-Path $Venv 'Scripts\python.exe'

Write-Host ''
Write-Host '  SharkyClips' -ForegroundColor Yellow -NoNewline
Write-Host (T '  -  Yayıncılar için ücretsiz, yerel, yapay zekâlı Shorts kesici' '  -  Free, local, AI-powered Shorts clipper for streamers')
Write-Host ('  ' + (T 'Kurulum klasörü: ' 'Install folder: ') + $AppDir) -ForegroundColor DarkGray
Write-Host ''

# Some Python packages have very deep file paths; Windows limits paths to 260 characters
# unless "long paths" are enabled. Stop early with a clear message instead of a pip error.
$longPaths = $false
try { $longPaths = ((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction Stop).LongPathsEnabled -eq 1) } catch { }
if (-not $longPaths -and $AppDir.Length -gt 110) {
    Fail ((T 'Kurulum klasörünün yolu çok uzun ({0} karakter). Windows 260 karakterden uzun dosya yollarına izin vermiyor. SharkyClips klasörünü daha kısa bir yere taşıyın (ör. C:\SharkyClips) veya Windows''ta uzun yolları açın: https://pip.pypa.io/warnings/enable-long-paths' 'The install folder path is too long ({0} characters): Windows limits file paths to 260 characters. Move the SharkyClips folder somewhere shorter (e.g. C:\SharkyClips) or enable long paths in Windows: https://pip.pypa.io/warnings/enable-long-paths') -f $AppDir.Length)
}

if ([Environment]::OSVersion.Version.Major -lt 10) { Fail (T 'SharkyClips için Windows 10 veya 11 gerekiyor.' 'SharkyClips needs Windows 10 or 11.') }
if (-not [Environment]::Is64BitOperatingSystem) { Fail (T 'SharkyClips 64 bit Windows gerektirir.' 'SharkyClips needs 64-bit Windows.') }

# ------------------------------------------------------------------ what is there already?

Say (T 'Bilgisayarınız kontrol ediliyor...' 'Checking your computer...')
$winget = Find-Exe 'winget' @("$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe")
$venvVersion = $null
if (Test-Path -LiteralPath $VenvPy) { $venvVersion = Python-Version $VenvPy; if (-not (Python-Ok $venvVersion)) { $venvVersion = $null } }
$python = $null
if (-not $venvVersion) { $python = Find-Python }
$ffmpeg = Find-Exe 'ffmpeg'
$ffprobe = Find-Exe 'ffprobe'
$git = Find-Exe 'git' @("$env:ProgramFiles\Git\cmd\git.exe")
$jsRuntime = Find-Exe 'deno' @("$env:USERPROFILE\.deno\bin\deno.exe")
if (-not $jsRuntime) { $jsRuntime = Find-Exe 'node' }
$ollama = Ollama-Path
$nvidiaSmi = Find-Exe 'nvidia-smi' @("$env:WINDIR\System32\nvidia-smi.exe")
$gpuName = $null
if ($nvidiaSmi) {
    try { $gpuName = (& $nvidiaSmi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1) } catch { }
    if ($gpuName) { $gpuName = "$gpuName".Trim() }
}

# The plan: what is found, what will be installed. Sizes are rough download sizes.
$plan = New-Object System.Collections.ArrayList
function Add-Plan([string]$label, [bool]$found, [string]$detail, [string]$size, [string]$wingetId) {
    [void]$plan.Add([pscustomobject]@{ Label = $label; Found = $found; Detail = $detail; Size = $size; Id = $wingetId })
}
if ($venvVersion) { Add-Plan 'Python' $true "$venvVersion (SharkyClips\.venv)" '' '' }
elseif ($python) { Add-Plan 'Python' $true ("$(Python-Version $python)") '' '' }
else { Add-Plan 'Python 3.12' $false (T 'programlama dili, SharkyClips onunla çalışır' 'runs SharkyClips') '~30 MB' 'Python.Python.3.12' }
if ($ffmpeg -and $ffprobe) { Add-Plan 'FFmpeg' $true $ffmpeg '' '' }
else { Add-Plan 'FFmpeg' $false (T 'video ve ses işleme' 'video and audio processing') '~200 MB' 'Gyan.FFmpeg' }
if ($git) { Add-Plan 'Git' $true $git '' '' }
else { Add-Plan 'Git' $false (T 'SharkyClips''i indirir ve günceller' 'downloads and updates SharkyClips') '~60 MB' 'Git.Git' }
if ($jsRuntime) { Add-Plan 'JavaScript runtime' $true $jsRuntime '' '' }
else { Add-Plan 'Deno' $false (T 'YouTube indirmeleri için gerekli' 'needed for YouTube downloads') '~40 MB' 'DenoLand.Deno' }
if ($ollama) { Add-Plan 'Ollama' $true $ollama '' '' }
else { Add-Plan 'Ollama' $false (T 'yerel yapay zekâ (başlıklar, viral puan)' 'local AI (titles, viral score)') '~700 MB' 'Ollama.Ollama' }

$pkgSize = '~1.5 GB'
if ($gpuName) { $pkgSize = '~3 GB' }
$pkgDetail = T 'Python paketleri (SharkyClips\.venv içine)' 'Python packages (inside SharkyClips\.venv)'
if ($gpuName) { $pkgDetail += T " + NVIDIA CUDA kütüphaneleri ($gpuName)" " + NVIDIA CUDA libraries ($gpuName)" }

$missing = @($plan | Where-Object { -not $_.Found })

Write-Host ''
Write-Host (T 'SharkyClips şunları kuracak:' 'SharkyClips will set up:') -ForegroundColor White
foreach ($item in $plan) {
    if ($item.Found) {
        Write-Host ('  [' + (T 'var  ' 'found') + '] ') -ForegroundColor Green -NoNewline
        Write-Host "$($item.Label)  " -NoNewline
        Write-Host $item.Detail -ForegroundColor DarkGray
    } else {
        Write-Host ('  [' + (T 'kur  ' 'new  ') + '] ') -ForegroundColor Yellow -NoNewline
        Write-Host "$($item.Label) - $($item.Detail)  " -NoNewline
        Write-Host $item.Size -ForegroundColor DarkGray
    }
}
Write-Host ('  [' + (T 'kur  ' 'new  ') + '] ') -ForegroundColor Yellow -NoNewline
Write-Host "$pkgDetail  " -NoNewline; Write-Host $pkgSize -ForegroundColor DarkGray
if (-not $NoModels) {
    Write-Host ('  [' + (T 'kur  ' 'new  ') + '] ') -ForegroundColor Yellow -NoNewline
    Write-Host (T 'Yapay zekâ modelleri: Whisper (konuşmayı yazıya döker) + yerel dil modeli (Qwen 3.5)  ' 'AI models: Whisper (speech to text) + local language model (Qwen 3.5)  ') -NoNewline
    Write-Host (T '~2-8 GB, donanıma göre' '~2-8 GB, depends on your hardware') -ForegroundColor DarkGray
}
if (-not $NoShortcuts) {
    Write-Host ('  [' + (T 'oluştur' 'create') + '] ') -ForegroundColor Yellow -NoNewline
    Write-Host (T 'Masaüstü kısayolu + Başlat menüsü kaydı "SharkyClips"' 'Desktop shortcut + Start menu entry "SharkyClips"')
}
if ($Bootstrap) {
    Write-Host ('  [' + (T 'indir ' 'get  ') + '] ') -ForegroundColor Yellow -NoNewline
    Write-Host (T "SharkyClips -> $AppDir" "SharkyClips -> $AppDir")
}

$drive = $null
try {
    $root = [IO.Path]::GetPathRoot($AppDir)
    $drive = New-Object System.IO.DriveInfo($root)
    $freeGb = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
    Write-Host ''
    Write-Host ((T 'Gereken yer: en fazla ~12 GB. Boş yer ({0}): {1} GB' 'Space needed: up to ~12 GB. Free space ({0}): {1} GB') -f $root, $freeGb) -ForegroundColor DarkGray
    if ($freeGb -lt 12) { Warn (T 'Disk alanı az; büyük modeller sığmayabilir.' 'Low disk space; the big models may not fit.') }
} catch { }
Write-Host (T 'Her şey bu bilgisayarda çalışır. Hiçbir videonuz internete yüklenmez.' 'Everything runs on this computer. None of your videos are uploaded anywhere.') -ForegroundColor DarkGray
Write-Host ''

if ($DryRun) {
    Say (T 'Deneme modu (-DryRun): hiçbir şey kurulmadı.' 'Dry run (-DryRun): nothing was installed.') 'Yellow'
    exit 0
}
if (-not $Confirmed -and -not (Ask (T 'Kuruluma başlansın mı?' 'Start the installation?') $true)) {
    Say (T 'İptal edildi. Hiçbir şey değiştirilmedi.' 'Cancelled. Nothing was changed.') 'Yellow'
    exit 0
}

# ------------------------------------------------------------------ install

$total = 6
$n = 0
$installedTools = @($PreInstalled.Split(',') | Where-Object { $_ })

# 1. System tools ----------------------------------------------------
$n++; Step $n $total (T 'Sistem araçları' 'System tools')
if ($missing.Count -gt 0 -and -not $winget) {
    Fail (T 'winget bulunamadı. Microsoft Store''dan "Uygulama Yükleyici"yi (App Installer) kurun/güncelleyin ve tekrar deneyin.' 'winget was not found. Install or update "App Installer" from the Microsoft Store, then run the installer again.')
}
foreach ($item in $missing) {
    Say ((T '  {0} kuruluyor...' '  Installing {0}...') -f $item.Label)
    Winget-Install $item.Id $item.Label
    $installedTools += $item.Id
}
if (-not $venvVersion) {
    $python = Find-Python
    if (-not $python) { Fail (T 'Python 3.12 kurulamadı. https://www.python.org/downloads/ adresinden kurup tekrar deneyin.' 'Python 3.12 could not be installed. Install it from https://www.python.org/downloads/ and run the installer again.') }
    Ok ("Python $(Python-Version $python)")
} else { Ok "Python $venvVersion" }
$ffmpeg = Find-Exe 'ffmpeg'
if ($ffmpeg) { Ok 'FFmpeg' } else { Warn (T 'FFmpeg bulunamadı. Yeni bir pencere açıp kurulumu tekrar çalıştırın.' 'FFmpeg not found. Open a new window and run the installer again.') }
$git = Find-Exe 'git' @("$env:ProgramFiles\Git\cmd\git.exe")
if ($git) { Ok 'Git' } else { Warn (T 'Git bulunamadı: otomatik güncelleme çalışmaz.' 'Git not found: automatic updates won''t work.') }
$ollama = Ollama-Path
# Ollama's installer makes it start with Windows. SharkyClips starts it only when needed (Settings
# can turn autostart back on), so its Startup shortcut is parked in ~/.sharkyclips.
$ollamaStartup = Join-Path ([Environment]::GetFolderPath('Startup')) 'Ollama.lnk'
if (Test-Path $ollamaStartup) {
    $parked = Join-Path $env:USERPROFILE '.sharkyclips\disabled-startup'
    New-Item -ItemType Directory -Force -Path $parked | Out-Null
    Move-Item -Force $ollamaStartup (Join-Path $parked 'Ollama.lnk')
}
if ($ollama) { Ok 'Ollama' } else { Warn (T 'Ollama bulunamadı: yapay zekâ başlıkları kapalı kalır.' 'Ollama not found: AI titles stay off.') }

# 2. SharkyClips itself ------------------------------------------------
$n++; Step $n $total 'SharkyClips'
if ($Bootstrap) {
    if (-not $git) { Fail (T 'SharkyClips''i indirmek için Git gerekli.' 'Git is needed to download SharkyClips.') }
    if (Test-Path -LiteralPath (Join-Path $AppDir '.git')) {
        & $git -C $AppDir pull --ff-only --quiet
        if ($LASTEXITCODE -ne 0) { Warn (T 'Güncelleme alınamadı, mevcut sürümle devam ediliyor.' 'Could not pull updates, continuing with the current version.') }
    } elseif ((Test-Path -LiteralPath $AppDir) -and (Get-ChildItem -LiteralPath $AppDir -Force | Select-Object -First 1)) {
        Fail ((T '{0} klasörü dolu. Başka bir klasör seçin: -InstallDir <klasör>' 'The folder {0} is not empty. Pick another one: -InstallDir <folder>') -f $AppDir)
    } else {
        Say (T '  İndiriliyor (git clone)...' '  Downloading (git clone)...') 'DarkGray'
        & $git clone --quiet $RepoUrl $AppDir
        if ($LASTEXITCODE -ne 0) { Fail (T 'SharkyClips indirilemedi (git clone).' 'Could not download SharkyClips (git clone).') }
    }
    # Continue with the installer that came with this version.
    $next = Join-Path $AppDir 'installer\windows\install.ps1'
    $forward = @('-Lang', $Lang, '-Confirmed')
    if ($installedTools.Count -gt 0) { $forward += @('-PreInstalled', ($installedTools -join ',')) }
    if ($Yes) { $forward += '-Yes' }
    if ($NoModels) { $forward += '-NoModels' }
    if ($NoShortcuts) { $forward += '-NoShortcuts' }
    if ($ShortcutDir) { $forward += @('-ShortcutDir', $ShortcutDir) }
    if ($NoLaunch) { $forward += '-NoLaunch' }
    Ok $AppDir
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $next @forward
    exit $LASTEXITCODE
}
Ok $AppDir
$version = '?'
try {
    # One source of truth for the version: the VERSION file at the repo root.
    $version = (Get-Content -LiteralPath (Join-Path $AppDir 'VERSION') -Raw).Trim()
} catch { }

# 3. Python environment ----------------------------------------------
$n++; Step $n $total (T 'Python ortamı (.venv)' 'Python environment (.venv)')
if (-not $venvVersion) {
    if (Test-Path -LiteralPath $Venv) { Remove-Item -LiteralPath $Venv -Recurse -Force }
    & $python -m venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPy)) { Fail (T 'Python ortamı oluşturulamadı.' 'Could not create the Python environment.') }
}
Ok $Venv

# 4. Python packages -------------------------------------------------
$n++; Step $n $total ((T 'Python paketleri ({0}, birkaç dakika sürebilir)' 'Python packages ({0}, this can take a few minutes)') -f $pkgSize)
& $VenvPy -m pip install --upgrade --quiet --disable-pip-version-check pip
$reqs = @('-r', (Join-Path $AppDir 'backend\requirements.txt'))
if ($gpuName) { $reqs += @('-r', (Join-Path $AppDir 'backend\requirements-nvidia.txt')) }
& $VenvPy -m pip install --upgrade --disable-pip-version-check --progress-bar on @reqs
if ($LASTEXITCODE -ne 0) {
    Warn (T 'Bir paket kurulamadı, bir kez daha deneniyor...' 'A package failed to install, trying once more...')
    & $VenvPy -m pip install --upgrade --disable-pip-version-check @reqs
    if ($LASTEXITCODE -ne 0) { Fail (T 'Python paketleri kurulamadı (hata yukarıda). İnternet bağlantınızı ve boş disk alanını kontrol edip tekrar deneyin.' 'Python packages could not be installed (see the error above). Check your internet connection and free disk space, then try again.') }
}
Ok (T 'Paketler kuruldu' 'Packages installed')

# 5. Check everything + AI models (doctor) ---------------------------
$n++; Step $n $total (T 'Kontrol ve yapay zekâ modelleri (ilk seferde uzun sürebilir)' 'Checks and AI models (the first time can take a while)')
$doctorArgs = @((Join-Path $AppDir 'backend\cli.py'), 'doctor')
if ($NoModels) { $doctorArgs += '--no-fix' } else { $doctorArgs += '--download-models' }
$env:PYTHONIOENCODING = 'utf-8'
& $VenvPy @doctorArgs
if ($LASTEXITCODE -ne 0) {
    Warn (T 'Kontrolde eksikler var (yukarıdaki tabloya bakın). SharkyClips yine de açılır; "python cli.py doctor" ile tekrar kontrol edebilirsiniz.' 'Some checks failed (see the table above). SharkyClips still opens; run the installer again to retry.')
}

# 6. Shortcuts --------------------------------------------------------
$n++; Step $n $total (T 'Kısayollar' 'Shortcuts')
# pythonw: no console window; SharkyClips shows a tray icon (Open / performance mode / Quit).
$launcher = Join-Path $AppDir '.venv\Scripts\pythonw.exe'
$launcherArgs = '"' + (Join-Path $AppDir 'backend\cli.py') + '" launch --tray'
$icon = Join-Path $AppDir 'assets\icon\sharkyclips.ico'
function New-Shortcut([string]$path, [string]$target, [string]$description) {
    $shell = New-Object -ComObject WScript.Shell
    $s = $shell.CreateShortcut($path)
    $s.TargetPath = $target
    $s.Arguments = $launcherArgs
    $s.WorkingDirectory = $AppDir
    $s.IconLocation = "$icon,0"
    $s.Description = $description
    $s.Save()
}
if ($NoShortcuts) {
    Say (T '  Atlandı (-NoShortcuts).' '  Skipped (-NoShortcuts).') 'DarkGray'
} else {
    $desc = T 'SharkyClips: yayınlarınızdan Shorts kesin' 'SharkyClips: clip Shorts from your streams'
    if ($ShortcutDir) {
        New-Item -ItemType Directory -Force -Path $ShortcutDir | Out-Null
        $desktop = $ShortcutDir; $startMenu = $ShortcutDir
    } else {
        $desktop = [Environment]::GetFolderPath('Desktop')
        $startMenu = [Environment]::GetFolderPath('Programs')
    }
    # Shortcuts under the old name (ClipForge, before 1.2.1) that point here are replaced.
    foreach ($d in @($desktop, $startMenu)) {
        $old = Join-Path $d 'ClipForge.lnk'
        if (Test-Path -LiteralPath $old) {
            $s = (New-Object -ComObject WScript.Shell).CreateShortcut($old)
            if (($s.TargetPath + ' ' + $s.Arguments) -like "*$AppDir*") { Remove-Item -LiteralPath $old -Force }
        }
    }
    New-Shortcut (Join-Path $desktop 'SharkyClips.lnk') $launcher $desc
    Ok ((T 'Masaüstü: {0}' 'Desktop: {0}') -f (Join-Path $desktop 'SharkyClips.lnk'))
    if ($startMenu -ne $desktop) {
        New-Shortcut (Join-Path $startMenu 'SharkyClips.lnk') $launcher $desc
        Ok ((T 'Başlat menüsü: {0}' 'Start menu: {0}') -f (Join-Path $startMenu 'SharkyClips.lnk'))
    }
    if (-not $ShortcutDir) {
        # "Apps & features" entry, so SharkyClips can be removed like any other app.
        $key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SharkyClips'
        $oldKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipForge'
        if ((Test-Path $oldKey) -and ((Get-ItemProperty $oldKey).InstallLocation -eq $AppDir)) { Remove-Item -Path $oldKey -Recurse -Force }
        New-Item -Path $key -Force | Out-Null
        $uninstall = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $AppDir 'installer\windows\uninstall.ps1') + '"'
        $values = @{
            DisplayName = 'SharkyClips'; DisplayVersion = $version; Publisher = 'SharkyClips'
            DisplayIcon = $icon; InstallLocation = $AppDir; UninstallString = $uninstall
            URLInfoAbout = 'https://github.com/utkualsir/sharkyclips'
        }
        foreach ($k in $values.Keys) { Set-ItemProperty -Path $key -Name $k -Value $values[$k] }
        Set-ItemProperty -Path $key -Name NoModify -Value 1 -Type DWord
        Set-ItemProperty -Path $key -Name NoRepair -Value 1 -Type DWord
        Ok (T 'Uygulamalar listesine eklendi (oradan kaldırılabilir)' 'Added to Apps & features (uninstall from there)')
    }
}

# Remember which tools this installer added, so the uninstaller can mention them.
try {
    $statePath = Join-Path $AppDir '.install-state.json'
    $old = @()
    if (Test-Path -LiteralPath $statePath) { $old = @((Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json).installed_tools) }
    $state = @{ version = $version; installed_at = (Get-Date).ToString('s'); installed_tools = @($old + $installedTools | Where-Object { $_ } | Select-Object -Unique) }
    $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
} catch { }

Write-Host ''
Write-Host ((T 'SharkyClips {0} hazır!' 'SharkyClips {0} is ready!') -f $version) -ForegroundColor Green
Write-Host (T 'Masaüstündeki "SharkyClips" simgesine çift tıklayın: tarayıcıda açılır. Pencere açılmaz; saatin yanındaki SharkyClips simgesinden açabilir veya kapatabilirsiniz.' 'Double-click "SharkyClips" on your desktop: it opens in your browser. No window stays open; use the SharkyClips icon next to the clock to open or quit it.')

if (-not $NoLaunch -and -not $Yes) {
    if (Ask (T 'SharkyClips şimdi açılsın mı?' 'Open SharkyClips now?') $true) {
        Start-Process -FilePath $launcher -ArgumentList $launcherArgs -WorkingDirectory $AppDir
    }
}
exit 0
