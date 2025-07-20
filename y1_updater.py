#!/usr/bin/env python3
"""
Y1 Helper Updater Script
Efficiently checks for updates and handles patching vs exe download decisions.
"""

import os
import sys
import json
import hashlib
import subprocess
import tempfile
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pathlib import Path
import requests
from typing import Dict, List, Optional, Tuple, Set

# Configuration
GITHUB_REPO = "team-slide/Y1-helper"
GITHUB_API_BASE = "https://api.github.com"
MAX_FILES_FOR_PATCH = 50  # Increased from 10 to 50 for larger projects
WORKING_DIR = Path.cwd()
TEMP_DIR = WORKING_DIR / "temp"  # Add temp directory for updater and helper

def get_github_token() -> str:
    """Get GitHub token from config file or environment variable."""
    # First try to read from config.ini
    config_path = WORKING_DIR / "config.ini"
    if config_path.exists():
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            if config.has_section('github') and config.has_option('github', 'token'):
                return config.get('github', 'token')
        except Exception:
            pass
    
    # Fallback to environment variable
    return os.environ.get("GITHUB_TOKEN", "")

def get_target_branch() -> str:
    """Read the target branch from branch.txt file."""
    branch_file = WORKING_DIR / "branch.txt"
    if branch_file.exists():
        try:
            with open(branch_file, 'r', encoding='utf-8') as f:
                branch = f.read().strip()
                if branch:
                    return branch
        except Exception:
            pass
    return "master"  # Default to master branch  # Work from current directory (root)

class UpdaterGUI:
    """GUI for the updater with progress and log output."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Y1 Helper Updater")
        self.root.geometry("600x200")
        self.root.resizable(True, True)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.root.winfo_screenheight() // 2) - (200 // 2)
        self.root.geometry(f"600x200+{x}+{y}")
        
        # Bring to front
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.root.focus_force()
        
        self.setup_ui()
        self.log_messages = []
        self.expanded = False
        
    def setup_ui(self):
        """Setup the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Y1 Helper Updater", 
                               font=("Segoe UI", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                           maximum=100, length=400)
        self.progress_bar.pack(fill=tk.X)
        
        # Latest log line display
        self.latest_log_var = tk.StringVar(value="Initializing...")
        self.latest_log_label = ttk.Label(progress_frame, textvariable=self.latest_log_var,
                                         font=("Segoe UI", 9), wraplength=550)
        self.latest_log_label.pack(pady=(5, 0))
        
        # Expand log button
        self.expand_btn = ttk.Button(progress_frame, text="📋 Show Full Log", 
                                   command=self.toggle_log_expansion)
        self.expand_btn.pack(pady=(5, 0))
        
        # Log frame (initially hidden)
        self.log_frame = ttk.Frame(main_frame)
        
        # Log label
        log_label = ttk.Label(self.log_frame, text="Update Log:", font=("Segoe UI", 10, "bold"))
        log_label.pack(anchor=tk.W)
        
        # Log text area with scrollbar
        log_container = ttk.Frame(self.log_frame)
        log_container.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.log_text = tk.Text(log_container, height=12, font=("Consolas", 8),
                               bg="#f0f0f0", fg="#000000", wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Close button (initially disabled)
        self.close_btn = ttk.Button(button_frame, text="Close", command=self.root.destroy,
                                   state="disabled")
        self.close_btn.pack(side=tk.RIGHT)
        
    def log(self, message: str):
        """Add a message to the log."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_messages.append(log_entry)
        
        # Update GUI in main thread
        self.root.after(0, self._update_log_display, log_entry)
        
    def _update_log_display(self, message: str):
        """Update the log display (called in main thread)."""
        # Update latest log line
        self.latest_log_var.set(message)
        
        # Update full log if expanded
        if self.expanded:
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        
        self.root.update_idletasks()
        
    def toggle_log_expansion(self):
        """Toggle between compact and expanded log view."""
        if self.expanded:
            # Collapse
            self.log_frame.pack_forget()
            self.expand_btn.config(text="📋 Show Full Log")
            self.root.geometry("600x200")
            self.expanded = False
        else:
            # Expand
            self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            self.expand_btn.config(text="📋 Hide Full Log")
            self.root.geometry("600x400")
            self.expanded = True
            
            # Populate log with all messages
            self.log_text.delete(1.0, tk.END)
            for msg in self.log_messages:
                self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        
    def update_progress(self, value: float, status: str = None):
        """Update progress bar and status."""
        self.root.after(0, self._update_progress_gui, value, status)
        
    def _update_progress_gui(self, value: float, status: str = None):
        """Update progress GUI (called in main thread)."""
        self.progress_var.set(value)
        if status:
            self.latest_log_var.set(status)
        self.root.update_idletasks()
        
    def enable_close(self):
        """Enable the close button."""
        self.root.after(0, lambda: self.close_btn.config(state="normal"))
        
    def show_error(self, title: str, message: str):
        """Show error message."""
        self.root.after(0, lambda: messagebox.showerror(title, message))
        
    def show_info(self, title: str, message: str):
        """Show info message."""
        self.root.after(0, lambda: messagebox.showinfo(title, message))
        
    def run(self):
        """Run the GUI main loop."""
        self.root.mainloop()

def get_file_info(filepath: Path) -> Tuple[int, float]:
    """Get file size and modification time for fast comparison."""
    try:
        stat = filepath.stat()
        return stat.st_size, stat.st_mtime
    except Exception:
        return 0, 0

def get_file_hash(filepath: Path) -> str:
    """Get SHA256 hash of a file, normalized for line endings."""
    hash_sha256 = hashlib.sha256()
    try:
        # Try to read as text first (for text files)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Normalize line endings to LF (GitHub standard)
            normalized_content = content.replace('\r\n', '\n').replace('\r', '\n')
            hash_sha256.update(normalized_content.encode('utf-8'))
        return hash_sha256.hexdigest()
    except (UnicodeDecodeError, UnicodeError):
        # Fallback to binary hash for non-text files (images, executables, etc.)
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""
    except Exception:
        return ""

def parse_gitignore(gui: UpdaterGUI = None) -> Tuple[Set[str], Set[str]]:
    """Parse .gitignore file to get exclude patterns."""
    exclude_dirs = {'.git', '__pycache__', 'node_modules', '.vscode', '.idea', 'build', 'dist', 'python', 'env', 'venv', 'ENV', 'env.bak', 'venv.bak', 'temp'}
    exclude_files = {'.gitignore', '.DS_Store', 'Thumbs.db', 'desktop.ini', 'y1_updater.py', 'branch.txt', 'version.txt', 'config.ini', 'Y1HelperUpdater.exe', 'Y1Helper-*-Setup.exe'}
    
    gitignore_path = WORKING_DIR / '.gitignore'
    if gitignore_path.exists():
        if gui:
            gui.log("Reading .gitignore file...")
        
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle directory patterns (ending with /)
                        if line.endswith('/'):
                            exclude_dirs.add(line[:-1])
                        # Handle file patterns
                        elif '*' in line or '?' in line:
                            # Simple glob pattern - add to both sets for safety
                            exclude_files.add(line)
                            exclude_dirs.add(line)
                        else:
                            exclude_files.add(line)
        except Exception as e:
            if gui:
                gui.log(f"WARNING: Could not read .gitignore: {e}")
    
    if gui:
        gui.log(f"Excluding {len(exclude_dirs)} directories and {len(exclude_files)} file patterns")
    
    return exclude_dirs, exclude_files

def get_local_file_structure(gui: UpdaterGUI = None) -> Dict[str, Tuple[int, float]]:
    """Get local file structure with fast size/mtime comparison, excluding certain directories."""
    if gui:
        gui.log("Analyzing local files...")
        gui.update_progress(5, "Analyzing local files...")
    
    exclude_dirs, exclude_files = parse_gitignore(gui)
    
    file_structure = {}
    
    for root, dirs, files in os.walk(WORKING_DIR):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            filepath = Path(root) / file
            rel_path = filepath.relative_to(WORKING_DIR)
            rel_path_str = str(rel_path).replace('\\', '/')  # Normalize to forward slashes
            
            # Skip if it's the updater itself
            if rel_path.name in {'y1_updater.py'}:
                continue
            
            # Check if file should be excluded based on .gitignore patterns
            should_exclude = False
            
            # Check exact file name match
            if file in exclude_files:
                should_exclude = True
            
            # Check relative path match
            if rel_path_str in exclude_files:
                should_exclude = True
            
            # Check glob patterns (simple implementation)
            for pattern in exclude_files:
                if '*' in pattern or '?' in pattern:
                    # Simple glob matching
                    if pattern.endswith('*'):
                        prefix = pattern[:-1]
                        if rel_path_str.startswith(prefix):
                            should_exclude = True
                            break
                    elif pattern.startswith('*'):
                        suffix = pattern[1:]
                        if rel_path_str.endswith(suffix):
                            should_exclude = True
                            break
                    elif '*' in pattern:
                        # Handle patterns like "*.exe"
                        if pattern.startswith('*.'):
                            ext = pattern[1:]
                            if rel_path_str.endswith(ext):
                                should_exclude = True
                                break
            
            if should_exclude:
                continue
                
            try:
                file_structure[str(rel_path)] = get_file_info(filepath)
            except Exception as e:
                error_msg = f"Error analyzing {rel_path}: {e}"
                if gui:
                    gui.log(f"WARNING: {error_msg}")
                else:
                    print(error_msg)
    
    if gui:
        gui.log(f"Found {len(file_structure)} local files to check")
        gui.update_progress(15, f"Found {len(file_structure)} local files")
    
    return file_structure

def make_github_request(endpoint: str) -> Optional[Dict]:
    """Make a single GitHub API request with error handling."""
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Add authorization header only if token is provided
    github_token = get_github_token()
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    try:
        response = requests.get(f"{GITHUB_API_BASE}/{endpoint}", headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"GitHub API error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def get_github_file_structure(gui: UpdaterGUI = None) -> Optional[Dict[str, Tuple[str, str]]]:
    """Get GitHub repository file structure with minimal API calls, including update dates."""
    if gui:
        gui.log("Connecting to GitHub repository...")
        gui.update_progress(10, "Connecting to GitHub...")
    
    # Get target branch
    target_branch = get_target_branch()
    if gui:
        gui.log(f"Using branch: {target_branch}")
    
    # Get tree recursively in one call
    tree_data = make_github_request(f"repos/{GITHUB_REPO}/git/trees/{target_branch}?recursive=1")
    if not tree_data:
        if gui:
            gui.log("ERROR: Failed to connect to GitHub repository")
        return None
    
    if gui:
        gui.log("Retrieving file structure from GitHub...")
        gui.update_progress(20, "Getting file structure...")
    
    file_structure = {}
    exclude_dirs, exclude_files = parse_gitignore(gui)
    
    for item in tree_data.get('tree', []):
        if item['type'] == 'blob':
            file_path = item['path']
            
            # Check if file should be excluded based on .gitignore patterns
            should_exclude = False
            
            # Check exact path match
            if file_path in exclude_files:
                should_exclude = True
            
            # Check glob patterns (simple implementation)
            for pattern in exclude_files:
                if '*' in pattern or '?' in pattern:
                    # Simple glob matching
                    if pattern.endswith('*'):
                        prefix = pattern[:-1]
                        if file_path.startswith(prefix):
                            should_exclude = True
                            break
                    elif pattern.startswith('*'):
                        suffix = pattern[1:]
                        if file_path.endswith(suffix):
                            should_exclude = True
                            break
                    elif '*' in pattern:
                        # Handle patterns like "*.exe"
                        if pattern.startswith('*.'):
                            ext = pattern[1:]
                            if file_path.endswith(ext):
                                should_exclude = True
                                break
            
            if not should_exclude:
                # Store both SHA and update time
                file_structure[file_path] = (item['sha'], item.get('updated_at', ''))
    
    if gui:
        gui.log(f"Found {len(file_structure)} files in GitHub repository")
        gui.update_progress(30, f"Found {len(file_structure)} files")
    
    return file_structure

def get_latest_release_info() -> Optional[Dict]:
    """Get latest release information."""
    # For releases, we'll use the latest release regardless of branch
    # since releases are typically created from master/main
    return make_github_request(f"repos/{GITHUB_REPO}/releases/latest")

def download_file(url: str, filepath: Path) -> bool:
    """Download a file with progress indication."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Simple progress indicator
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rDownloading: {progress:.1f}%", end='', flush=True)
        
        print()  # New line after progress
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def download_and_run_exe(release_info: Dict, gui: UpdaterGUI = None) -> bool:
    """Download latest exe from release and run it."""
    assets = release_info.get('assets', [])
    exe_asset = None
    
    # Find the first .exe asset
    for asset in assets:
        if asset['name'].endswith('.exe'):
            exe_asset = asset
            break
    
    if not exe_asset:
        error_msg = "No executable found in latest release"
        if gui:
            gui.log(f"ERROR: {error_msg}")
        else:
            print(error_msg)
        return False
    
    if gui:
        gui.log(f"Found executable: {exe_asset['name']}")
        gui.update_progress(40, f"Downloading {exe_asset['name']}...")
    else:
        print(f"Found executable: {exe_asset['name']}")
    
    # Download to temp directory
    temp_dir = Path(tempfile.gettempdir())
    exe_path = temp_dir / exe_asset['name']
    
    if gui:
        gui.log(f"Downloading {exe_asset['name']}...")
    else:
        print(f"Downloading {exe_asset['name']}...")
    
    if not download_file(exe_asset['browser_download_url'], exe_path):
        error_msg = f"Failed to download {exe_asset['name']}"
        if gui:
            gui.log(f"ERROR: {error_msg}")
        else:
            print(error_msg)
        return False
    
    if gui:
        gui.log(f"Downloaded to: {exe_path}")
        gui.update_progress(90, "Launching executable...")
        gui.log("Launching executable...")
    else:
        print(f"Downloaded to: {exe_path}")
        print("Launching executable...")
    
    try:
        # Launch the exe and exit
        subprocess.Popen([str(exe_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True
    except Exception as e:
        error_msg = f"Failed to launch executable: {e}"
        if gui:
            gui.log(f"ERROR: {error_msg}")
        else:
            print(error_msg)
        return False

def patch_files(local_files: Dict[str, Tuple[int, float]], github_files: Dict[str, Tuple[str, str]], gui: UpdaterGUI = None) -> bool:
    """Patch files that are different or missing."""
    files_to_download = []
    import datetime
    
    # Check for missing or different files using date comparison
    for filepath, (github_hash, github_updated_at) in github_files.items():
        local_info = local_files.get(filepath, (0, 0))
        
        if local_info == (0, 0):  # File doesn't exist locally
            files_to_download.append(filepath)
        else:
            # Compare local modification time with GitHub update time
            local_size, local_mtime = local_info
            
            if github_updated_at:
                try:
                    # Parse GitHub date (ISO format)
                    github_date = datetime.datetime.fromisoformat(github_updated_at.replace('Z', '+00:00'))
                    local_date = datetime.datetime.fromtimestamp(local_mtime)
                    
                    # If GitHub file is newer than local file, it needs updating
                    if github_date > local_date:
                        files_to_download.append(filepath)
                except Exception:
                    # If date parsing fails, download the file
                    files_to_download.append(filepath)
            else:
                # If no GitHub date available, download the file
                files_to_download.append(filepath)
    
    if not files_to_download:
        if gui:
            gui.log("All files are up to date")
        else:
            print("All files are up to date")
        return True
    
    if gui:
        gui.log(f"Need to update {len(files_to_download)} files")
        gui.update_progress(40, f"Updating {len(files_to_download)} files...")
    else:
        print(f"Need to update {len(files_to_download)} files")
    
    # Download each file
    for i, filepath in enumerate(files_to_download):
        if gui:
            progress = 40 + (i / len(files_to_download)) * 50
            gui.update_progress(progress, f"Downloading: {filepath}")
            gui.log(f"Downloading: {filepath}")
        else:
            print(f"Downloading: {filepath}")
        
        # Create directory if needed
        file_path = WORKING_DIR / filepath
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get file content from GitHub
        content_data = make_github_request(f"repos/{GITHUB_REPO}/contents/{filepath}")
        if not content_data:
            error_msg = f"Failed to get content for {filepath}"
            if gui:
                gui.log(f"ERROR: {error_msg}")
            else:
                print(error_msg)
            continue
        
        # Decode content
        import base64
        try:
            content = base64.b64decode(content_data['content']).decode('utf-8')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            if gui:
                gui.log(f"Updated: {filepath}")
            else:
                print(f"Updated: {filepath}")
        except Exception as e:
            error_msg = f"Failed to update {filepath}: {e}"
            if gui:
                gui.log(f"ERROR: {error_msg}")
            else:
                print(error_msg)
    
    if gui:
        gui.update_progress(90, "Patching completed")
        gui.log("Patching completed successfully")
    
    return True

def run_updater_logic(gui: UpdaterGUI):
    """Run the updater logic in a separate thread."""
    try:
        # Check if y1_helper.py exists in the current directory
        y1_helper_path = WORKING_DIR / "y1_helper.py"
        if not y1_helper_path.exists():
            gui.log("ERROR: y1_helper.py not found in current directory")
            gui.show_error("Error", "y1_helper.py not found in current directory")
            gui.enable_close()
            return
        
        # Get local file structure
        local_files = get_local_file_structure(gui)
        
        # Get GitHub file structure
        github_files = get_github_file_structure(gui)
        if not github_files:
            gui.log("ERROR: Failed to get GitHub file structure")
            gui.show_error("Error", "Failed to connect to GitHub repository")
            gui.enable_close()
            return
        
        # Count files that need updating using date comparison
        files_to_update = 0
        import datetime
        
        for filepath, (github_hash, github_updated_at) in github_files.items():
            local_info = local_files.get(filepath, (0, 0))
            
            if local_info == (0, 0):  # File doesn't exist locally
                files_to_update += 1
            else:
                # Compare local modification time with GitHub update time
                local_size, local_mtime = local_info
                
                if github_updated_at:
                    try:
                        # Parse GitHub date (ISO format)
                        github_date = datetime.datetime.fromisoformat(github_updated_at.replace('Z', '+00:00'))
                        local_date = datetime.datetime.fromtimestamp(local_mtime)
                        
                        # If GitHub file is newer than local file, it needs updating
                        if github_date > local_date:
                            files_to_update += 1
                    except Exception:
                        # If date parsing fails, assume file needs updating
                        files_to_update += 1
                else:
                    # If no GitHub date available, assume file needs updating
                    files_to_update += 1
        
        gui.log(f"Files that need updating: {files_to_update}")
        gui.update_progress(35, f"Found {files_to_update} files to update")
        
        # Decision logic
        if files_to_update <= MAX_FILES_FOR_PATCH:
            gui.log(f"Updating {files_to_update} files (under {MAX_FILES_FOR_PATCH} limit)")
            if patch_files(local_files, github_files, gui):
                gui.log("Patching completed successfully")
                gui.update_progress(100, "Launching Y1 Helper...")
                gui.log("Launching y1_helper.py...")
                
                # Launch y1_helper.py
                try:
                    y1_helper_path = WORKING_DIR / "y1_helper.py"
                    subprocess.run([sys.executable, str(y1_helper_path)])
                    gui.log("Y1 Helper launched successfully")
                    gui.show_info("Success", "Update completed and Y1 Helper launched successfully!")
                except Exception as e:
                    error_msg = f"Failed to launch y1_helper.py: {e}"
                    gui.log(f"ERROR: {error_msg}")
                    gui.show_error("Error", error_msg)
            else:
                gui.log("ERROR: Patching failed")
                gui.show_error("Error", "Failed to patch files")
        else:
            gui.log(f"Too many files to patch ({files_to_update} > {MAX_FILES_FOR_PATCH})")
            gui.log("Downloading latest executable release...")
            
            # Get latest release
            release_info = get_latest_release_info()
            if not release_info:
                gui.log("ERROR: Failed to get latest release info")
                gui.show_error("Error", "Failed to get latest release information")
                gui.enable_close()
                return
            
            gui.log(f"Latest release: {release_info.get('tag_name', 'Unknown')}")
            
            if download_and_run_exe(release_info, gui):
                gui.log("Executable launched successfully")
                gui.update_progress(100, "Executable launched")
                gui.show_info("Success", "Latest version downloaded and launched successfully!")
            else:
                gui.log("ERROR: Failed to download and launch executable")
                gui.show_error("Error", "Failed to download and launch executable")
        
        gui.enable_close()
        
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        gui.log(f"ERROR: {error_msg}")
        gui.show_error("Error", error_msg)
        gui.enable_close()

def main():
    """Main updater logic with GUI."""
    # Create GUI
    gui = UpdaterGUI()
    
    # Run updater logic in separate thread
    updater_thread = threading.Thread(target=run_updater_logic, args=(gui,))
    updater_thread.daemon = True
    updater_thread.start()
    
    # Run GUI main loop
    gui.run()

if __name__ == "__main__":
    main() 