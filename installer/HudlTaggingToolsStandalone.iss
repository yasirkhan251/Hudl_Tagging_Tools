#define MyAppName "Hudl Tagging Tools"
#define MyAppVersion "1.0.0"
#define MyPublisher "Yasir Khan"

[Setup]
AppId={{9F4AAB23-4A4D-4CB9-9B68-4A2E0F00A610}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
DefaultDirName={autopf}\Hudl Tagging Tools
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=HudlTaggingToolsSetup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayIcon={app}\HudlTaggingTools.exe
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\package\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Hudl Tagging Tools"; Filename: "{app}\HudlTaggingTools.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Hudl Tagging Tools"; Filename: "{app}\HudlTaggingTools.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HudlTaggingTools.exe"; Description: "Launch Hudl Tagging Tools"; Flags: postinstall nowait skipifsilent
