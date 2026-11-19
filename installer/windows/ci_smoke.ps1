<#
Installer smoke test (1.2.56), run by .github/workflows/installer.yml on a clean Windows runner:

  1. silent install of SharkyClips-Setup-<v>.exe (per user, no admin), timed
  2. checks: files, Start menu shortcut, Apps & features entry (name, version, icon)
  3. starts SharkyClips.exe like a double-click, waits for the UI on 127.0.0.1:8000-8010,
     checks the page, an asset, /api/app (version, install kind) and /api/setup
  4. cli.py doctor --no-fix (bundled Python + FFmpeg, Whisper smoke test on the CPU)
  5. cli.py selftest (a tiny generated clip rendered on the CPU)
  6. silent uninstall: app folder, shortcut and Apps entry gone, settings + projects kept

    powershell -File installer/windows/ci_smoke.ps1 -Setup installer/dist/SharkyClips-Setup-1.2.56.exe
#>
param(
    [Parameter(Mandatory = $true)][string]$Setup,
    [string]$Report = "installer-smoke.json"
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$app = Join-Path $env:LOCALAPPDATA 'Programs\SharkyClips'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B0C8E52-3F0B-4C5E-9E7B-5A1C2D7E8F31}_is1'
$startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'SharkyClips.lnk'
$version = (Get-Content (Join-Path $PSScriptRoot '..\..\VERSION') -Raw).Trim()
$result = [ordered]@{ version = $version; setup_mb = [math]::Round((Get-Item $Setup).Length / 1MB, 1) }

function Step([string]$t) { Write-Host "`n=== $t" -ForegroundColor Cyan }
function Fail([string]$t) { Write-Host "FAIL: $t" -ForegroundColor Red; $result.failed = $t; Save; exit 1 }
function Save { $result | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 $Report }
function Check([bool]$ok, [string]$what) { if (-not $ok) { Fail $what } else { Write-Host "ok  $what" -ForegroundColor Green } }

Step "install (silent)"
if (Test-Path $app) { Fail "the app folder exists before installing: not a clean runner" }
$t0 = Get-Date
$p = Start-Process -FilePath $Setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/LOG=install.log' -Wait -PassThru
$result.install_seconds = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
Check ($p.ExitCode -eq 0) "installer exit code 0 (was $($p.ExitCode))"
Write-Host "install took $($result.install_seconds) s"
$result.installed_mb = [math]::Round(((Get-ChildItem $app -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 0)

Step "files, shortcut, Apps & features"
foreach ($f in 'SharkyClips.exe', 'python\pythonw.exe', 'python\python.exe', 'ffmpeg\bin\ffmpeg.exe', 'backend\cli.py', 'frontend\dist\index.html', 'install.json', 'unins000.exe') {
    Check (Test-Path (Join-Path $app $f)) "installed $f"
}
Check (-not (Test-Path (Join-Path $app 'backend\sharkyclips\google_client.json'))) "no Google client in the install"
Check (Test-Path $startMenu) "Start menu shortcut"
$entry = Get-ItemProperty $key -ErrorAction SilentlyContinue
Check ($null -ne $entry) "Apps & features entry"
Check ($entry.DisplayVersion -eq $version) "Apps & features version $($entry.DisplayVersion)"
Check ($entry.DisplayName -eq 'SharkyClips') "Apps & features name"
Check ([string]$entry.DisplayIcon -like '*SharkyClips.exe*') "Apps & features icon"

Step "launch like a double-click"
$t1 = Get-Date
Start-Process -FilePath (Join-Path $app 'SharkyClips.exe') -WorkingDirectory $app
$port = $null
for ($i = 0; $i -lt 240 -and -not $port; $i++) {
    Start-Sleep -Milliseconds 750
    foreach ($pt in 8000..8010) {
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$pt/api/app" -TimeoutSec 2
            if ($r.version) { $port = $pt; break }
        } catch { }
    }
}
if (-not $port) {
    Get-Content (Join-Path $env:USERPROFILE '.sharkyclips\logs\sharkyclips.log') -ErrorAction SilentlyContinue | Select-Object -Last 60
    Get-Content (Join-Path $env:USERPROFILE '.sharkyclips\logs\launcher.log') -ErrorAction SilentlyContinue | Select-Object -Last 20
    Fail "the UI didn't answer within 180 s"
}
$result.start_seconds = [math]::Round(((Get-Date) - $t1).TotalSeconds, 1)
Write-Host "UI on port $port after $($result.start_seconds) s"
$state = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/app"
Check ($state.version -eq $version) "running version $($state.version)"
Check ($state.install_kind -eq 'installer') "install kind '$($state.install_kind)'"
$page = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing
Check ($page.StatusCode -eq 200 -and $page.Content -match 'id="root"') "UI page loads"
$asset = [regex]::Match($page.Content, '/assets/[^"]+\.js').Value
Check ($asset -ne '') "UI page references its script"
Check ((Invoke-WebRequest -Uri "http://127.0.0.1:$port$asset" -UseBasicParsing).StatusCode -eq 200) "UI script loads ($asset)"
$planRaw = (Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/setup" -UseBasicParsing -TimeoutSec 120).Content
Write-Host $planRaw
$plan = $planRaw | ConvertFrom-Json
Check (@($plan.items | Where-Object { $_.id -eq 'whisper' }).Count -eq 1) "first-run download plan lists Whisper"
$result.setup_plan = @($plan.items | ForEach-Object { "$($_.id)=$($_.size_mb)MB" + $(if ($_.present) { '(present)' } else { '' }) })
$ws = Join-Path ([Environment]::GetFolderPath('MyVideos')) 'SharkyClips'
Check (Test-Path $ws) "projects folder created in Videos ($ws)"

$py = Join-Path $app 'python\python.exe'
$cli = Join-Path $app 'backend\cli.py'
Step "doctor (bundled Python + FFmpeg, CPU smoke test)"
$t2 = Get-Date
& $py $cli doctor --no-fix
$doctorCode = $LASTEXITCODE
$result.doctor_seconds = [math]::Round(((Get-Date) - $t2).TotalSeconds, 1)
Check ($doctorCode -eq 0) "doctor passes"

Step "selftest (tiny clip rendered on the CPU)"
$out = & $py $cli selftest
$out | Write-Host
Check ($LASTEXITCODE -eq 0) "selftest render"
$result.selftest = ($out | Select-Object -Last 1 | ConvertFrom-Json)

Step "diagnostic report has no user name"
$diag = (& $py $cli diag --quick) -join "`n"
Check ($diag -match 'diagnostic report') "diag prints a report"
Check (-not ($diag -match [regex]::Escape($env:USERPROFILE))) "diag hides the user folder"

Step "close SharkyClips"
Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($app + '\', [StringComparison]::OrdinalIgnoreCase) } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Step "uninstall (silent: keeps settings and projects)"
New-Item -ItemType File -Force (Join-Path $ws 'keep-me.txt') | Out-Null
$t3 = Get-Date
Start-Process -FilePath (Join-Path $app 'unins000.exe') -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait
# the uninstaller hands over to a copy of itself in %TEMP%: wait until the files are gone
for ($i = 0; $i -lt 120 -and (Test-Path (Join-Path $app 'unins000.exe')); $i++) { Start-Sleep -Seconds 1 }
Start-Sleep -Seconds 2
$result.uninstall_seconds = [math]::Round(((Get-Date) - $t3).TotalSeconds, 1)
Check (-not (Test-Path (Join-Path $app 'python'))) "app files removed"
Check (-not (Test-Path (Join-Path $app 'SharkyClips.exe'))) "launcher removed"
Check (-not (Test-Path $startMenu)) "Start menu shortcut removed"
Check (-not (Test-Path $key)) "Apps & features entry removed"
Check (Test-Path (Join-Path $env:USERPROFILE '.sharkyclips\config.json')) "settings kept"
Check (Test-Path (Join-Path $ws 'keep-me.txt')) "projects kept"

$result.ok = $true
Save
Write-Host "`nInstaller smoke test passed:" -ForegroundColor Green
$result | ConvertTo-Json -Depth 5
