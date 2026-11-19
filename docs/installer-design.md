# One-click Windows installer - design and decision log

<!-- REPORT-TR -->

## 1. Goal

A normal streamer installs SharkyClips like any other app: download one file, double-click, Next,
done. No Python, no console windows, no `install.bat`, no manual steps. Heavy optional parts are
downloaded inside the app on the first run, picked for the user's hardware.

## 2. Options considered

| Option | Verdict |
| --- | --- |
| **Inno Setup** + embedded Python + native launcher | **Chosen.** Free, 25+ years old, per-user install without admin (`PrivilegesRequired=lowest`), LZMA2 solid compression, real "Apps & features" entry, silent mode (`/VERYSILENT`) for CI and the updater, a scriptable uninstaller (Pascal) for the "keep my projects?" questions. Preinstalled on GitHub's `windows-latest` runners. |
| WiX / MSI | Per-user MSI is possible but awkward (ICE rules, per-machine defaults), much more XML for the same result, and the uninstall questions need a custom action DLL. |
| MSIX | Rejected: an MSIX can't be installed at all without a trusted signature (sideloading an unsigned MSIX is blocked), the app container breaks our own subprocess / Playwright / Ollama model, and `%LOCALAPPDATA%` writes are virtualised. |
| PyInstaller / Nuitka one-folder | Rejected: freezing faster-whisper / CTranslate2, onnxruntime, sherpa-onnx, OpenCV, Playwright and numba is fragile, every release can break on a hidden import, antivirus tools flag PyInstaller boot loaders often, and SharkyClips runs `sys.executable -m sharkyclips.smoke` and `pip` (GPU libraries) which a frozen app can't do. |
| Briefcase | Builds an MSI with WiX underneath; same MSI drawbacks and less control over the Python layout. |

**Why an embedded Python and not a frozen app:** the app keeps running exactly the code the git
installs run (same `backend/`, same `frontend/dist`, same `VERSION`), so a bug is the same bug in
both and every existing test covers the installer build too. `config.REPO_ROOT` resolves to the
install folder because the installed folder has the same layout as the repository.

## 3. What is in the installer (CPU-complete)

```
%LOCALAPPDATA%\Programs\SharkyClips\
  SharkyClips.exe          native launcher (C#, .NET Framework 4.8 - part of every Windows 10/11)
  install.json             {"kind": "installer", "version": ...}: tells the app it runs as an installed copy
  VERSION  CHANGELOG.md  LICENSE  THIRD-PARTY-NOTICES.txt
  backend\cli.py  backend\sharkyclips\...       (no tests)
  frontend\dist\...                             (the built UI)
  assets\icon\sharkyclips.ico   docs\google-verification.md
  python\                  python.org embeddable Python 3.12.10 (SHA-256 pinned) + Lib\site-packages
                           with every CPU dependency of backend/requirements.txt, plus pip
  ffmpeg\bin\ffmpeg.exe ffprobe.exe   FFmpeg 9.0.2 "essentials" (gyan.dev build, SHA-256 pinned)
```

Not in the installer (downloaded on the first run, see section 5): NVIDIA CUDA libraries, Whisper
models, Ollama + the LLM, Deno (yt-dlp's JavaScript runtime for YouTube), and the on-demand voice /
cover models (they keep downloading on first use, as before).

User data never lives in the install folder:

| What | Where | On update | On uninstall |
| --- | --- | --- | --- |
| settings, logins, learned style | `%USERPROFILE%\.sharkyclips` (unchanged) | kept | asked, default keep |
| projects (new installs) | `%USERPROFILE%\Videos\SharkyClips` (`workspace_dir`, written on first start) | kept | asked, default keep |
| Whisper models | Hugging Face cache (unchanged, so existing users keep theirs) | kept | asked, default keep |
| LLM models | Ollama's own folder (unchanged) | kept | asked, default keep (Ollama itself is a separate app) |
| GPU libraries, Deno | `%LOCALAPPDATA%\SharkyClips\runtime` | kept | asked together with the models |

## 4. Launcher (`installer/windows/launcher/SharkyClips.cs`)

* Windows-subsystem exe (no console), compiled in CI with the `csc.exe` that ships with Windows
  (no Visual Studio, no extra SDK). Icon + version resource from `VERSION`.
* Single instance: a named mutex; a second double-click just runs `cli.py launch` again, which
  opens the running server in the browser (existing `instance.py` logic).
* Starts `python\pythonw.exe backend\cli.py launch --tray` hidden; the existing Python side does the
  splash page, tray icon, port choice, supervisor and restart-after-update.
* Output goes to `%USERPROFILE%\.sharkyclips\logs\launcher.log`. If Python exits with an error (or
  can't start at all), the launcher shows an error window with the last log lines, "Copy
  diagnostic info" (runs `cli.py diag`, which is passed through `redact.py`: no tokens, no e-mail
  addresses, no user name in paths) and "Open log folder".

## 5. First-run downloads (`backend/sharkyclips/components.py`, UI step in the onboarding)

The onboarding (already there: language, content, performance, YouTube) gets a "Downloads" step,
and Settings > Downloads shows the same list later. Components:

| Component | When it is picked | Size (approx.) | Source + check |
| --- | --- | --- | --- |
| Whisper model (`small` on Light / CPU, `large-v3-turbo` on a GPU) | always | 0.5-1.6 GB | Hugging Face (Systran repos), SHA-256 of every file compared with the repo's LFS hash |
| Whisper `tiny` (doctor / quick checks) | always | 75 MB | same |
| NVIDIA CUDA libraries (cuBLAS, cuDNN 9) | NVIDIA GPU with >= 4 GB VRAM | ~1.2 GB | PyPI wheels, SHA-256 from PyPI's JSON API, then `pip install --no-deps --target` |
| Ollama + LLM model (`qwen3.5:9b`, `:4b` on weak PCs) | PCs that aren't "tiny" (Light preset keeps template titles on very low RAM) | 1.9 GB + 3-6 GB | Ollama's GitHub release (asset SHA-256), model via Ollama (digest-checked layers) |
| Deno | always (YouTube downloads) | 43 MB | Deno's GitHub release, SHA-256 pinned |

Downloads resume (HTTP `Range`, `.part` files), are verified before use, show bytes, speed and time
left, and can be cancelled. Already present parts (a migrating user's Ollama, cached models) are
detected and skipped. After this step everything works offline.

## 6. Existing users (install.bat / git checkout)

* The git workflow is untouched: no `install.json` = "git mode", the updater keeps using
  `git merge --ff-only <release tag>`.
* The installer finds an old copy (the `HKCU\...\Uninstall\SharkyClips` entry of `install.ps1`, or
  `%USERPROFILE%\SharkyClips\.git`). On the first start of the installed app (`migrate.py`):
  * settings already live in `~/.sharkyclips` and are simply used;
  * if `workspace_dir` isn't set, it is set to the old `<checkout>\workspace`: projects stay where
    they are, nothing is moved or copied, nothing can be lost;
  * the old Desktop / Start menu `SharkyClips.lnk` that point into the old checkout are pointed at
    the new launcher; the old Apps & features entry is renamed "SharkyClips (old git copy)";
  * the old checkout itself is never deleted (the user may still develop there).

## 7. Updates for installer users (`updater.py`, installer mode)

1. `GET https://api.github.com/repos/utkualsir/sharkyclips/releases/latest` (only the official
   repo, https only). The tag must be `v<semver>` and strictly higher than the running version.
2. The release must carry `SharkyClips-Setup-<v>.exe` and `SharkyClips-Setup-<v>.exe.sha256`.
3. Download with resume to `%LOCALAPPDATA%\SharkyClips\updates`, then check the SHA-256 against the
   `.sha256` file **and** GitHub's own asset digest. If Authenticode-signed, the signature must be
   valid; with `update_require_signed` an unsigned file is refused.
4. When no job is queued or running, the installer runs silently
   (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /RELAUNCH=1`), closes SharkyClips, installs over it
   and starts it again. The installer itself refuses to install an older version over a newer one.

## 8. Code signing

An unsigned installer works, but Microsoft Defender SmartScreen shows "Windows protected your PC"
for new downloads until the file builds reputation. The README documents **More info -> Run anyway**
(with an illustration, `docs/screenshots/smartscreen.png`). Options, cheapest first:

| Option | Cost | Fit for SharkyClips | Notes |
| --- | --- | --- | --- |
| **SignPath Foundation** (signpath.org) | free for OSS | **best, but needs a public repo** | Certificate is issued to "SignPath Foundation" (shown as publisher). Conditions: OSI license (MIT: ok), public source, no proprietary parts, at least one release, fully automated build from the repository (our GitHub Actions job), MFA for every team member on GitHub and SignPath, a published code-signing policy page. |
| Certum "Open Source Code Signing" (certum.eu) | ~EUR 30-70 / year + card reader or SimplySign cloud | works with a private repo | Individual OV certificate in your own name; identity check with ID card. SmartScreen reputation still grows slowly (OV, not EV). |
| Azure Artifact Signing (ex Trusted Signing) | USD 9.99 / month | probably not available | Public onboarding for individuals has been limited to some countries (US/CA, at times EU/UK) and organisations with 3+ years of history; check the current terms. |
| EV certificate (DigiCert, Sectigo ...) | USD 250-500+ / year | overkill | Needs a registered company. |

How it plugs in (already prepared): the CI job builds `SharkyClips-Setup-<v>.exe`; a signing step
goes between "Build the installer" and "Smoke test" (SignPath: `signpath/github-action-submit-signing-request`;
Certum/Azure: `signtool sign /fd sha256 /tr <timestamp-url> /td sha256 ...`). The launcher
`SharkyClips.exe` should be signed too (sign the stage before ISCC, or let SignPath sign both
with its "deep signing" of the Inno payload). The updater already checks the Authenticode
signature of a downloaded installer: a signed file with a broken signature is refused, and the
setting `update_require_signed: true` refuses unsigned ones (turn it on once releases are signed).

## 9. CI (`.github/workflows/installer.yml`)

On every `v*` tag (and by hand): build on `windows-latest`, install silently into a clean user
folder, start the launcher, wait for the UI, run `cli.py doctor --no-fix`, render a tiny sample
clip on the CPU (`cli.py installer-smoke`), uninstall silently, check the folder is gone and the
projects are kept, then attach `SharkyClips-Setup-<v>.exe` + `.sha256` to the GitHub Release.

## 10. Decision log

(Unattended run, 2026-11-19. Every decision taken without the owner is listed here.)

1. **Inno Setup** over WiX / MSIX / PyInstaller (section 2). Script works with Inno Setup 6.x (the
   runner's) and 7.x.
2. **Python 3.12.10 embeddable** (last 3.12 binary release from python.org; the dev venv and CI use
   3.12). SHA-256 `4acbed6d...a3c3`, checked against python.org's SPDX file.
3. **FFmpeg 9.0.2 essentials** (gyan.dev via its GitHub mirror `GyanD/codexffmpeg`, SHA-256 pinned
   from the release's asset digest): has libass, freetype, x264/x265, NVENC/QSV/AMF.
4. **Projects default for new installs: `%USERPROFILE%\Videos\SharkyClips`.** Not inside the install
   folder (an uninstall or update must never touch projects), and not `%USERPROFILE%\SharkyClips`
   (that is where old git installs live).
5. **Launcher in C# compiled by the Windows `csc.exe`**: zero extra toolchain, tiny exe, WinForms
   for the error window.
6. **The heavy optional parts are downloaded by the app, not by the installer**: the installer
   stays one file that works offline, and the app can show real progress / resume / checksums.
7. **GPU libraries go to `%LOCALAPPDATA%\SharkyClips\runtime\gpu`**, outside the install folder,
   so an update (which replaces `python\` completely to drop stale packages) keeps them.
8. **Uninstall asks three questions, default "keep"** (projects, settings, downloaded models and
   tools); a silent uninstall keeps everything.
9. **Update = the full new installer** (simple, verifiable). Delta updates are a possible later
   optimisation.
