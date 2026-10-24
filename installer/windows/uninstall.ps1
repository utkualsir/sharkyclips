<#
Remove ClipForge from this computer.

Removes the app folder, its Python packages (.venv), the shortcuts and the "Apps & features"
entry. Asks separately before deleting your projects (workspace), your settings and the
downloaded AI models; the default answer always keeps them.
Python, FFmpeg, Git, Deno and Ollama are left installed (other programs may use them).

Options:
  -Yes             don't ask; remove the app but keep projects, settings and AI models
  -DeleteProjects  with -Yes: also delete the projects
  -Lang tr|en
  -AppDir D        the ClipForge folder (default: the folder this script is in)
  -ShortcutDir D   shortcuts were created there (installer -ShortcutDir; for testing)
#>
[CmdletBinding()]
param(
    [switch]$Yes,
    [switch]$DeleteProjects,
    [ValidateSet('auto', 'tr', 'en')][string]$Lang = 'auto',
    [string]$AppDir,
    [string]$ShortcutDir
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
if ($Lang -eq 'auto') {
    $Lang = 'en'
    try { if ((Get-UICulture).TwoLetterISOLanguageName -eq 'tr') { $Lang = 'tr' } } catch { }
}
function T([string]$tr, [string]$en) { if ($Lang -eq 'tr') { return $tr } return $en }
function Ok([string]$text) { Write-Host "  OK  $text" -ForegroundColor Green }
function Ask([string]$question, [bool]$default) {
    if ($Yes) { return $default }
    $hint = if ($default) { (T '[E/h]' '[Y/n]') } else { (T '[e/H]' '[y/N]') }
    $answer = Read-Host "$question $hint"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $default }
    return $answer.Trim().ToLower() -match '^(e|evet|y|yes)$'
}
function Size-Gb([string]$path) {
    try {
        $bytes = (Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        return [math]::Round(($bytes / 1GB), 2)
    } catch { return 0 }
}

if (-not $AppDir) { $AppDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')) }
$AppDir = $AppDir.TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $AppDir 'backend\cli.py'))) {
    Write-Host ((T '{0} bir ClipForge klasörü değil.' '{0} is not a ClipForge folder.') -f $AppDir) -ForegroundColor Red
    exit 1
}
Set-Location -LiteralPath $env:TEMP  # we can't delete the folder we are standing in

Write-Host ''
Write-Host (T 'ClipForge kaldırılacak:' 'This removes ClipForge:') -ForegroundColor White
Write-Host "  $AppDir" -ForegroundColor DarkGray
Write-Host (T '  uygulama, Python paketleri (.venv), kısayollar' '  the app, its Python packages (.venv), the shortcuts') -ForegroundColor DarkGray
Write-Host ''
if (-not (Ask (T 'Devam edilsin mi?' 'Continue?') $false)) {
    if (-not $Yes) { Write-Host (T 'İptal edildi.' 'Cancelled.') -ForegroundColor Yellow; exit 0 }
}

# --- where are the projects and settings? -------------------------------------------
$configDir = if ($env:CLIPFORGE_HOME) { $env:CLIPFORGE_HOME } else { Join-Path $env:USERPROFILE '.clipforge' }
$workspace = Join-Path $AppDir 'workspace'
try {
    $cfgFile = Join-Path $configDir 'config.json'
    if (Test-Path -LiteralPath $cfgFile) {
        $cfg = Get-Content -LiteralPath $cfgFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($cfg.workspace_dir) { $workspace = [Environment]::ExpandEnvironmentVariables($cfg.workspace_dir) }
    }
} catch { }
$projects = @()
if (Test-Path -LiteralPath $workspace) {
    $projects = @(Get-ChildItem -LiteralPath $workspace -Directory -Force | Where-Object { $_.Name -notlike '_*' -and $_.Name -notlike '.*' })
}
$deleteWorkspace = $false
if ($projects.Count -gt 0) {
    $gb = Size-Gb $workspace
    Write-Host ''
    Write-Host ((T 'Projeleriniz: {0} proje, {1} GB  ({2})' 'Your projects: {0} projects, {1} GB  ({2})') -f $projects.Count, $gb, $workspace) -ForegroundColor White
    foreach ($p in ($projects | Select-Object -First 8)) { Write-Host "  - $($p.Name)" -ForegroundColor DarkGray }
    if ($Yes) { $deleteWorkspace = [bool]$DeleteProjects }
    else { $deleteWorkspace = Ask (T 'Projeler ve kesilmiş klipler de SİLİNSİN mi? (geri alınamaz)' 'Also DELETE these projects and rendered clips? (cannot be undone)') $false }
}
$deleteSettings = $false
if ((Test-Path -LiteralPath $configDir) -and -not $Yes) {
    $deleteSettings = Ask ((T 'Ayarlar ve öğrenilmiş başlık tarzınız ({0}) silinsin mi?' 'Delete your settings and learned title style ({0})?') -f $configDir) $false
}

# Downloaded AI models: Whisper (Hugging Face cache) and the local LLM (Ollama).
$hfHub = if ($env:HF_HOME) { Join-Path $env:HF_HOME 'hub' } else { Join-Path $env:USERPROFILE '.cache\huggingface\hub' }
$whisper = @()
if (Test-Path -LiteralPath $hfHub) {
    $whisper = @(Get-ChildItem -LiteralPath $hfHub -Directory | Where-Object { $_.Name -like 'models--*faster-whisper*' -or $_.Name -like 'models--mlx-community--whisper*' })
}
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue | Select-Object -First 1)
$ollamaExe = if ($ollama) { $ollama.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
$llmModels = @()
if (Test-Path -LiteralPath $ollamaExe) {
    try {
        $list = & $ollamaExe list 2>$null
        $llmModels = @($list | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] } | Where-Object { $_ -like 'qwen3.5:*' })
    } catch { }
}
$deleteModels = $false
if (($whisper.Count + $llmModels.Count) -gt 0 -and -not $Yes) {
    $names = @($whisper | ForEach-Object { $_.Name -replace '^models--', '' -replace '--', '/' }) + $llmModels
    Write-Host ''
    Write-Host ((T 'İndirilmiş yapay zekâ modelleri: {0}' 'Downloaded AI models: {0}') -f ($names -join ', ')) -ForegroundColor White
    $deleteModels = Ask (T 'Bu modeller silinsin mi? (başka programlar kullanmıyorsa yer açar)' 'Delete these models? (frees space if no other program uses them)') $false
}

# --- remove --------------------------------------------------------------------------
Write-Host ''
# Stop a running ClipForge (its Python runs from this folder's .venv).
$venvPy = Join-Path $AppDir '.venv\Scripts\python.exe'
try {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.ExecutablePath -eq $venvPy -or $_.CommandLine -like "*$AppDir*cli.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 500
} catch { }

$installedTools = @()
try {
    $state = Get-Content -LiteralPath (Join-Path $AppDir '.install-state.json') -Raw | ConvertFrom-Json
    $installedTools = @($state.installed_tools)
} catch { }

$shortcutDirs = if ($ShortcutDir) { @($ShortcutDir) } else { @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) }
$shell = New-Object -ComObject WScript.Shell
foreach ($dir in $shortcutDirs) {
    $lnk = Join-Path $dir 'ClipForge.lnk'
    if (Test-Path -LiteralPath $lnk) {
        $target = $shell.CreateShortcut($lnk).TargetPath
        if ($target -like "$AppDir\*") { Remove-Item -LiteralPath $lnk -Force; Ok ((T 'Kısayol silindi: {0}' 'Removed shortcut: {0}') -f $lnk) }
    }
}
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipForge'
if (-not $ShortcutDir -and (Test-Path $key)) {
    $loc = (Get-ItemProperty -Path $key -ErrorAction SilentlyContinue).InstallLocation
    if ($loc -eq $AppDir) { Remove-Item -Path $key -Recurse -Force; Ok (T 'Uygulamalar listesinden çıkarıldı' 'Removed from Apps & features') }
}

if ($deleteModels) {
    foreach ($d in $whisper) { Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction SilentlyContinue }
    foreach ($m in $llmModels) { & $ollamaExe rm $m | Out-Null }
    Ok (T 'Yapay zekâ modelleri silindi' 'AI models deleted')
}
if ($deleteSettings) {
    Remove-Item -LiteralPath $configDir -Recurse -Force -ErrorAction SilentlyContinue
    Ok ((T 'Ayarlar silindi: {0}' 'Settings deleted: {0}') -f $configDir)
}

$workspaceInside = ([IO.Path]::GetFullPath($workspace).TrimEnd('\') -like "$AppDir\*")
if ($deleteWorkspace -and (Test-Path -LiteralPath $workspace)) {
    Remove-Item -LiteralPath $workspace -Recurse -Force
    Ok ((T 'Projeler silindi: {0}' 'Projects deleted: {0}') -f $workspace)
}
$keepInside = $workspaceInside -and (Test-Path -LiteralPath $workspace) -and $projects.Count -gt 0
if ($keepInside) {
    # Keep the workspace folder, remove everything else.
    Get-ChildItem -LiteralPath $AppDir -Force | Where-Object { $_.FullName -ne [IO.Path]::GetFullPath($workspace).TrimEnd('\') } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
} else {
    Remove-Item -LiteralPath $AppDir -Recurse -Force -ErrorAction SilentlyContinue
}
$left = @()
if (Test-Path -LiteralPath $AppDir) { $left = @(Get-ChildItem -LiteralPath $AppDir -Force | Where-Object { -not $keepInside -or $_.Name -ne 'workspace' }) }
if ($left.Count -gt 0) {
    Write-Host ((T '  !   Bazı dosyalar silinemedi (kullanımda olabilir): {0}' '  !   Some files could not be removed (maybe in use): {0}') -f $AppDir) -ForegroundColor Yellow
} else {
    Ok ((T 'ClipForge kaldırıldı: {0}' 'ClipForge removed: {0}') -f $AppDir)
}
if ($keepInside) { Write-Host ((T 'Projeleriniz duruyor: {0}' 'Your projects are still here: {0}') -f $workspace) -ForegroundColor Cyan }

if ($installedTools.Count -gt 0) {
    Write-Host ''
    Write-Host (T 'Kurulumun eklediği araçlar yerinde bırakıldı. İsterseniz şöyle kaldırabilirsiniz:' 'Tools the installer added were left installed. To remove them too:') -ForegroundColor DarkGray
    foreach ($id in $installedTools) { Write-Host "  winget uninstall --id $id -e" -ForegroundColor DarkGray }
}
Write-Host ''
if (-not $Yes -and -not $env:CLIPFORGE_NO_PAUSE) { Read-Host (T 'Kapatmak için Enter' 'Press Enter to close') | Out-Null }
exit 0
