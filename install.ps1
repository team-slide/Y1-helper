# Y1 Helper - Complete PowerShell Installation Script
# This script handles everything: preparation, installation, and setup

# Script parameters (must be first)
param(
    [switch]$Force,
    [switch]$SkipPython,
    [switch]$SkipMTK,
    [switch]$Silent
)

# Set console colors and encoding
$Host.UI.RawUI.WindowTitle = "Y1 Helper - Installation"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Define all helper functions first (before any other code)
function Write-Header {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n[STEP] $Message" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Message)
    Write-Host "SUCCESS: $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "INFO: $Message" -ForegroundColor Blue
}

function Write-Warning {
    param([string]$Message)
    Write-Host "WARNING: $Message" -ForegroundColor Magenta
}

# Check for administrator privileges
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Auto-elevate script if not running as administrator
function Request-AdministratorPrivileges {
    if (-not (Test-Administrator)) {
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Y1 Helper - Installation" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "This script requires administrator privileges to install Y1 Helper"
        Write-Host "Attempting to elevate privileges..."
        
        try {
            # Get the current script path
            $scriptPath = $MyInvocation.MyCommand.Path
            if (-not $scriptPath) {
                $scriptPath = $PSCommandPath
            }
            if (-not $scriptPath) {
                $scriptPath = Join-Path $PWD "install.ps1"
            }
            
            # Build arguments for the elevated process
            $arguments = @()
            if ($Force) { $arguments += "-Force" }
            if ($SkipPython) { $arguments += "-SkipPython" }
            if ($SkipMTK) { $arguments += "-SkipMTK" }
            if ($Silent) { $arguments += "-Silent" }
            
            $argumentString = $arguments -join " "
            
            Write-Host "Restarting script with elevated privileges..."
            Write-Host "UAC prompt will appear - please click 'Yes' to continue"
            
            # Start the script with elevated privileges
            Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$scriptPath`" $argumentString" -Verb RunAs -Wait
            
            # Exit the current non-elevated process
            exit 0
            
        } catch {
            Write-Host "Failed to elevate privileges automatically"
            Write-Host "Please run PowerShell as Administrator and try again"
            Write-Host "Right-click on PowerShell and select 'Run as administrator'"
            Write-Host "Then navigate to this folder and run: .\install.ps1"
            Read-Host "Press Enter to exit"
            exit 1
        }
    }
}

# Get latest Python version
function Get-LatestPythonVersion {
    Write-Step "Checking for latest Python version (3.13+)..."
    
    try {
        $web = New-Object System.Net.WebClient
        $ftpContent = $web.DownloadString('https://www.python.org/ftp/python/')
        
        $versions = @()
        $lines = $ftpContent -split "`n"
        foreach ($line in $lines) {
            if ($line -match '3\.(\d+)\.(\d+)/') {
                $major = [int]$matches[1]
                $minor = [int]$matches[2]
                
                # Only consider versions 3.13 and newer
                if ($major -eq 3 -and $minor -ge 13) {
                    $versions += "3.$major.$minor"
                }
            }
        }
        
        if ($versions.Count -gt 0) {
            $latestVersion = ($versions | Sort-Object -Descending)[0]
            Write-Success "Latest Python version found: $latestVersion"
            return $latestVersion
        }
        
        Write-Info "No Python 3.13+ version found, using fallback version"
        return "3.13.5"
        
    } catch {
        Write-Error "Error checking Python.org: $($_.Exception.Message)"
        Write-Info "Using fallback version"
        return "3.13.5"
    }
}

# Enhanced Python detection with version checking
function Test-PythonInstalled {
    Write-Step "Checking for Python installation..."
    
    $pythonCommands = @("python", "py", "python3")
    $foundPython = $null
    $foundVersion = $null
    
    foreach ($cmd in $pythonCommands) {
        try {
            Write-Info "Trying command: $cmd"
            $pythonVersion = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                $foundPython = $cmd
                $foundVersion = $pythonVersion
                Write-Success "Python found: $pythonVersion (using $cmd)"
                
                # Check if version is 3.13 or higher
                if ($pythonVersion -match 'Python (\d+)\.(\d+)\.(\d+)') {
                    $major = [int]$matches[1]
                    $minor = [int]$matches[2]
                    $patch = [int]$matches[3]
                    
                    if ($major -eq 3 -and $minor -ge 13) {
                        Write-Success "Python version is compatible (3.$minor.$patch)"
                        return @{ Command = $cmd; Version = $pythonVersion; Compatible = $true }
                    } else {
                        Write-Warning "Python version $major.$minor.$patch found, but 3.13+ is recommended"
                        return @{ Command = $cmd; Version = $pythonVersion; Compatible = $false }
                    }
                }
                break
            }
        } catch {
            Write-Info "Command $cmd not found, trying next..."
            continue
        }
    }
    
    Write-Info "Python not found in PATH, checking common installation locations..."
    
    # Check common Python installation locations
    $commonPaths = @(
        "C:\Python*",
        "C:\Program Files\Python*",
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python*",
        "C:\Program Files (x86)\Python*"
    )
    
    foreach ($pathPattern in $commonPaths) {
        $pythonDirs = Get-ChildItem -Path $pathPattern -Directory -ErrorAction SilentlyContinue
        foreach ($pythonDir in $pythonDirs) {
            $pythonExe = Join-Path $pythonDir.FullName "python.exe"
            if (Test-Path $pythonExe) {
                Write-Success "Found Python installation at: $($pythonDir.FullName)"
                
                # Check version
                try {
                    $versionOutput = & $pythonExe --version 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "Python version: $versionOutput"
                        
                        if ($versionOutput -match 'Python (\d+)\.(\d+)\.(\d+)') {
                            $major = [int]$matches[1]
                            $minor = [int]$matches[2]
                            $patch = [int]$matches[3]
                            
                            if ($major -eq 3 -and $minor -ge 13) {
                                return @{ Command = $pythonExe; Version = $versionOutput; Compatible = $true }
                            } else {
                                Write-Warning "Python version $major.$minor.$patch found, but 3.13+ is recommended"
                                return @{ Command = $pythonExe; Version = $versionOutput; Compatible = $false }
                            }
                        }
                    }
                } catch {
                    Write-Info "Could not determine version for: $pythonExe"
                }
            }
        }
    }
    
    return $null
}

# Install Python using winget
function Install-PythonWinget {
    Write-Step "Trying winget installation..."
    
    try {
        # Check if winget is available
        $wingetVersion = winget --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Info "Winget not available, skipping winget installation"
            return $false
        }
        
        Write-Info "Winget version: $wingetVersion"
        
        # Check available Python versions
        $wingetOutput = winget search Python.Python 2>&1
        $pythonVersions = $wingetOutput | Select-String "Python\.Python\.(\d+\.\d+)"
        
        # Try Python 3.14 first
        if ($wingetOutput -match "3\.14") {
            Write-Info "Found Python 3.14 in winget, installing..."
            winget install Python.Python.3.14 --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Python 3.14 installed via winget"
                return $true
            }
        }
        
        # Try Python 3.13
        if ($wingetOutput -match "3\.13") {
            Write-Info "Found Python 3.13 in winget, installing..."
            winget install Python.Python.3.13 --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Python 3.13 installed via winget"
                return $true
            }
        }
        
        # Try Python 3.12 as fallback
        Write-Info "Trying Python 3.12 as fallback..."
        winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python 3.12 installed via winget"
            return $true
        }
        
        Write-Error "Winget installation failed"
        return $false
        
    } catch {
        Write-Error "Winget not available or failed: $($_.Exception.Message)"
        return $false
    }
}

# Install Python using Windows Installer
function Install-PythonWindowsInstaller {
    param([string]$Version)
    
    Write-Step "Installing Python $Version using Windows Installer..."
    
    try {
        $installerUrl = "https://www.python.org/ftp/python/$Version/python-$Version-amd64.exe"
        $installerPath = "$env:TEMP\python-installer.exe"
        
        Write-Info "Downloading Python installer from: $installerUrl"
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        
        if (Test-Path $installerPath) {
            Write-Info "Installing Python silently..."
            
            $installArgs = @(
                "/quiet",
                "InstallAllUsers=1",
                "PrependPath=1",
                "Include_test=0",
                "Include_pip=1",
                "Include_doc=0",
                "Include_dev=0",
                "Include_launcher=1",
                "AssociateFiles=1",
                "Shortcuts=1",
                "TargetDir=C:\Python$Version"
            )
            
            Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait
            
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Python $Version installed successfully"
                Remove-Item $installerPath -Force
                return $true
            } else {
                Write-Error "Python installation failed with exit code: $LASTEXITCODE"
            }
        } else {
            Write-Error "Failed to download Python installer"
        }
        
        if (Test-Path $installerPath) {
            Remove-Item $installerPath -Force
        }
        
        return $false
        
    } catch {
        Write-Error "Error installing Python: $($_.Exception.Message)"
        return $false
    }
}

# Enhanced Python PATH configuration
function Set-PythonPath {
    param([string]$Version)
    
    Write-Step "Configuring Python PATH environment variables..."
    
    try {
        # Extract major.minor version
        $versionParts = $Version -split '\.'
        $major = $versionParts[0]
        $minor = $versionParts[1]
        
        # Set Python paths
        $pythonDir = "C:\Python$Version"
        $pythonScripts = "$pythonDir\Scripts"
        
        # Check if Python is installed in expected location
        if (-not (Test-Path "$pythonDir\python.exe")) {
            Write-Info "Checking alternative Python locations..."
            
            $alternativePaths = @(
                "C:\Program Files\Python$major$minor",
                "$env:LOCALAPPDATA\Programs\Python\Python$major$minor",
                "C:\Program Files (x86)\Python$major$minor"
            )
            
            foreach ($path in $alternativePaths) {
                if (Test-Path "$path\python.exe") {
                    $pythonDir = $path
                    $pythonScripts = "$pythonDir\Scripts"
                    Write-Info "Found Python in: $pythonDir"
                    break
                }
            }
        }
        
        # Configure System PATH
        Write-Info "Configuring system PATH..."
        $systemPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
        
        if ($systemPath -notlike "*$pythonDir*") {
            $newSystemPath = "$pythonDir;$pythonScripts;$systemPath"
            [Environment]::SetEnvironmentVariable("PATH", $newSystemPath, "Machine")
            Write-Success "System PATH updated successfully"
        } else {
            Write-Info "Python already in system PATH"
        }
        
        # Configure User PATH
        Write-Info "Configuring user PATH..."
        $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
        
        if ($userPath -notlike "*$pythonDir*") {
            $newUserPath = "$pythonDir;$pythonScripts;$userPath"
            [Environment]::SetEnvironmentVariable("PATH", $newUserPath, "User")
            Write-Success "User PATH updated successfully"
        } else {
            Write-Info "Python already in user PATH"
        }
        
        # Set PYTHONPATH
        Write-Info "Setting PYTHONPATH..."
        $pythonPath = "$pythonDir\Lib\site-packages"
        [Environment]::SetEnvironmentVariable("PYTHONPATH", $pythonPath, "Machine")
        Write-Success "PYTHONPATH set successfully"
        
        # Set PYTHONHOME
        Write-Info "Setting PYTHONHOME..."
        [Environment]::SetEnvironmentVariable("PYTHONHOME", $pythonDir, "Machine")
        Write-Success "PYTHONHOME set successfully"
        
        # Refresh current session PATH
        $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User")
        
        return $true
        
    } catch {
        Write-Error "Error configuring Python PATH: $($_.Exception.Message)"
        return $false
    }
}

# Enhanced pip installation and verification
function Install-EnsurePip {
    Write-Step "Ensuring pip is installed and up to date..."
    
    try {
        # Try different Python commands
        $pythonCommands = @("python", "py", "python3")
        $success = $false
        
        foreach ($pythonCmd in $pythonCommands) {
            try {
                Write-Info "Checking pip with: $pythonCmd"
                
                # Check if pip is available
                $pipCheck = & $pythonCmd -m pip --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "pip found: $pipCheck"
                    
                    # Upgrade pip to latest version
                    Write-Info "Upgrading pip to latest version..."
                    & $pythonCmd -m pip install --upgrade pip
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "pip upgraded successfully"
                        $success = $true
                        break
                    }
                } else {
                    Write-Info "pip not found, installing..."
                    
                    # Download get-pip.py
                    $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
                    $getPipPath = "$env:TEMP\get-pip.py"
                    
                    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
                    
                    if (Test-Path $getPipPath) {
                        & $pythonCmd $getPipPath
                        if ($LASTEXITCODE -eq 0) {
                            Write-Success "pip installed successfully"
                            $success = $true
                            break
                        }
                    }
                    
                    if (Test-Path $getPipPath) {
                        Remove-Item $getPipPath -Force
                    }
                }
            } catch {
                Write-Info "Failed with $pythonCmd, trying next..."
                continue
            }
        }
        
        if ($success) {
            return $true
        } else {
            Write-Error "Failed to install/upgrade pip with any Python command"
            return $false
        }
        
    } catch {
        Write-Error "Error ensuring pip: $($_.Exception.Message)"
        return $false
    }
}

# Enhanced Python dependencies installation
function Install-PythonDependencies {
    Write-Step "Installing/Updating Python dependencies..."
    
    try {
        # First ensure pip is available
        if (-not (Install-EnsurePip)) {
            Write-Error "Failed to ensure pip is available"
            return $false
        }
        
        # Get script directory more reliably
        $scriptDir = $PSScriptRoot
        if (-not $scriptDir) {
            $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        }
        if (-not $scriptDir) {
            $scriptDir = Get-Location
        }
        
        $requirementsFile = Join-Path $scriptDir "requirements.txt"
        
        if (Test-Path $requirementsFile) {
            Write-Info "Installing/updating packages from requirements.txt..."
            
            # Try different Python commands
            $pythonCommands = @("python", "py", "python3")
            $pipCommands = @("pip", "pip3")
            
            $success = $false
            
            foreach ($pythonCmd in $pythonCommands) {
                foreach ($pipCmd in $pipCommands) {
                    try {
                        Write-Info "Trying: $pythonCmd -m $pipCmd install --upgrade -r $requirementsFile"
                        & $pythonCmd -m $pipCmd install --upgrade -r $requirementsFile
                        if ($LASTEXITCODE -eq 0) {
                            Write-Success "Python dependencies installed/updated successfully using $pythonCmd"
                            $success = $true
                            break
                        }
                    } catch {
                        Write-Info "Failed with $pythonCmd -m $pipCmd, trying next..."
                        continue
                    }
                }
                if ($success) { break }
            }
            
            if ($success) {
                # Verify key dependencies
                Write-Info "Verifying key dependencies..."
                $keyDeps = @("Pillow", "numpy", "requests")
                
                foreach ($dep in $keyDeps) {
                    try {
                        $checkResult = & python -c "import $dep; print('$dep version:', $dep.__version__)" 2>&1
                        if ($LASTEXITCODE -eq 0) {
                            Write-Success "$checkResult"
                        } else {
                            Write-Warning "Could not verify $dep"
                        }
                    } catch {
                        Write-Warning "Could not verify $dep"
                    }
                }
                
                return $true
            } else {
                Write-Error "Failed to install Python dependencies with any Python command"
                return $false
            }
        } else {
            Write-Error "requirements.txt not found"
            return $false
        }
        
    } catch {
        Write-Error "Error installing dependencies: $($_.Exception.Message)"
        return $false
    }
}

# Install MTK Driver
function Install-MTKDriver {
    Write-Step "Installing MTK Driver..."
    
    try {
        # Get script directory more reliably
        $scriptDir = $PSScriptRoot
        if (-not $scriptDir) {
            $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        }
        if (-not $scriptDir) {
            $scriptDir = Get-Location
        }
        
        $mtkInstaller = Join-Path $scriptDir "MTK Driver Setup.exe"
        
        if (Test-Path $mtkInstaller) {
            Write-Info "Found MTK Driver Setup.exe: $mtkInstaller"
            Write-Info "Starting MTK Driver installation..."
            
            # Check if MTK Driver is already installed
            $mtkDrivers = Get-WmiObject -Class Win32_PnPSignedDriver | Where-Object { $_.DeviceName -like "*MTK*" -or $_.DeviceName -like "*MediaTek*" }
            if ($mtkDrivers) {
                Write-Info "MTK drivers detected in system:"
                foreach ($driver in $mtkDrivers) {
                    Write-Info "  - $($driver.DeviceName)"
                }
                $response = Read-Host "MTK drivers appear to be installed. Reinstall anyway? (y/N)"
                if ($response -ne "y" -and $response -ne "Y") {
                    Write-Info "MTK Driver installation skipped"
                    return $true
                }
            }
            
            Start-Process -FilePath $mtkInstaller -Wait
            Write-Success "MTK Driver installation completed"
            return $true
        } else {
            Write-Warning "MTK Driver Setup.exe not found at: $mtkInstaller"
            Write-Info "You may need to download MTK drivers separately for SP Flash Tool"
            return $false
        }
        
    } catch {
        Write-Error "Error installing MTK Driver: $($_.Exception.Message)"
        return $false
    }
}

# Install Y1 Helper to Program Files
function Install-Y1Helper {
    Write-Step "Installing Y1 Helper to Program Files..."
    
    try {
        # Get script directory more reliably
        $scriptDir = $PSScriptRoot
        if (-not $scriptDir) {
            $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        }
        if (-not $scriptDir) {
            $scriptDir = Get-Location
        }
        
        Write-Info "Script directory: $scriptDir"
        $installDir = "C:\Program Files\Y1 Helper"
        
        # Always remove existing installation without prompting
        if (Test-Path $installDir) {
            Write-Info "Removing existing installation..."
            Remove-Item $installDir -Recurse -Force
        }
        
        # Create installation directory
        New-Item -ItemType Directory -Path $installDir -Force | Out-Null
        
        # Copy all files
        Write-Info "Copying files to Program Files..."
        Copy-Item -Path "$scriptDir\*" -Destination $installDir -Recurse -Force
        
        Write-Success "Y1 Helper installed to: $installDir"
        return $true
        
    } catch {
        Write-Error "Error installing Y1 Helper: $($_.Exception.Message)"
        return $false
    }
}

# Create shortcuts
function New-Y1HelperShortcuts {
    Write-Step "Creating shortcuts..."
    
    try {
        $installDir = "C:\Program Files\Y1 Helper"
        $y1HelperExe = Join-Path $installDir "y1_helper.py"
        $iconPath = Join-Path $installDir "icon.ico"
        
        # Remove existing shortcuts first
        Write-Info "Removing existing shortcuts..."
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        $desktopShortcut = Join-Path $desktopPath "Y1 Helper.lnk"
        if (Test-Path $desktopShortcut) {
            Remove-Item $desktopShortcut -Force
            Write-Info "Removed existing desktop shortcut"
        }
        
        $startMenuPath = [Environment]::GetFolderPath("StartMenu")
        $startMenuDir = Join-Path $startMenuPath "Programs\Y1 Helper"
        if (Test-Path $startMenuDir) {
            Remove-Item $startMenuDir -Recurse -Force
            Write-Info "Removed existing start menu shortcuts"
        }
        
        # Create desktop shortcut
        Write-Info "Creating desktop shortcut..."
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($desktopShortcut)
        $Shortcut.TargetPath = "python"
        $Shortcut.Arguments = "`"$y1HelperExe`""
        $Shortcut.WorkingDirectory = $installDir
        $Shortcut.Description = "Y1 Helper - Device Management Tool"
        if (Test-Path $iconPath) {
            $Shortcut.IconLocation = $iconPath
        }
        $Shortcut.Save()
        
        # Create start menu shortcut
        Write-Info "Creating start menu shortcut..."
        if (-not (Test-Path $startMenuDir)) {
            New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null
        }
        
        $startMenuShortcut = Join-Path $startMenuDir "Y1 Helper.lnk"
        $Shortcut = $WshShell.CreateShortcut($startMenuShortcut)
        $Shortcut.TargetPath = "python"
        $Shortcut.Arguments = "`"$y1HelperExe`""
        $Shortcut.WorkingDirectory = $installDir
        $Shortcut.Description = "Y1 Helper - Device Management Tool"
        if (Test-Path $iconPath) {
            $Shortcut.IconLocation = $iconPath
        }
        $Shortcut.Save()
        
        Write-Success "Shortcuts created successfully"
        Write-Info "Desktop shortcut: $desktopShortcut"
        Write-Info "Start menu shortcut: $startMenuShortcut"
        return $true
        
    } catch {
        Write-Error "Error creating shortcuts: $($_.Exception.Message)"
        return $false
    }
}

# Create uninstaller
function New-Y1HelperUninstaller {
    Write-Step "Creating uninstaller..."
    
    try {
        $installDir = "C:\Program Files\Y1 Helper"
        $uninstallerPath = Join-Path $installDir "uninstall.ps1"
        
        $uninstallerContent = @"
# Y1 Helper Uninstaller
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Y1 Helper - Uninstaller" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "Uninstalling Y1 Helper..." -ForegroundColor Yellow

# Remove shortcuts
Write-Host "Removing shortcuts..." -ForegroundColor Blue
`$desktopPath = [Environment]::GetFolderPath("Desktop")
`$desktopShortcut = Join-Path `$desktopPath "Y1 Helper.lnk"
if (Test-Path `$desktopShortcut) {
    Remove-Item `$desktopShortcut -Force
    Write-Host "✓ Desktop shortcut removed" -ForegroundColor Green
} else {
    Write-Host "Desktop shortcut not found" -ForegroundColor Gray
}

`$startMenuPath = [Environment]::GetFolderPath("StartMenu")
`$startMenuDir = Join-Path `$startMenuPath "Programs\Y1 Helper"
if (Test-Path `$startMenuDir) {
    Remove-Item `$startMenuDir -Recurse -Force
    Write-Host "✓ Start menu shortcuts removed" -ForegroundColor Green
} else {
    Write-Host "Start menu shortcuts not found" -ForegroundColor Gray
}

# Remove installation directory
Write-Host "Removing installation directory..." -ForegroundColor Blue
`$installDir = "C:\Program Files\Y1 Helper"
if (Test-Path `$installDir) {
    Remove-Item `$installDir -Recurse -Force
    Write-Host "✓ Installation directory removed" -ForegroundColor Green
} else {
    Write-Host "Installation directory not found" -ForegroundColor Gray
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Y1 Helper has been uninstalled successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Read-Host "Press Enter to exit"
"@
        
        Set-Content -Path $uninstallerPath -Value $uninstallerContent
        Write-Success "Uninstaller created at: $uninstallerPath"
        return $true
        
    } catch {
        Write-Error "Error creating uninstaller: $($_.Exception.Message)"
        return $false
    }
}

# Check SP Flash Tool availability
function Test-SPFlashTool {
    Write-Step "Checking SP Flash Tool availability..."
    
    try {
        $scriptDir = $PSScriptRoot
        if (-not $scriptDir) {
            $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        }
        if (-not $scriptDir) {
            $scriptDir = Get-Location
        }
        
        $flashToolExe = Join-Path $scriptDir "flash_tool.exe"
        
        if (Test-Path $flashToolExe) {
            Write-Success "SP Flash Tool found: $flashToolExe"
            return $true
        } else {
            Write-Warning "SP Flash Tool (flash_tool.exe) not found"
            Write-Info "SP Flash Tool is required for device flashing operations"
            return $false
        }
        
    } catch {
        Write-Error "Error checking SP Flash Tool: $($_.Exception.Message)"
        return $false
    }
}

# Detect Python launchers
function Get-PythonLaunchers {
    $launchers = @{}
    
    # Check for project's WinPython installation
    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    if (-not $scriptDir) {
        $scriptDir = Get-Location
    }
    
    # Check if WinPython is already extracted
    $winPythonDir = Join-Path $scriptDir "WPy64-31350"
    $winPythonExe = Join-Path $winPythonDir "WinPython Interpreter.exe"
    
    if (Test-Path $winPythonExe) {
        try {
            & $winPythonExe --version > $null 2>&1
            if ($LASTEXITCODE -eq 0) {
                $launchers["Project"] = $winPythonExe
                Write-Host "Found WinPython Interpreter: $winPythonExe"
            }
        } catch {}
    } else {
        # Check if py.exe exists and extract it if needed
        $projectPyExe = Join-Path $scriptDir "py.exe"
        if (Test-Path $projectPyExe) {
            Write-Host "Found project py.exe, extracting WinPython..."
            try {
                # Extract WinPython
                & $projectPyExe /auto
                if ($LASTEXITCODE -eq 0) {
                    # Wait a moment for extraction to complete
                    Start-Sleep -Seconds 3
                    if (Test-Path $winPythonExe) {
                        try {
                            & $winPythonExe --version > $null 2>&1
                            if ($LASTEXITCODE -eq 0) {
                                $launchers["Project"] = $winPythonExe
                                Write-Host "Successfully extracted and found WinPython Interpreter: $winPythonExe"
                            }
                        } catch {}
                    }
                }
            } catch {
                Write-Host "Failed to extract WinPython: $($_.Exception.Message)"
            }
        }
    }
    
    # Check for system py
    try {
        & py --version > $null 2>&1
        if ($LASTEXITCODE -eq 0) {
            $launchers["System"] = "py"
            Write-Host "Found system py launcher"
        }
    } catch {}
    
    # Check for system python
    try {
        & python --version > $null 2>&1
        if ($LASTEXITCODE -eq 0) {
            $launchers["SystemPython"] = "python"
            Write-Host "Found system python"
        }
    } catch {}
    
    if ($launchers.Count -eq 0) {
        Write-Host "ERROR: No Python launchers found."
        return $null
    }
    
    return $launchers
}

# Install Python dependencies for all available launchers
function Install-PythonDependencies {
    Write-Step "Installing/Updating Python dependencies for all launchers..."
    try {
        $launchers = Get-PythonLaunchers
        if (-not $launchers) { Write-Host "Skipping dependency installation: No Python launchers found."; return $false }
        
        $successCount = 0
        foreach ($launcherType in $launchers.Keys) {
            $launcher = $launchers[$launcherType]
                            Write-Host "Installing dependencies for ${launcherType} launcher: $launcher"
            
            try {
                # Ensure pip is available
                Write-Host "Ensuring pip is installed and up to date for $launcherType..."
                try {
                    & $launcher -m pip --version
                    if ($LASTEXITCODE -ne 0) {
                        Write-Host "pip not found for $launcherType, attempting to install..."
                        $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
                        $getPipPath = "$env:TEMP\get-pip-$launcherType.py"
                        Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
                        & $launcher $getPipPath
                        Remove-Item $getPipPath -Force
                    }
                    Write-Host "Upgrading pip for $launcherType..."
                    & $launcher -m pip install --upgrade pip
                } catch { Write-Host "Failed to ensure pip for $launcherType." }
                
                # Install requirements
                $scriptDir = $PSScriptRoot; if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
                if (-not $scriptDir) { $scriptDir = Get-Location }
                $requirementsFile = Join-Path $scriptDir "requirements.txt"
                if (Test-Path $requirementsFile) {
                    Write-Host "Installing/updating packages from requirements.txt for $launcherType..."
                    & $launcher -m pip install --upgrade -r $requirementsFile
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "Dependencies installed/updated successfully for $launcherType."
                        # Verify key dependencies
                        $verify = & $launcher -c "import PIL; import numpy; import requests; print('All imports OK')" 2>&1
                        if ($LASTEXITCODE -eq 0) {
                            Write-Host "${launcherType}: $verify"
                            $successCount++
                        } else {
                            Write-Host "WARNING: Could not verify all dependencies for ${launcherType}. Output:"; Write-Host $verify
                        }
                    } else {
                        Write-Host "ERROR: pip install failed for $launcherType."
                    }
                } else {
                    Write-Host "requirements.txt not found for $launcherType."
                }
            } catch {
                Write-Host "Error installing dependencies for ${launcherType}: $($_.Exception.Message)"
            }
        }
        
        if ($successCount -gt 0) {
            Write-Host "Successfully installed dependencies for $successCount launcher(s)."
            return $true
        } else {
            Write-Host "Failed to install dependencies for any launcher."
            return $false
        }
    } catch {
        Write-Host "Error installing dependencies: $($_.Exception.Message)"
        return $false
    }
}

# Launch Y1 Helper using available launchers
function Start-Y1Helper {
    Write-Step "Launching Y1 Helper..."
    try {
        $installDir = "C:\Program Files\Y1 Helper"
        $y1HelperExe = Join-Path $installDir "y1_helper.py"
        $launchers = Get-PythonLaunchers
        if (-not $launchers) { Write-Host "ERROR: No Python launchers found to start Y1 Helper."; return $false }
        
        if (Test-Path $y1HelperExe) {
            # Try project WinPython interpreter first, then system launchers
            $scriptDir = $PSScriptRoot; if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
            if (-not $scriptDir) { $scriptDir = Get-Location }
            $winPythonDir = Join-Path $scriptDir "WPy64-31350"
            $projectPythonExe = Join-Path $winPythonDir "WinPython Interpreter.exe"
            
            if (Test-Path $projectPythonExe) {
                Write-Host "Starting Y1 Helper with project WinPython interpreter..."
                Start-Process -FilePath $projectPythonExe -ArgumentList "`"$y1HelperExe`"" -WorkingDirectory $installDir
                Write-Host "Y1 Helper launched successfully with project WinPython interpreter"
                return $true
            } else {
                # Fallback to system launcher
                $systemLauncher = $launchers["System"]
                if (-not $systemLauncher) { $systemLauncher = $launchers["SystemPython"] }
                if ($systemLauncher) {
                    Write-Host "Starting Y1 Helper with system launcher: $systemLauncher..."
                    Start-Process -FilePath $systemLauncher -ArgumentList "`"$y1HelperExe`"" -WorkingDirectory $installDir
                    Write-Host "Y1 Helper launched successfully with system launcher"
                    return $true
                }
            }
            Write-Host "ERROR: No suitable Python launcher found"
            return $false
        } else {
            Write-Host "ERROR: Y1 Helper executable not found"
            return $false
        }
    } catch {
        Write-Host "Error launching Y1 Helper: $($_.Exception.Message)"
        return $false
    }
}

# Create shortcuts with different Python launchers
function New-Y1HelperShortcuts {
    Write-Step "Creating shortcuts..."
    try {
        $installDir = "C:\Program Files\Y1 Helper"
        $y1HelperExe = Join-Path $installDir "y1_helper.py"
        $iconPath = Join-Path $installDir "icon.ico"
        
        # Get launchers
        $launchers = Get-PythonLaunchers
        if (-not $launchers) { Write-Host "ERROR: No Python launchers found for shortcuts."; return $false }
        
        # Get project WinPython interpreter path
        $scriptDir = $PSScriptRoot; if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
        if (-not $scriptDir) { $scriptDir = Get-Location }
        $winPythonDir = Join-Path $scriptDir "WPy64-31350"
        $projectPythonExe = Join-Path $winPythonDir "WinPython Interpreter.exe"
        
        # Remove existing shortcuts first
        Write-Host "Removing existing shortcuts..."
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        $desktopShortcut = Join-Path $desktopPath "Y1 Helper.lnk"
        if (Test-Path $desktopShortcut) { Remove-Item $desktopShortcut -Force; Write-Host "Removed existing desktop shortcut" }
        $startMenuPath = [Environment]::GetFolderPath("StartMenu")
        $startMenuDir = Join-Path $startMenuPath "Programs\Y1 Helper"
        if (Test-Path $startMenuDir) { Remove-Item $startMenuDir -Recurse -Force; Write-Host "Removed existing start menu shortcuts" }
        
        # Create desktop shortcut using project's WinPython interpreter
        Write-Host "Creating desktop shortcut using project WinPython interpreter..."
        if (Test-Path $projectPythonExe) {
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut($desktopShortcut)
            $Shortcut.TargetPath = $projectPythonExe
            $Shortcut.Arguments = "`"$y1HelperExe`""
            $Shortcut.WorkingDirectory = $installDir
            $Shortcut.Description = "Y1 Helper - Device Management Tool (Project WinPython)"
            if (Test-Path $iconPath) { $Shortcut.IconLocation = $iconPath }
            $Shortcut.Save()
            Write-Host "Desktop shortcut created using project WinPython interpreter"
        } else {
            Write-Host "WARNING: Project WinPython interpreter not found, using system launcher for desktop shortcut"
            $systemLauncher = $launchers["System"]
            if (-not $systemLauncher) { $systemLauncher = $launchers["SystemPython"] }
            if ($systemLauncher) {
                $WshShell = New-Object -comObject WScript.Shell
                $Shortcut = $WshShell.CreateShortcut($desktopShortcut)
                $Shortcut.TargetPath = $systemLauncher
                $Shortcut.Arguments = "`"$y1HelperExe`""
                $Shortcut.WorkingDirectory = $installDir
                $Shortcut.Description = "Y1 Helper - Device Management Tool (System Python)"
                if (Test-Path $iconPath) { $Shortcut.IconLocation = $iconPath }
                $Shortcut.Save()
                Write-Host "Desktop shortcut created using system launcher"
            }
        }
        
        # Create start menu folder and shortcuts
        Write-Host "Creating start menu shortcuts..."
        if (-not (Test-Path $startMenuDir)) { New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null }
        
        # Start menu "Start" shortcut using Program Files Python
        $startMenuStartShortcut = Join-Path $startMenuDir "Start.lnk"
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($startMenuStartShortcut)
        $Shortcut.TargetPath = $y1HelperExe
        $Shortcut.WorkingDirectory = $installDir
        $Shortcut.Description = "Y1 Helper - Start (Program Files Python)"
        if (Test-Path $iconPath) { $Shortcut.IconLocation = $iconPath }
        $Shortcut.Save()
        Write-Host "Start menu 'Start' shortcut created (Program Files Python)"
        
        # Start menu "Start using System Python" shortcut
        $systemLauncher = $launchers["System"]
        if (-not $systemLauncher) { $systemLauncher = $launchers["SystemPython"] }
        if ($systemLauncher) {
            $startMenuSystemShortcut = Join-Path $startMenuDir "Start using System Python.lnk"
            $Shortcut = $WshShell.CreateShortcut($startMenuSystemShortcut)
            $Shortcut.TargetPath = $systemLauncher
            $Shortcut.Arguments = "`"$y1HelperExe`""
            $Shortcut.WorkingDirectory = $installDir
            $Shortcut.Description = "Y1 Helper - Start using System Python"
            if (Test-Path $iconPath) { $Shortcut.IconLocation = $iconPath }
            $Shortcut.Save()
            Write-Host "Start menu 'Start using System Python' shortcut created"
        }
        
        Write-Host "Shortcuts created successfully"
        Write-Host "Desktop shortcut: $desktopShortcut"
        Write-Host "Start menu folder: $startMenuDir"
        return $true
    } catch {
        Write-Host "Error creating shortcuts: $($_.Exception.Message)"
        return $false
    }
}

# Main installation function
function Install-Y1HelperComplete {
    Write-Header "Y1 Helper - Complete Installation"
    
    # Check administrator privileges
    if (-not (Test-Administrator)) {
        Request-AdministratorPrivileges
        return
    }
    
    Write-Host "INSTALLATION CONFIGURATION:"
    if ($SkipPython) {
        Write-Host "SKIPPING: Python installation and dependencies"
    } else {
        Write-Host "INCLUDING: Python installation and dependencies"
    }
    if ($SkipMTK) {
        Write-Host "SKIPPING: MTK Driver installation"
    } else {
        Write-Host "INCLUDING: MTK Driver installation"
    }
    if ($Silent) {
        Write-Host "SILENT MODE: No user prompts"
    }
    Write-Host "AUTO-OVERWRITE: Existing installations will be automatically replaced"

    $stageResults = @{}

    # Step 1: MTK Driver
    try {
        if (-not $SkipMTK) {
            Write-Host "Step 1: MTK Driver Installation"
            $stageResults["MTK Driver"] = if (Install-MTKDriver) { "OK" } else { "FAIL" }
        } else {
            $stageResults["MTK Driver"] = "SKIPPED"
        }
    } catch { $stageResults["MTK Driver"] = "FAIL" }

    # Step 2: Python
    try {
        Write-Host "Step 2: Python Installation and Setup"
        $pythonOk = $false
        $pythonInfo = $null
        if (-not $SkipPython) {
            $pythonInfo = Test-PythonInstalled
            if ($pythonInfo) {
                if ($pythonInfo.Compatible) {
                    Write-Host "Compatible Python found: $($pythonInfo.Version)"
                    $pythonOk = $true
                } else {
                    Write-Host "Python found but version may be outdated: $($pythonInfo.Version)"
                    $pythonOk = $true
                }
            } else {
                Write-Host "Python not found, installing..."
                if (Install-PythonWinget -or Install-PythonWindowsInstaller -Version (Get-LatestPythonVersion)) {
                    $pythonOk = $true
                }
            }
            if ($pythonOk) {
                $stageResults["Python"] = "OK"
            } else {
                $stageResults["Python"] = "FAIL"
            }
        } else {
            $stageResults["Python"] = "SKIPPED"
        }
    } catch { $stageResults["Python"] = "FAIL" }

    # Step 3: Dependencies (always try)
    try {
        Write-Host "Step 3: Python Dependencies Installation/Update"
        if (Install-PythonDependencies) {
            $stageResults["Dependencies"] = "OK"
        } else {
            $stageResults["Dependencies"] = "FAIL"
        }
    } catch { $stageResults["Dependencies"] = "FAIL" }

    # Step 4: Y1 Helper
    try {
        Write-Host "Step 4: Y1 Helper Application Installation"
        if (Install-Y1Helper) {
            $stageResults["Y1 Helper"] = "OK"
        } else {
            $stageResults["Y1 Helper"] = "FAIL"
        }
    } catch { $stageResults["Y1 Helper"] = "FAIL" }

    # Step 5: Shortcuts
    try {
        Write-Host "Step 5: Creating Shortcuts"
        if (New-Y1HelperShortcuts) {
            $stageResults["Shortcuts"] = "OK"
        } else {
            $stageResults["Shortcuts"] = "FAIL"
        }
    } catch { $stageResults["Shortcuts"] = "FAIL" }

    # Step 6: Uninstaller
    try {
        Write-Host "Step 6: Creating Uninstaller"
        if (New-Y1HelperUninstaller) {
            $stageResults["Uninstaller"] = "OK"
        } else {
            $stageResults["Uninstaller"] = "FAIL"
        }
    } catch { $stageResults["Uninstaller"] = "FAIL" }

    # Step 7: SP Flash Tool
    try {
        Write-Host "Step 7: Checking SP Flash Tool"
        $stageResults["SP Flash Tool"] = if (Test-SPFlashTool) { "OK" } else { "FAIL" }
    } catch { $stageResults["SP Flash Tool"] = "FAIL" }

    # Step 8: Launch Y1 Helper
    try {
        Write-Host "Step 8: Launching Y1 Helper"
        if (Start-Y1Helper) {
            $stageResults["Y1 Helper Launch"] = "OK"
        } else {
            $stageResults["Y1 Helper Launch"] = "FAIL"
        }
    } catch { $stageResults["Y1 Helper Launch"] = "FAIL" }

    # Summary
    Write-Host "\nINSTALLATION SUMMARY:"
    foreach ($stage in $stageResults.Keys) {
        Write-Host "${stage}: $($stageResults[$stage])"
    }
    Write-Host "\nIf any stage failed, review the output above for details."
    Read-Host "Press Enter to exit"
}

# Run the installation
Install-Y1HelperComplete
