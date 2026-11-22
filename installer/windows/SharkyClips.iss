; SharkyClips Windows installer (1.2.56). Built by installer/windows/build_installer.py:
;   ISCC /DAppVersion=1.2.56 /DStageDir=<staged app> /DOutDir=<dist> SharkyClips.iss
; Per-user install into %LOCALAPPDATA%\Programs\SharkyClips (no admin), Start menu shortcut,
; optional desktop shortcut, Apps & features entry. Never touches projects or settings: the
; uninstaller asks (default: keep). Works with Inno Setup 6.x and 7.x.

#ifndef AppVersion
  #error AppVersion is required (/DAppVersion=x.y.z)
#endif
#ifndef StageDir
  #error StageDir is required (/DStageDir=...)
#endif
#ifndef OutDir
  #define OutDir "."
#endif

#define AppName "SharkyClips"
#define AppExe "SharkyClips.exe"

[Setup]
; Never change the AppId: updates and the uninstaller find the installed copy through it.
AppId={{6B0C8E52-3F0B-4C5E-9E7B-5A1C2D7E8F31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=SharkyClips
AppPublisherURL=https://github.com/utkualsir/sharkyclips
AppSupportURL=https://github.com/utkualsir/sharkyclips/issues
AppUpdatesURL=https://github.com/utkualsir/sharkyclips/releases
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} setup
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutDir}
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile={#StageDir}\assets\icon\sharkyclips.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
; 1.2.65 "Shark Sign" art (installer/make_icons.py draws them)
WizardImageFile={#SourcePath}wizard.bmp,{#SourcePath}wizard-150.bmp,{#SourcePath}wizard-200.bmp
WizardSmallImageFile={#SourcePath}wizard-small.bmp,{#SourcePath}wizard-small-150.bmp,{#SourcePath}wizard-small-200.bmp
CloseApplications=no
RestartApplications=no
SetupLogging=yes
ShowLanguageDialog=auto
UsePreviousTasks=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "hu"; MessagesFile: "compiler:Languages\Hungarian.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
en.DesktopIcon=Create a desktop shortcut
tr.DesktopIcon=Masaüstüne kısayol oluştur
de.DesktopIcon=Desktop-Verknüpfung erstellen
hu.DesktopIcon=Asztali parancsikon létrehozása
ru.DesktopIcon=Создать ярлык на рабочем столе
en.LaunchNow=Start SharkyClips now
tr.LaunchNow=SharkyClips'i şimdi başlat
de.LaunchNow=SharkyClips jetzt starten
hu.LaunchNow=SharkyClips indítása most
ru.LaunchNow=Запустить SharkyClips
en.Downgrade=A newer SharkyClips (%1) is already installed. This installer has %2.%n%nSharkyClips never goes back to an older version.
tr.Downgrade=Daha yeni bir SharkyClips (%1) zaten kurulu. Bu kurulum dosyası %2 sürümünü içeriyor.%n%nSharkyClips hiçbir zaman eski bir sürüme dönmez.
de.Downgrade=Ein neueres SharkyClips (%1) ist bereits installiert. Dieses Setup enthält %2.%n%nSharkyClips geht nie auf eine ältere Version zurück.
hu.Downgrade=Már telepítve van egy újabb SharkyClips (%1). Ez a telepítő a(z) %2 verziót tartalmazza.%n%nA SharkyClips soha nem tér vissza régebbi verzióra.
ru.Downgrade=Уже установлена более новая версия SharkyClips (%1). Этот установщик содержит %2.%n%nSharkyClips никогда не возвращается к старой версии.
en.AskProjects=Also delete your SharkyClips projects and rendered clips?%n%n%1%n%nThis cannot be undone. Choose No to keep them.
tr.AskProjects=SharkyClips projeleriniz ve hazırlanmış klipleriniz de silinsin mi?%n%n%1%n%nBu geri alınamaz. Saklamak için Hayır'ı seçin.
de.AskProjects=Auch Ihre SharkyClips-Projekte und fertigen Clips löschen?%n%n%1%n%nDas kann nicht rückgängig gemacht werden. Wählen Sie Nein, um sie zu behalten.
hu.AskProjects=Törli a SharkyClips projektjeit és elkészült klipjeit is?%n%n%1%n%nEz nem vonható vissza. A megtartáshoz válassza a Nem lehetőséget.
ru.AskProjects=Удалить также ваши проекты SharkyClips и готовые клипы?%n%n%1%n%nЭто нельзя отменить. Выберите «Нет», чтобы сохранить их.
en.AskSettings=Delete your settings, sign-ins and learned title style?%n%n%1%n%nChoose No to keep them for a later install.
tr.AskSettings=Ayarlarınız, oturum açmalarınız ve öğrenilmiş başlık tarzınız silinsin mi?%n%n%1%n%nSonraki bir kurulum için saklamak üzere Hayır'ı seçin.
de.AskSettings=Ihre Einstellungen, Anmeldungen und Ihren gelernten Titelstil löschen?%n%n%1%n%nWählen Sie Nein, um sie für eine spätere Installation zu behalten.
hu.AskSettings=Törli a beállításait, bejelentkezéseit és a megtanult címstílust?%n%n%1%n%nA megtartáshoz válassza a Nem lehetőséget.
ru.AskSettings=Удалить настройки, входы в аккаунты и выученный стиль заголовков?%n%n%1%n%nВыберите «Нет», чтобы сохранить их.
en.AskModels=Delete the downloaded AI models and tools (Whisper models, GPU libraries, Deno)?%n%nThey can be downloaded again. Ollama is a separate app: remove it in Apps & features if you want.
tr.AskModels=İndirilen yapay zekâ modelleri ve araçlar (Whisper modelleri, GPU kütüphaneleri, Deno) silinsin mi?%n%nTekrar indirilebilirler. Ollama ayrı bir uygulamadır: isterseniz Uygulamalar listesinden kaldırın.
de.AskModels=Die heruntergeladenen KI-Modelle und Werkzeuge (Whisper-Modelle, GPU-Bibliotheken, Deno) löschen?%n%nSie können erneut heruntergeladen werden. Ollama ist eine eigene App.
hu.AskModels=Törli a letöltött MI-modelleket és eszközöket (Whisper-modellek, GPU-könyvtárak, Deno)?%n%nÚjra letölthetők. Az Ollama külön alkalmazás.
ru.AskModels=Удалить загруженные модели ИИ и инструменты (модели Whisper, библиотеки GPU, Deno)?%n%nИх можно скачать снова. Ollama — отдельное приложение.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; Flags: unchecked

[InstallDelete]
; A clean runtime on every update (stale packages / old files never linger). User data is never
; in {app}: settings in %USERPROFILE%\.sharkyclips, projects in Videos\SharkyClips, models in their
; caches, GPU libraries in %LOCALAPPDATA%\SharkyClips\runtime.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\backend"
Type: filesandordirs; Name: "{app}\frontend"
Type: filesandordirs; Name: "{app}\ffmpeg"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchNow}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: RelaunchAfterSilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\backend"
Type: filesandordirs; Name: "{app}\frontend"
Type: filesandordirs; Name: "{app}\ffmpeg"
Type: files; Name: "{app}\updating.flag"
Type: dirifempty; Name: "{app}"

[Code]
var
  PathsLoaded: Boolean;
  PathWorkspace, PathSettings, PathRuntime, PathHf: String;

function RelaunchAfterSilent(): Boolean;
begin
  Result := WizardSilent() and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;

// "1.2.10" -> comparable parts (never a string compare: 1.2.10 > 1.2.9)
function VersionPart(var S: String): Integer;
var
  P: Integer;
begin
  P := Pos('.', S);
  if P = 0 then begin
    Result := StrToIntDef(S, 0);
    S := '';
  end else begin
    Result := StrToIntDef(Copy(S, 1, P - 1), 0);
    S := Copy(S, P + 1, Length(S));
  end;
end;

function CompareVersions(A, B: String): Integer;
var
  I, X, Y: Integer;
begin
  Result := 0;
  for I := 1 to 3 do begin
    X := VersionPart(A);
    Y := VersionPart(B);
    if X > Y then begin Result := 1; exit; end;
    if X < Y then begin Result := -1; exit; end;
  end;
end;

function InstalledVersion(): String;
begin
  Result := '';
  if not RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B0C8E52-3F0B-4C5E-9E7B-5A1C2D7E8F31}_is1',
                             'DisplayVersion', Result) then
    Result := '';
end;

function InitializeSetup(): Boolean;
var
  Old: String;
begin
  Result := True;
  Old := InstalledVersion();
  if (Old <> '') and (CompareVersions(Old, '{#AppVersion}') > 0) and
     (ExpandConstant('{param:ALLOWDOWNGRADE|0}') <> '1') then begin
    SuppressibleMsgBox(FmtMessage(CustomMessage('Downgrade'), [Old, '{#AppVersion}']), mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

// Every process whose exe lies in the install folder (the launcher first, then its Python and
// FFmpeg). By path, never by process tree: the update's own installer was started by SharkyClips'
// server and must survive this. The uninstaller runs from a temporary copy, and is skipped anyway.
procedure KillAppProcesses();
var
  Code: Integer;
  Script: String;
begin
  // The folder goes in as a -File argument (taken literally: a ' in a user name can't break it).
  Script := ExpandConstant('{tmp}\sharkyclips-close.ps1');
  SaveStringToFile(Script,
    'param([string]$AppDir)' + #13#10 +
    '$d = $AppDir.TrimEnd([char]92) + [char]92' + #13#10 +
    '$p = @(Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($d, [StringComparison]::OrdinalIgnoreCase) -and $_.ProcessName -notlike ''unins*'' })' + #13#10 +
    '$p | Where-Object { $_.ProcessName -eq ''SharkyClips'' } | Stop-Process -Force -ErrorAction SilentlyContinue' + #13#10 +
    '$p | Stop-Process -Force -ErrorAction SilentlyContinue' + #13#10, False);
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
       '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + Script + '" "' + ExpandConstant('{app}') + '"',
       '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

// Close a running SharkyClips before its files are replaced. updating.flag tells the launcher
// that its server was closed on purpose (no error window).
procedure StopRunningCopy();
var
  Dir: String;
begin
  Dir := ExpandConstant('{app}');
  SaveStringToFile(Dir + '\updating.flag', GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':'), False);
  KillAppProcesses();
  Sleep(800);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if DirExists(ExpandConstant('{app}')) then
    StopRunningCopy();
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    DeleteFile(ExpandConstant('{app}\updating.flag'));
end;

// ------------------------------------------------------------------ uninstall

procedure LoadPaths();
var
  Code, I, P: Integer;
  Tmp: String;
  Lines: TArrayOfString;
  Key, Val: String;
begin
  if PathsLoaded then exit;
  PathsLoaded := True;
  Tmp := ExpandConstant('{tmp}\sharkyclips-paths.txt');
  // Python knows where the projects really are (config workspace_dir, the migrated git folder ...)
  if Exec(ExpandConstant('{cmd}'), '/C ""' + ExpandConstant('{app}\python\python.exe') + '" "' +
          ExpandConstant('{app}\backend\cli.py') + '" installer-paths > "' + Tmp + '" 2>nul"',
          ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) and LoadStringsFromFile(Tmp, Lines) then begin
    for I := 0 to GetArrayLength(Lines) - 1 do begin
      P := Pos('=', Lines[I]);
      if P > 0 then begin
        Key := Copy(Lines[I], 1, P - 1);
        Val := Trim(Copy(Lines[I], P + 1, Length(Lines[I])));
        if Key = 'workspace' then PathWorkspace := Val;
        if Key = 'settings' then PathSettings := Val;
        if Key = 'runtime' then PathRuntime := Val;
        if Key = 'hf_cache' then PathHf := Val;
      end;
    end;
  end;
  if PathSettings = '' then PathSettings := ExpandConstant('{%USERPROFILE}\.sharkyclips');
  if PathRuntime = '' then PathRuntime := ExpandConstant('{localappdata}\SharkyClips');
end;

function IsSafeToDelete(Dir: String): Boolean;
var
  D: String;
begin
  // Never a drive root, the user folder itself or a Windows folder.
  D := Lowercase(RemoveBackslashUnlessRoot(Dir));
  Result := (Length(D) > 10) and (D <> Lowercase(ExpandConstant('{%USERPROFILE}'))) and
            (Pos(Lowercase(ExpandConstant('{win}')), D) <> 1) and DirExists(Dir);
end;

procedure DeleteWhisperModels();
var
  F: TFindRec;
begin
  if (PathHf = '') or not DirExists(PathHf) then exit;
  if FindFirst(PathHf + '\models--*faster-whisper*', F) then begin
    try
      repeat
        if (F.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          DelTree(PathHf + '\' + F.Name, True, True, True);
      until not FindNext(F);
    finally
      FindClose(F);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DelProjects, DelSettings, DelModels: Boolean;
begin
  if CurUninstallStep = usUninstall then begin
    KillAppProcesses();
    // A silent uninstall (/SILENT, /VERYSILENT: the CI test, scripts) never asks and keeps everything.
    if UninstallSilent() then exit;
    LoadPaths();
    DelProjects := (PathWorkspace <> '') and DirExists(PathWorkspace) and
      (SuppressibleMsgBox(FmtMessage(CustomMessage('AskProjects'), [PathWorkspace]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES);
    DelSettings := DirExists(PathSettings) and
      (SuppressibleMsgBox(FmtMessage(CustomMessage('AskSettings'), [PathSettings]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES);
    DelModels := (DirExists(PathRuntime) or ((PathHf <> '') and DirExists(PathHf))) and
      (SuppressibleMsgBox(CustomMessage('AskModels'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES);
    if DelProjects and IsSafeToDelete(PathWorkspace) then DelTree(PathWorkspace, True, True, True);
    if DelSettings and IsSafeToDelete(PathSettings) then DelTree(PathSettings, True, True, True);
    if DelModels then begin
      if IsSafeToDelete(PathRuntime) then DelTree(PathRuntime, True, True, True);
      DeleteWhisperModels();
    end;
  end;
end;
