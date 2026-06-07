[Setup]
AppName=Volt
AppVersion=0.5.0

AppPublisher=Volt Open Source
DefaultDirName={autopf}\Volt
DefaultGroupName=Volt
OutputBaseFilename=Volt_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
OutputDir=..\dist

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "runatstartup"; Description: "Launch Volt at startup"; GroupDescription: "Startup Options";

[Files]
Source: "..\dist\Volt\Volt.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\Volt\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Volt"; Filename: "{app}\Volt.exe"
Name: "{autodesktop}\Volt"; Filename: "{app}\Volt.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Volt"; ValueData: """{app}\Volt.exe"""; Tasks: runatstartup

[Run]
Filename: "{app}\Volt.exe"; Description: "{cm:LaunchProgram,Volt}"; Flags: nowait postinstall skipifsilent
