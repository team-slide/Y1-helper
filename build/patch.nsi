RequestExecutionLevel admin

!define APPNAME "Y1 Helper"
!define COMPANYNAME "Y1"
!define VERSION "0.8.2"

; Set install directory to %LOCALAPPDATA%\Y1 Helper
InstallDir "$LOCALAPPDATA\${APPNAME}"

!include "MUI2.nsh"
!define MUI_ICON "..\icon.ico"
!define MUI_UNICON "..\icon.ico"

!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "WinMessages.nsh"

SetCompressor /SOLID lzma

Name "Y1 Helper Patch"
OutFile "patch.exe"
ShowInstDetails show

; Define curl executable path
!define CURL_EXE "$TEMP\curl.exe"
!define CURL_DLL "$TEMP\libcurl-x64.dll"

; Function to kill ADB and Python processes
Function KillADBAndPythonProcesses
    DetailPrint "Terminating ADB and Python processes..."
    
    ; Kill ADB processes
    nsExec::ExecToLog 'taskkill /F /IM adb.exe /T'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully terminated ADB processes"
    ${Else}
        DetailPrint "No ADB processes found or already terminated"
    ${EndIf}
    
    ; Kill Python processes
    nsExec::ExecToLog 'taskkill /F /IM python.exe /T'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully terminated Python processes"
    ${Else}
        DetailPrint "No Python processes found or already terminated"
    ${EndIf}
    
    ; Brief wait to ensure processes are fully terminated
    Sleep 500
FunctionEnd

; Function to show quick process termination warning
Function ShowQuickProcessWarning
    MessageBox MB_OK|MB_ICONINFORMATION "Y1 Helper Patch will now terminate any running ADB and Python processes to prevent update conflicts.$\r$\n$\r$\nPlease ensure you have saved your work in any Python applications or ADB sessions.$\r$\n$\r$\nClick OK to continue with the patch."
    Call KillADBAndPythonProcesses
FunctionEnd

; Function to download files from GitHub (primary method)
Function DownloadFromGitHub
    DetailPrint "Downloading files from GitHub master repository..."
    
    SetOutPath "$INSTDIR"
    
    ; Priority 1: Download y1_helper.py and config.ini first
    DetailPrint "Downloading y1_helper.py from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\y1_helper.py" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/y1_helper.py"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded y1_helper.py from GitHub"
    ${Else}
        DetailPrint "Failed to download y1_helper.py from GitHub, using local fallback"
        File "..\y1_helper.py"
    ${EndIf}
    
    DetailPrint "Downloading config.ini from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\config.ini" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/config.ini"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded config.ini from GitHub"
    ${Else}
        DetailPrint "Failed to download config.ini from GitHub, using local fallback"
        ${If} ${FileExists} "..\config.ini"
            File "..\config.ini"
        ${EndIf}
    ${EndIf}
    
    ; Priority 2: Download other core files
    DetailPrint "Downloading old.py from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\old.py" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/old.py"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded old.py from GitHub"
    ${Else}
        DetailPrint "Failed to download old.py from GitHub, using local fallback"
        File "..\old.py"
    ${EndIf}
    
    DetailPrint "Downloading requirements.txt from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\requirements.txt" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/requirements.txt"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded requirements.txt from GitHub"
    ${Else}
        DetailPrint "Failed to download requirements.txt from GitHub, using local fallback"
        File "..\requirements.txt"
    ${EndIf}
    
    DetailPrint "Downloading version.txt from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\version.txt" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/version.txt"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded version.txt from GitHub"
    ${Else}
        DetailPrint "Failed to download version.txt from GitHub, using local fallback"
        ${If} ${FileExists} "..\version.txt"
            File "..\version.txt"
        ${EndIf}
    ${EndIf}
    
    DetailPrint "Downloading branch.txt from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\branch.txt" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/branch.txt"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded branch.txt from GitHub"
    ${Else}
        DetailPrint "Failed to download branch.txt from GitHub, using local fallback"
        ${If} ${FileExists} "..\branch.txt"
            File "..\branch.txt"
        ${EndIf}
    ${EndIf}
    
    ; Priority 3: Download .gitignore
    DetailPrint "Downloading .gitignore from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\.gitignore" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/.gitignore"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded .gitignore from GitHub"
    ${Else}
        DetailPrint "Failed to download .gitignore from GitHub, using local fallback"
        ${If} ${FileExists} "..\.gitignore"
            File "..\.gitignore"
        ${EndIf}
    ${EndIf}
    
    ; Always install local image files (not on GitHub)
    DetailPrint "Installing local image files..."
    File "..\icon.ico"
    File "..\icon.png"
    File "..\ready.png"
    File "..\sleeping.png"
FunctionEnd

; Function to install local files (fallback method)
Function InstallLocalFiles
    DetailPrint "Installing local project files as fallback..."
    
    SetOutPath "$INSTDIR"
    File "..\y1_helper.py"
    File "..\old.py"
    File "..\requirements.txt"
    File "..\icon.ico"
    File "..\icon.png"
    File "..\ready.png"
    File "..\sleeping.png"
    
    ; Try to install optional files if they exist
    ${If} ${FileExists} "..\config.ini"
        File "..\config.ini"
    ${EndIf}
    ${If} ${FileExists} "..\version.txt"
        File "..\version.txt"
    ${EndIf}
    ${If} ${FileExists} "..\branch.txt"
        File "..\branch.txt"
    ${EndIf}
    ${If} ${FileExists} "..\.gitignore"
        File "..\.gitignore"
    ${EndIf}
FunctionEnd

; Function to check if Y1 Helper is properly installed
Function CheckY1HelperInstallation
    ; Check if the standard install directory exists and has the required files
    IfFileExists "$INSTDIR\y1_helper.py" 0 +3
    IfFileExists "$INSTDIR\assets\python\python.exe" 0 +2
    IfFileExists "$INSTDIR\assets\flash_tool.exe" 0 +1
    Goto InstallationOK
    
    ; Check if there's an existing installation in the standard location
    IfFileExists "$LOCALAPPDATA\Y1 Helper\y1_helper.py" 0 +3
    IfFileExists "$LOCALAPPDATA\Y1 Helper\assets\python\python.exe" 0 +2
    IfFileExists "$LOCALAPPDATA\Y1 Helper\assets\flash_tool.exe" 0 +1
    Goto UseExistingInstallLocation
    
    ; No proper installation found, show error dialog
    MessageBox MB_OK|MB_ICONEXCLAMATION "Y1 Helper is not properly installed.$\r$\n$\r$\nPlease run the full installer (installer.exe) first to install Y1 Helper to the standard location.$\r$\n$\r$\nThe patch can only update an existing installation."
    Abort "Installation not found"
    
    UseExistingInstallLocation:
        ; Use the existing installation location
        StrCpy $INSTDIR "$LOCALAPPDATA\Y1 Helper"
        DetailPrint "Using existing installation at: $INSTDIR"
        Goto InstallationOK
    
    InstallationOK:
        DetailPrint "Y1 Helper installation found at: $INSTDIR"
FunctionEnd

; Non-interactive patch installer with progress dialog
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Patch" SEC01
    ; Show quick process termination warning
    Call ShowQuickProcessWarning

    ; Show progress dialog for graceful appearance
    SetDetailsView show
    DetailPrint "Applying patch..."

    ; Always overwrite existing files
    SetOverwrite on
    
    ; Auto-close when complete
    SetAutoClose true

    ; Check if Y1 Helper is properly installed
    Call CheckY1HelperInstallation

    ; Extract curl.exe and libcurl-x64.dll to temp directory
    SetOutPath "$TEMP"
    File "curl.exe"
    File "libcurl-x64.dll"
    
    SetOutPath "$INSTDIR"
    
    ; Download files from GitHub first (prioritizing y1_helper.py and config.ini)
    Call DownloadFromGitHub
    
    ; Note: No MTK Driver installation in patch - assumes it's already installed
    ; Note: Don't touch .old directory in patch - preserve user's old installations
    ; Note: Don't touch assets directory in patch - preserve user's assets
    
    ; Clean up excluded cache files if they exist (preserve working_tokens.json)
    DetailPrint "Cleaning up excluded cache files..."
    Delete "$INSTDIR\.cache\apps_cache.json"
    Delete "$INSTDIR\.cache\index.xml"
    Delete "$INSTDIR\.cache\last_update.txt"
    Delete "$INSTDIR\.cache\slide_manifest.xml"
    
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Install Shortcut Files"
    SetOutPath "$INSTDIR"
    
    ; Embed .lnk files directly in installer payload
    File "Y1 Helper.lnk"
    File "Y1 Helper (run old versions).lnk"
SectionEnd

Section "Launch Y1 Helper"
    ; Wait 3 seconds for graceful appearance before launching
    DetailPrint "Preparing to launch Y1 Helper..."
    Sleep 3000
    DetailPrint "Launching Y1 Helper..."
    Exec '"$INSTDIR\assets\python\python.exe" "$INSTDIR\y1_helper.py"'
SectionEnd

Section "Update Shortcuts"
    SetShellVarContext all
    
    ; Remove ALL existing shortcuts and directory completely (requires admin privileges)
    DetailPrint "Removing existing shortcuts..."
    Delete "$DESKTOP\Y1 Helper.lnk"
    RMDir /r "$SMPROGRAMS\Y1 Helper"
    
    ; Create Start Menu directory fresh
    CreateDirectory "$SMPROGRAMS\Y1 Helper"
    
    ; Copy embedded .lnk files from installer payload to Start Menu
    DetailPrint "Copying Y1 Helper shortcut..."
    CopyFiles "$INSTDIR\Y1 Helper.lnk" "$SMPROGRAMS\Y1 Helper\Y1 Helper.lnk"
    
    DetailPrint "Copying Y1 Helper (run old versions) shortcut..."
    CopyFiles "$INSTDIR\Y1 Helper (run old versions).lnk" "$SMPROGRAMS\Y1 Helper\Y1 Helper (run old versions).lnk"
    
    ; Create SP Flash Tool shortcut
    DetailPrint "Creating SP Flash Tool shortcut..."
    CreateShortCut "$SMPROGRAMS\Y1 Helper\SP Flash Tool.lnk" "$INSTDIR\assets\flash_tool.exe" "" "$INSTDIR\assets\flash_tool.exe" 0 "" "" "$INSTDIR"
    
    ; Create Rockbox Utility shortcut
    DetailPrint "Creating Rockbox Utility shortcut..."
    CreateShortCut "$SMPROGRAMS\Y1 Helper\Rockbox Utility.lnk" "$INSTDIR\assets\RockboxUtility.exe" "" "$INSTDIR\assets\RockboxUtility.exe" 0 "" "" "$INSTDIR"
    
    ; Create Uninstall shortcut
    DetailPrint "Creating Uninstall shortcut..."
    CreateShortCut "$SMPROGRAMS\Y1 Helper\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\icon.ico" 0 "" "" "$INSTDIR"
    
    ; Copy Desktop shortcut from embedded installer payload
    DetailPrint "Copying Desktop shortcut..."
    CopyFiles "$INSTDIR\Y1 Helper.lnk" "$DESKTOP\Y1 Helper.lnk"
    
    DetailPrint "All 6 shortcuts created successfully"
SectionEnd

Section "Uninstall"
    ; Remove all shortcuts
    Delete "$DESKTOP\Y1 Helper.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Y1 Helper.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Y1 Helper (run old versions).lnk"
    Delete "$SMPROGRAMS\Y1 Helper\SP Flash Tool.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Rockbox Utility.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Uninstall.lnk"
    
    ; Remove all application files and directories
    RMDir /r "$INSTDIR\assets"
    RMDir /r "$INSTDIR\.old"
    ; Remove .cache directory but preserve working_tokens.json if it exists
    ; Delete specific cache files that should be removed
    Delete "$INSTDIR\.cache\apps_cache.json"
    Delete "$INSTDIR\.cache\index.xml"
    Delete "$INSTDIR\.cache\last_update.txt"
    Delete "$INSTDIR\.cache\slide_manifest.xml"
    ; Remove all other files in cache directory
    Delete "$INSTDIR\.cache\*.*"
    RMDir "$INSTDIR\.cache"
    Delete "$INSTDIR\y1_helper.py"
    Delete "$INSTDIR\old.py"
    Delete "$INSTDIR\config.ini"
    Delete "$INSTDIR\version.txt"
    Delete "$INSTDIR\branch.txt"
    Delete "$INSTDIR\icon.ico"
    Delete "$INSTDIR\icon.png"
    Delete "$INSTDIR\ready.png"
    Delete "$INSTDIR\sleeping.png"
    Delete "$INSTDIR\requirements.txt"
    Delete "$INSTDIR\Uninstall.exe"
    
    ; Remove all other files in root directory
    Delete "$INSTDIR\*.*"
    
    ; Remove Start Menu directory
    RMDir "$SMPROGRAMS\Y1 Helper"
    
    ; Remove installation directory
    RMDir "$INSTDIR"
SectionEnd

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "Y1 Helper Patch"
VIAddVersionKey "CompanyName" "Team Slide"
VIAddVersionKey "FileDescription" "Y1 Helper Patch (Runtime v.${VERSION})"
VIAddVersionKey "LegalCopyright" "Team Slide"
VIAddVersionKey "FileVersion" "${VERSION}.0"

# To build the patch, run:
#   "C:\Program Files (x86)\NSIS\makensis.exe" build\patch.nsi 

; Make installer non-interactive with minimal progress modal
SilentInstall silent
ShowInstDetails show
AutoCloseWindow true 