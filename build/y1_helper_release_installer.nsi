RequestExecutionLevel admin

!define APPNAME "Y1 Helper"
!define COMPANYNAME "Y1"
!define VERSION "0.9.0"

; Set install directory to %LOCALAPPDATA%\Y1 Helper
InstallDir "$LOCALAPPDATA\${APPNAME}"

!include "MUI2.nsh"
!define MUI_ICON "..\icon.ico"
!define MUI_UNICON "..\icon.ico"

!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "WinMessages.nsh"

SetCompressor /SOLID lzma

Name "Y1 Helper Release Installer"
OutFile "installer.exe"
ShowInstDetails show

; Define curl executable path
!define CURL_EXE "$TEMP\curl.exe"
!define CURL_DLL "$TEMP\libcurl-x64.dll"

; Modern UI settings
!define MUI_WELCOMEPAGE_TITLE "Welcome to Y1 Helper"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of Y1 Helper.$\r$\n$\r$\nY1 Helper is a comprehensive tool for device management and firmware operations."
!define MUI_WELCOMEPAGE_BGCOLOR "FFFFFF"
!define MUI_WELCOMEPAGE_TEXT_COLOR "000000"

!define MUI_DIRECTORYPAGE_TEXT_TOP "Setup will install Y1 Helper in the following folder.$\r$\n$\r$\nTo install in a different folder, click Browse and select another folder. Click Next to continue."
!define MUI_DIRECTORYPAGE_BGCOLOR "FFFFFF"
!define MUI_DIRECTORYPAGE_TEXT_COLOR "000000"

!define MUI_INSTFILESPAGE_FINISHHEADER_TEXT "Installation Complete"
!define MUI_INSTFILESPAGE_FINISHHEADER_SUBTEXT "Y1 Helper has been successfully installed on your computer."
!define MUI_INSTFILESPAGE_BGCOLOR "FFFFFF"
!define MUI_INSTFILESPAGE_TEXT_COLOR "000000"

!define MUI_FINISHPAGE_TITLE "Installation Complete"
!define MUI_FINISHPAGE_TEXT "Y1 Helper has been successfully installed on your computer.$\r$\n$\r$\nClick Finish to close this wizard."
!define MUI_FINISHPAGE_BGCOLOR "FFFFFF"
!define MUI_FINISHPAGE_TEXT_COLOR "000000"

; Function to kill ADB and Python processes
Function KillADBAndPythonProcesses
    DetailPrint "Checking for running ADB and Python processes..."
    
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
    
    ; Additional wait to ensure processes are fully terminated
    Sleep 1000
FunctionEnd

; Function to show process termination confirmation
Function ShowProcessTerminationDialog
    MessageBox MB_YESNO|MB_ICONQUESTION "Y1 Helper needs to terminate any running ADB and Python processes to prevent installation conflicts.$\r$\n$\r$\nThis will close any active Python applications and ADB connections. Please save your work before continuing.$\r$\n$\r$\nDo you want to continue?" IDYES continue_install IDNO abort_install
    
    abort_install:
        Abort "Installation cancelled by user"
    
    continue_install:
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
    
    ; Download localization files
    DetailPrint "Downloading localization.py from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\localization.py" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/localization.py"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded localization.py from GitHub"
    ${Else}
        DetailPrint "Failed to download localization.py from GitHub, using local fallback"
        ${If} ${FileExists} "..\localization.py"
            File "..\localization.py"
        ${EndIf}
    ${EndIf}
    
    DetailPrint "Downloading invite_url.txt from GitHub..."
    nsExec::ExecToLog '"${CURL_EXE}" -k -L -o "$INSTDIR\invite_url.txt" "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/invite_url.txt"'
    Pop $0
    ${If} $0 == 0
        DetailPrint "Successfully downloaded invite_url.txt from GitHub"
    ${Else}
        DetailPrint "Failed to download invite_url.txt from GitHub, using local fallback"
        ${If} ${FileExists} "..\invite_url.txt"
            File "..\invite_url.txt"
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
    ${If} ${FileExists} "..\localization.py"
        File "..\localization.py"
    ${EndIf}
    ${If} ${FileExists} "..\invite_url.txt"
        File "..\invite_url.txt"
    ${EndIf}
FunctionEnd

; MUI Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; MUI Languages
!insertmacro MUI_LANGUAGE "English"

; Finish page options
!define MUI_FINISHPAGE_RUN "$INSTDIR\assets\python\python.exe"
!define MUI_FINISHPAGE_RUN_PARAMETERS "$INSTDIR\y1_helper.py"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Y1 Helper"
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"

Section "Install" SEC01
    ; Show process termination confirmation before installation
    Call ShowProcessTerminationDialog
    
    ; Extract curl.exe and libcurl-x64.dll to temp directory
    SetOutPath "$TEMP"
    File "curl.exe"
    File "libcurl-x64.dll"
    
    SetOutPath "$INSTDIR"
    
    ; Download files from GitHub first (prioritizing y1_helper.py and config.ini)
    Call DownloadFromGitHub
    
    ; Install assets directory (only if it doesn't exist or is incomplete)
    SetOutPath "$INSTDIR\assets"
    File /r "..\assets\*.*"
    
    ; Install .old directory recursively (all old versions 0.5.0 to 0.8.0)
    SetOutPath "$INSTDIR\.old"
    File /r "..\.old\*.*"
    
    ; Install .cache directory with selective file copying (only working_tokens.json, exclude others)
    DetailPrint "Installing .cache directory with selective files..."
    SetOutPath "$INSTDIR\.cache"
    ${If} ${FileExists} "..\.cache\working_tokens.json"
        File "..\.cache\working_tokens.json"
        DetailPrint "Installed working_tokens.json from .cache directory"
    ${Else}
        DetailPrint "working_tokens.json not found in .cache directory"
    ${EndIf}
    
    ; Explicitly exclude cache files that should not be installed
    DetailPrint "Excluding apps_cache.json, index.xml, last_update.txt, slide_manifest.xml from .cache"
    
    ; Create necessary subdirectories in assets (with nonfatal to handle empty dirs)
    ; Create empty ROM directory (ROM files will be populated by the app)
    SetOutPath "$INSTDIR\assets\rom"
    ; Don't include ROM files - let the app populate them
    SetOutPath "$INSTDIR\assets\sqldrivers"
    File /nonfatal /r "..\assets\sqldrivers\*.*"
    SetOutPath "$INSTDIR\assets\settings"
    File /nonfatal /r "..\assets\settings\*.*"
    SetOutPath "$INSTDIR\assets\python"
    File /nonfatal /r "..\assets\python\*.*"
    SetOutPath "$INSTDIR\assets\notebooks"
    File /nonfatal /r "..\assets\notebooks\*.*"
    SetOutPath "$INSTDIR\assets\imageformats"
    File /nonfatal /r "..\assets\imageformats\*.*"
    SetOutPath "$INSTDIR\assets\config"
    File /nonfatal /r "..\assets\config\*.*"
    SetOutPath "$INSTDIR\assets\codecs"
    File /nonfatal /r "..\assets\codecs\*.*"

    ; Install MTK Driver if not present
    IfFileExists "C:\Program Files\MediaTek\SP Driver\unins000.exe" +4 0
    DetailPrint "MediaTek Driver not found, installing..."
    SetOutPath "$INSTDIR"
    File "MTK Driver Setup.exe"
    ExecWait '"$INSTDIR\MTK Driver Setup.exe" /S'
    Delete "$INSTDIR\MTK Driver Setup.exe"
    DetailPrint "MediaTek Driver installation complete, installer removed"

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Install Shortcut Files"
    SetOutPath "$INSTDIR"
    
    ; Embed .lnk files directly in installer payload
    File "Y1 Helper.lnk"
    File "Y1 Helper (run old versions).lnk"
SectionEnd

Section "Shortcuts"
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
    
    DetailPrint "Creating Uninstall shortcut..."
    CreateShortCut "$SMPROGRAMS\Y1 Helper\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\icon.ico" 0 "" "" "$INSTDIR"
    
    ; Copy Desktop shortcut from embedded installer payload
    DetailPrint "Copying Desktop shortcut..."
    CopyFiles "$INSTDIR\Y1 Helper.lnk" "$DESKTOP\Y1 Helper.lnk"
    
    DetailPrint "All 6 shortcuts created successfully"
SectionEnd

Section "Uninstall"
    Delete "$DESKTOP\Y1 Helper.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Y1 Helper.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Y1 Helper (run old versions).lnk"
    Delete "$SMPROGRAMS\Y1 Helper\SP Flash Tool.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Rockbox Utility.lnk"
    Delete "$SMPROGRAMS\Y1 Helper\Uninstall.lnk"
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
    ; Remove all other files in root
    Delete "$INSTDIR\*.*"
    RMDir "$SMPROGRAMS\Y1 Helper"
    RMDir "$INSTDIR"
SectionEnd

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "Y1 Helper Release Installer"
VIAddVersionKey "CompanyName" "Team Slide"
VIAddVersionKey "FileDescription" "Y1 Helper Release Installer (Runtime v.${VERSION})"
VIAddVersionKey "LegalCopyright" "Team Slide"
VIAddVersionKey "FileVersion" "${VERSION}.0"

# To build the installer, run:
#   "C:\Program Files (x86)\NSIS\makensis.exe" build\y1_helper_release_installer.nsi 