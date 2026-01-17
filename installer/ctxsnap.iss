; CtxSnap Inno Setup Installer Script
; Build EXE first with PyInstaller so dist\CtxSnap\CtxSnap.exe exists.

#define AppName "CtxSnap"
#define AppVersion "0.1.0"
#define AppPublisher ""
#define AppExeName "CtxSnap.exe"

[Setup]
AppId={{8C7E7A5D-7C6E-4E1F-A8D1-7D27C1C6C9D1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
OutputBaseFilename=CtxSnap_Setup
SetupIconFile=..\assets\icon.ico

[Files]
Source: "..\dist\CtxSnap\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
