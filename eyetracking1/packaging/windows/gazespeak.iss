#ifndef MyAppName
  #define MyAppName "GazeSpeak Desktop"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "0.4.0"
#endif
#ifndef MyAppPublisher
  #define MyAppPublisher "GazeSpeak"
#endif
#ifndef MyDistDir
  #define MyDistDir "..\..\dist\GazeSpeak Desktop"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\..\release"
#endif

[Setup]
AppId={{F9F5FB1A-1A1A-4EC9-B5D8-5A1E87A4B541}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
OutputDir={#MyOutputDir}
OutputBaseFilename=GazeSpeak-{#MyAppVersion}-Windows-Setup
UninstallDisplayIcon={app}\GazeSpeak Desktop.exe
PrivilegesRequired=admin
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\GazeSpeak Desktop.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\GazeSpeak Desktop.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GazeSpeak Desktop.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
