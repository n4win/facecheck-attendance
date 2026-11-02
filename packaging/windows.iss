; Build: iscc /DAppVersion=1.0.0 packaging\windows.iss
[Setup]
AppName=FaceCheck Attendance
AppVersion={#AppVersion}
AppPublisher=n4win
; Program Files is deliberate: OpenCV on Windows cannot open model files on paths with
; non-ASCII characters, which a per-user install under a Thai username would have.
DefaultDirName={autopf}\FaceCheck Attendance
PrivilegesRequired=admin
DefaultGroupName=FaceCheck Attendance
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installers
OutputBaseFilename=FaceCheck-Attendance-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\FaceCheckAttendance.exe
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\FaceCheckAttendance\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Icons]
Name: "{group}\FaceCheck Attendance"; Filename: "{app}\FaceCheckAttendance.exe"
Name: "{autodesktop}\FaceCheck Attendance"; Filename: "{app}\FaceCheckAttendance.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FaceCheckAttendance.exe"; Description: "{cm:LaunchProgram,FaceCheck Attendance}"; Flags: nowait postinstall skipifsilent
