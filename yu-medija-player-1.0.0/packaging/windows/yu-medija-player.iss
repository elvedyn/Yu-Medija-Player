; Inno Setup script for Windows — compile with Inno Setup on a Windows machine
; after: pyinstaller --noconfirm yu-medija-player.spec
; (onefile exe already embeds icons, assets, and bundled libmpv DLLs)

#define MyAppName "Yu Medija Player"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "YuMedijaPlayer"
#define MyAppExeName "yu-medija-player.exe"

[Setup]
; Valid GUID (hex only) — do not change once published, or Windows treats it as a new app
AppId={{A7C4E2B1-9F31-4D6A-8C2E-1B2C3D4E5F60}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=yu-medija-player-setup-{#MyAppVersion}
SetupIconFile=..\..\icons\yu-medija-player.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\tools\*"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist recursesubdirs createallsubdirs

; Onedir-style extras (if you switch the spec later) — currently onefile is enough
Source: "..\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Optional helpers next to the exe (user may drop these in dist/ before compiling the installer)
Source: "..\..\dist\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\dist\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\dist\yt-dlp.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Yu Medija Player"; Flags: nowait postinstall skipifsilent
