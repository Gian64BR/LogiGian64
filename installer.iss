[Setup]
AppId={{9678E6A2-68BD-4BA1-B9B3-463C3E234872}
AppName=LogiGian64
AppVersion=0.2.0
AppPublisher=Gian64BR
AppPublisherURL=https://github.com/Gian64BR/LogiGian64
DefaultDirName={localappdata}\Programs\LogiGian64
DefaultGroupName=LogiGian64
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=dist
OutputBaseFilename=LogiGian64-Setup
SetupIconFile=assets\logigian64.ico
UninstallDisplayIcon={app}\LogiGian64.exe
LicenseFile=LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "dist\LogiGian64.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs
Source: "dist\LogiGian64-0.2-source.zip"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\LogiGian64"; Filename: "{app}\LogiGian64.exe"
Name: "{autodesktop}\LogiGian64"; Filename: "{app}\LogiGian64.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LogiGian64.exe"; Description: "Abrir LogiGian64"; Flags: nowait postinstall skipifsilent
