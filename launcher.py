#!/usr/bin/env python3
"""
Y1 Helper Launcher
Downloads latest files from GitHub and launches y1_helper.py
"""

import os
import sys
import subprocess
import urllib.request
import json
import hashlib
import tempfile
import zipfile
import threading
import time
import shutil
from pathlib import Path
from datetime import datetime
import argparse
import tkinter.scrolledtext as scrolledtext

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
except ImportError:
    print("Error: tkinter not available")
    sys.exit(1)

class Y1Launcher:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.github_repo = "team-slide/y1-helper"
        self.github_branch = self.get_branch_from_file()
        self.ignored_patterns = []
        self.progress_window = None
        self.patch_limits = {"added": 15, "changed": 15}  # Limits for patching vs exe update
        
    def get_branch_from_file(self):
        """Get branch from branch.txt file, default to master if not found"""
        branch_path = os.path.join(self.base_dir, "branch.txt")
        if os.path.exists(branch_path):
            try:
                with open(branch_path, 'r', encoding='utf-8') as f:
                    branch = f.read().strip()
                    if branch:
                        print(f"Using branch: {branch}")
                        return branch
            except Exception as e:
                print(f"Error reading branch.txt: {e}")
        print("Using default branch: master")
        return "master"
    
    def parse_gitignore(self):
        """Parse .gitignore file to get ignored patterns"""
        gitignore_path = os.path.join(self.base_dir, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.ignored_patterns.append(line)
            print(f"Loaded {len(self.ignored_patterns)} ignore patterns from .gitignore")
        else:
            print("No .gitignore file found")
    
    def is_ignored(self, file_path):
        """Check if a file should be ignored based on .gitignore patterns"""
        rel_path = os.path.relpath(file_path, self.base_dir)
        
        for pattern in self.ignored_patterns:
            # Handle directory patterns (ending with /)
            if pattern.endswith('/'):
                dir_pattern = pattern[:-1]  # Remove trailing slash
                # Check if the file is in or under this directory
                if (rel_path.startswith(dir_pattern + os.sep) or 
                    rel_path == dir_pattern or
                    any(part == dir_pattern for part in rel_path.split(os.sep))):
                    return True
            else:
                # Handle file patterns
                if (rel_path == pattern or 
                    rel_path.endswith(os.sep + pattern) or
                    pattern in rel_path.split(os.sep)):
                    return True
        
        return False
    
    def get_version(self):
        """Get current version from version.txt"""
        version_path = os.path.join(self.base_dir, "version.txt")
        if os.path.exists(version_path):
            try:
                with open(version_path, 'r', encoding='utf-8') as f:
                    version = f.read().strip()
                    if version:
                        return version
            except:
                pass
        return None
    
    def get_y1_helper_version(self):
        """Get version from y1_helper.py file directly"""
        y1_helper_path = os.path.join(self.base_dir, "y1_helper.py")
        if os.path.exists(y1_helper_path):
            try:
                with open(y1_helper_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for version assignment pattern
                    import re
                    match = re.search(r'self\.version\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        return match.group(1)
            except:
                pass
        return None
    
    def get_current_version(self):
        """Get current version from multiple sources, with fallback"""
        # Try version.txt first
        version = self.get_version()
        if version:
            return version
        
        # Fallback to y1_helper.py
        version = self.get_y1_helper_version()
        if version:
            return version
        
        # Final fallback
        return "0.0.0"
    
    def parse_version(self, version_string):
        """Parse version string into components (major, minor, patch)"""
        try:
            # Handle version strings like "v1.2.3", "1.2.3", "1.2.3-beta", etc.
            import re
            # Remove 'v' prefix and any suffix after dash or plus
            clean_version = re.sub(r'^v', '', version_string)
            clean_version = re.sub(r'[-+].*$', '', clean_version)
            
            parts = clean_version.split('.')
            if len(parts) >= 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            elif len(parts) == 2:
                return (int(parts[0]), int(parts[1]), 0)
            elif len(parts) == 1:
                return (int(parts[0]), 0, 0)
            else:
                return (0, 0, 0)
        except:
            return (0, 0, 0)
    
    def is_version_compatible(self, current_version, target_version):
        """Check if current version is compatible with target version for exe update"""
        current_parts = self.parse_version(current_version)
        target_parts = self.parse_version(target_version)
        
        # For exe-only releases, we want to ensure the user has a recent enough version
        # This prevents running exe updates on very old versions that might need incremental updates first
        
        # Check if target version is newer than current
        if target_parts > current_parts:
            # Calculate version difference
            major_diff = target_parts[0] - current_parts[0]
            minor_diff = target_parts[1] - current_parts[1]
            patch_diff = target_parts[2] - current_parts[2]
            
            # Allow exe updates if:
            # 1. Same major version with minor/patch updates (usually safe)
            # 2. Major version bump of 1 (e.g., 0.5.1 -> 1.0.0)
            # 3. Minor version bump within reasonable range (e.g., 0.5.1 -> 0.6.0 or 0.7.0)
            
            if major_diff == 0:
                # Same major version - allow minor/patch updates within reasonable range
                if minor_diff <= 2:
                    return True
                else:
                    return False
            elif major_diff == 1 and current_parts[0] >= 0:
                # Major version bump of 1 - allow if current major >= 0
                return True
            else:
                # Too big of a jump - require incremental updates
                return False
        else:
            # Target version is same or older - no need for exe update
            return False
    
    def get_version_from_release_tag(self, release_tag):
        """Extract version from release tag"""
        # Handle various tag formats: "v1.2.3", "1.2.3", "release-1.2.3", etc.
        import re
        
        # Try to extract version from tag
        version_match = re.search(r'(\d+\.\d+\.\d+)', release_tag)
        if version_match:
            return version_match.group(1)
        
        # If no version found, try to parse the tag as a version
        return release_tag
    
    def archive_current_version(self):
        """Archive current version to .old directory"""
        try:
            version = self.get_version()
            if version:
                archive_name = f"v{version}"
            else:
                archive_name = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            old_dir = os.path.join(self.base_dir, ".old")
            archive_dir = os.path.join(old_dir, archive_name)
            
            # Create .old directory if it doesn't exist
            os.makedirs(old_dir, exist_ok=True)
            
            # Remove existing archive if it exists
            if os.path.exists(archive_dir):
                shutil.rmtree(archive_dir)
            
            # Copy all files except ignored ones
            self.update_progress(0, 100, f"Archiving current version ({archive_name})...")
            
            copied_files = 0
            total_files = 0
            
            # First, count total files
            for root, dirs, files in os.walk(self.base_dir):
                # Skip ignored directories - this is the key fix
                dirs_to_remove = []
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    if self.is_ignored(dir_path):
                        dirs_to_remove.append(d)
                
                for d in dirs_to_remove:
                    dirs.remove(d)
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    
                    if not self.is_ignored(rel_path):
                        total_files += 1
            
            # Now copy files
            for root, dirs, files in os.walk(self.base_dir):
                # Skip ignored directories - this is the key fix
                dirs_to_remove = []
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    if self.is_ignored(dir_path):
                        dirs_to_remove.append(d)
                
                for d in dirs_to_remove:
                    dirs.remove(d)
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    
                    if not self.is_ignored(rel_path):
                        # Create destination directory
                        dest_dir = os.path.join(archive_dir, os.path.dirname(rel_path))
                        os.makedirs(dest_dir, exist_ok=True)
                        
                        # Copy file
                        dest_path = os.path.join(archive_dir, rel_path)
                        shutil.copy2(file_path, dest_path)
                        
                        copied_files += 1
                        progress = (copied_files / total_files) * 50  # Archive takes first 50% of progress
                        self.update_progress(progress, 100, f"Archiving {rel_path}...")
            
            print(f"Archived {copied_files} files to {archive_dir}")
            return archive_dir
            
        except Exception as e:
            print(f"Error archiving current version: {e}")
            return None
    
    def get_github_files(self):
        """Get list of files from GitHub repository (root only)"""
        try:
            api_url = f"https://api.github.com/repos/{self.github_repo}/git/trees/{self.github_branch}?recursive=1"
            with urllib.request.urlopen(api_url) as response:
                data = json.loads(response.read().decode('utf-8'))
            files = []
            py_files = []
            exe_files = []
            for item in data.get('tree', []):
                if item['type'] == 'blob':
                    file_path = item['path']
                    if not self.is_ignored(file_path):
                        file_info = {
                            'path': file_path,
                            'sha': item['sha'],
                            'size': item.get('size', 0)
                        }
                        files.append(file_info)
                        if file_path.endswith('.py'):
                            py_files.append(file_info)
                        elif file_path.endswith('.exe'):
                            exe_files.append(file_info)
            # Only keep root files
            files = [f for f in files if '/' not in f['path']]
            py_files = [f for f in py_files if '/' not in f['path']]
            exe_files = [f for f in exe_files if '/' not in f['path']]
            print(f"Found {len(files)} files in GitHub repository (root only)")
            print(f"Python files: {len(py_files)}, Executable files: {len(exe_files)}")
            self.py_files = py_files
            self.exe_files = exe_files
            return files
        except Exception as e:
            print(f"Error getting GitHub files: {e}")
            return []
    
    def check_latest_release_for_exe(self):
        """Check the latest release for exe-only updates with version compatibility"""
        try:
            # Get current version first
            current_version = self.get_current_version()
            print(f"Current version: {current_version}")
            
            # Get the latest release
            api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            with urllib.request.urlopen(api_url) as response:
                release_data = json.loads(response.read().decode('utf-8'))
            
            assets = release_data.get('assets', [])
            exe_assets = [asset for asset in assets if asset['name'].endswith('.exe')]
            py_assets = [asset for asset in assets if asset['name'].endswith('.py')]
            release_tag = release_data.get('tag_name', 'unknown')
            
            print(f"Latest release: {release_tag}")
            print(f"Release assets: {len(assets)} total, {len(exe_assets)} exe, {len(py_assets)} py")
            
            # Check if this is an exe-only release (only exe files, no py files)
            if len(exe_assets) > 0 and len(py_assets) == 0:
                # This is an exe-only release - check version compatibility
                exe_asset = exe_assets[0]  # Take the first exe
                
                # Extract version from release tag
                release_version = self.get_version_from_release_tag(release_tag)
                print(f"Release version: {release_version}")
                
                # Check if version is compatible
                is_compatible = self.is_version_compatible(current_version, release_version)
                print(f"Version compatibility: {is_compatible}")
                
                if is_compatible:
                    return {
                        'type': 'exe_only',
                        'asset': exe_asset,
                        'release_tag': release_tag,
                        'release_name': release_data.get('name', ''),
                        'release_body': release_data.get('body', ''),
                        'release_version': release_version,
                        'current_version': current_version
                    }
                else:
                    # Version not compatible - return info for logging
                    return {
                        'type': 'exe_only_incompatible',
                        'asset': exe_asset,
                        'release_tag': release_tag,
                        'release_version': release_version,
                        'current_version': current_version,
                        'reason': f"Version jump too large: {current_version} -> {release_version}"
                    }
            elif len(exe_assets) > 0 and len(py_assets) > 0:
                # This is a mixed release with both exe and py files
                return {
                    'type': 'mixed',
                    'exe_assets': exe_assets,
                    'py_assets': py_assets,
                    'release_tag': release_tag
                }
            else:
                # No exe files in this release
                return {
                    'type': 'no_exe',
                    'assets': assets,
                    'release_tag': release_tag
                }
                
        except Exception as e:
            print(f"Error checking latest release: {e}")
            return None
    
    def get_local_files(self):
        """Get list of local files in the root directory only"""
        local_files = []
        total_files = 0
        ignored_files = 0

        root = self.base_dir
        files = [f for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))]

        for file in files:
            total_files += 1
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, self.base_dir)

            if not self.is_ignored(rel_path):
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                        sha = hashlib.sha1(content).hexdigest()

                    local_files.append({
                        'path': rel_path,
                        'sha': sha,
                        'size': len(content)
                    })
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
            else:
                ignored_files += 1

        print(f"Total files scanned: {total_files}")
        print(f"Files ignored: {ignored_files}")
        print(f"Files included: {len(local_files)}")
        return local_files
    
    def determine_update_strategy(self, files_to_update, new_files):
        """Determine whether to patch files or use exe update based on limits and file types"""
        total_added = len(new_files)
        total_changed = len(files_to_update)
        
        self.update_progress(0, 100, f"Analyzing update strategy...")
        self.update_progress(0, 100, f"Files to add: {total_added}, Files to change: {total_changed}")
        
        # Check if we have .py files available for patching
        has_py_files = len(self.py_files) > 0
        
        # Check if we have .exe files available
        has_exe_files = len(self.exe_files) > 0
        
        # Determine strategy
        if has_py_files and total_added <= self.patch_limits["added"] and total_changed <= self.patch_limits["changed"]:
            strategy = "patch"
            self.update_progress(0, 100, f"Strategy: PATCH (within limits: {total_added}≤{self.patch_limits['added']}, {total_changed}≤{self.patch_limits['changed']})")
        elif has_exe_files:
            strategy = "exe"
            self.update_progress(0, 100, f"Strategy: EXE UPDATE (exceeds limits or no .py files)")
        else:
            strategy = "none"
            self.update_progress(0, 100, f"Strategy: NO UPDATE (no suitable files found)")
        
        return strategy, total_added, total_changed
    
    def download_file(self, file_path, sha):
        """Download a single file from GitHub"""
        try:
            # GitHub API URL for file content
            api_url = f"https://api.github.com/repos/{self.github_repo}/contents/{file_path}?ref={self.github_branch}"
            
            with urllib.request.urlopen(api_url) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            if 'content' in data:
                import base64
                content = base64.b64decode(data['content'])
                
                # Create directory if it doesn't exist
                local_path = os.path.join(self.base_dir, file_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Write file
                with open(local_path, 'wb') as f:
                    f.write(content)
                
                return True
            else:
                print(f"Error: No content found for {file_path}")
                return False
                
        except Exception as e:
            print(f"Error downloading {file_path}: {e}")
            return False
    
    def download_and_run_exe(self, exe_file):
        """Download and run exe file for user installation"""
        try:
            self.update_progress(0, 100, f"Downloading {exe_file['path']}...")
            
            # Download exe file
            if not self.download_file(exe_file['path'], exe_file['sha']):
                return False
            
            local_exe_path = os.path.join(self.base_dir, exe_file['path'])
            
            self.update_progress(50, 100, f"Running {exe_file['path']} for user installation...")
            
            # Run the exe file
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_SHOW  # Show the exe window
            
            process = subprocess.Popen(
                [local_exe_path],
                startupinfo=startupinfo
            )
            
            self.update_progress(75, 100, f"Waiting for {exe_file['path']} to complete...")
            
            # Wait for the exe to complete
            process.wait()
            
            self.update_progress(100, 100, f"{exe_file['path']} installation completed")
            return True
            
        except Exception as e:
            print(f"Error running exe update: {e}")
            self.update_progress(100, 100, f"Error running exe: {str(e)}")
            return False
    
    def download_and_run_release_exe(self, release_info):
        """Download and run exe file from a release asset"""
        try:
            asset = release_info['asset']
            asset_name = asset['name']
            download_url = asset['browser_download_url']
            file_size = asset.get('size', 0)
            
            # Show version information
            current_version = release_info.get('current_version', 'unknown')
            release_version = release_info.get('release_version', 'unknown')
            
            self.update_progress(0, 100, f"Downloading {asset_name} from release {release_info['release_tag']}...")
            self.update_progress(5, 100, f"Updating from version {current_version} to {release_version}")
            
            # Download the exe file
            local_exe_path = os.path.join(self.base_dir, asset_name)
            
            with urllib.request.urlopen(download_url) as response:
                downloaded = 0
                with open(local_exe_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if file_size > 0:
                            percent = (downloaded / file_size) * 50  # Download takes first 50%
                            self.update_progress(percent, 100, f"Downloading {asset_name}... {percent:.1f}%")
                        else:
                            self.update_progress(25, 100, f"Downloading {asset_name}... {downloaded:,} bytes")
            
            self.update_progress(50, 100, f"Running {asset_name} for installation...")
            
            # Run the exe file
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_SHOW  # Show the exe window
            
            process = subprocess.Popen(
                [local_exe_path],
                startupinfo=startupinfo
            )
            
            self.update_progress(75, 100, f"Waiting for {asset_name} to complete installation...")
            
            # Wait for the exe to complete
            process.wait()
            
            self.update_progress(100, 100, f"{asset_name} installation completed successfully")
            return True
            
        except Exception as e:
            print(f"Error running release exe update: {e}")
            self.update_progress(100, 100, f"Error running release exe: {str(e)}")
            return False
    
    def update_progress(self, current, total, message):
        """Update progress bar and log message"""
        if self.progress_window:
            try:
                progress = (current / total) * 100 if total > 0 else 0
                self.progress_window.progress_var.set(progress)
                self.progress_window.log_var.set(message)
                self.progress_window.update()
            except:
                pass
    
    def create_progress_window(self):
        """Create progress window as the only Tk window (no root flash)."""
        self.progress_window = tk.Tk()
        self.progress_window.title("Y1 Helper Launcher - Update Check")
        self.progress_window.geometry("500x300")
        self.progress_window.resizable(False, False)
        # Center window
        self.progress_window.update_idletasks()
        x = (self.progress_window.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.progress_window.winfo_screenheight() // 2) - (300 // 2)
        self.progress_window.geometry(f"500x300+{x}+{y}")
        # Make window modal
        self.progress_window.grab_set()
        # Create widgets
        frame = ttk.Frame(self.progress_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Y1 Helper Launcher", font=("Segoe UI", 14, "bold")).pack(pady=(0, 5))
        ttk.Label(frame, text="Checking for updates and patching...", font=("Segoe UI", 10)).pack(pady=(0, 20))
        # Progress bar
        self.progress_window.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(frame, variable=self.progress_window.progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, pady=(0, 15))
        # Detailed log message
        self.progress_window.log_var = tk.StringVar(value="Initializing launcher...")
        log_label = ttk.Label(frame, textvariable=self.progress_window.log_var, font=("Consolas", 9), wraplength=460, justify=tk.LEFT)
        log_label.pack(fill=tk.X, pady=(0, 10))
        # Status with more detail
        self.progress_window.status_var = tk.StringVar(value="Preparing to check for updates...")
        status_label = ttk.Label(frame, textvariable=self.progress_window.status_var, font=("Segoe UI", 8), wraplength=460, justify=tk.LEFT)
        status_label.pack(fill=tk.X, pady=(5, 0))
        # Branch info
        self.progress_window.branch_var = tk.StringVar(value=f"Branch: {self.github_branch}")
        branch_label = ttk.Label(frame, textvariable=self.progress_window.branch_var, font=("Segoe UI", 8, "italic"))
        branch_label.pack(fill=tk.X, pady=(5, 0))
        # Ensure focus and topmost
        self.progress_window.lift()
        self.progress_window.attributes('-topmost', True)
        self.progress_window.after(100, lambda: self.progress_window.attributes('-topmost', False))
        self.progress_window.focus_force()
    
    def check_and_update(self):
        """Check for updates and download if needed (root files only, exe-only release support)"""
        try:
            self.update_progress(0, 100, f"Checking for updates from branch: {self.github_branch}")
            self.parse_gitignore()
            
            # First, check for exe-only releases
            self.update_progress(10, 100, "Checking latest release for exe updates...")
            release_info = self.check_latest_release_for_exe()
            
            if release_info and release_info['type'] == 'exe_only':
                # This is an exe-only release, handle it directly
                self.update_progress(20, 100, f"Detected exe-only release: {release_info['release_tag']}")
                self.update_progress(25, 100, f"Release: {release_info['release_name'] or release_info['release_tag']}")
                self.update_progress(30, 100, f"Version: {release_info['current_version']} -> {release_info['release_version']}")
                
                # Archive current version before running exe
                archive_dir = self.archive_current_version()
                if not archive_dir:
                    print("Warning: Failed to archive current version")
                
                # Download and run the exe
                success = self.download_and_run_release_exe(release_info)
                if success:
                    self.update_progress(100, 100, "Exe update completed - launcher will exit")
                    return "exit"
                else:
                    return False
            elif release_info and release_info['type'] == 'exe_only_incompatible':
                # Exe-only release found but version is incompatible
                self.update_progress(20, 100, f"Found exe-only release but version incompatible")
                self.update_progress(25, 100, f"Current: {release_info['current_version']} -> Release: {release_info['release_version']}")
                self.update_progress(30, 100, f"Reason: {release_info['reason']}")
                self.update_progress(35, 100, "Proceeding with normal patch updates...")
                print(f"Version incompatible for exe update: {release_info['reason']}")
            
            # If not an exe-only release, proceed with normal repository file checking
            archive_dir = self.archive_current_version()
            if not archive_dir:
                print("Warning: Failed to archive current version")
            self.update_progress(30, 100, "Fetching repository information...")
            github_files = self.get_github_files()
            if not github_files:
                self.update_progress(100, 100, "No files found in repository")
                return False
            
            # Check for exe-only in repository files (legacy support)
            if len(self.exe_files) == 1 and len(github_files) == 1 and self.exe_files[0]['path'].endswith('.exe'):
                self.update_progress(70, 100, f"Detected exe-only release in repository: {self.exe_files[0]['path']}")
                success = self.download_and_run_exe(self.exe_files[0])
                if success:
                    self.update_progress(100, 100, "Exe update completed - launcher will exit")
                    return "exit"
                else:
                    return False
            
            self.update_progress(40, 100, "Scanning local files...")
            local_files = self.get_local_files()
            github_lookup = {f['path']: f for f in github_files}
            local_lookup = {f['path']: f for f in local_files}
            files_to_update = []
            new_files = []
            for github_file in github_files:
                path = github_file['path']
                if path in local_lookup:
                    local_file = local_lookup[path]
                    if local_file['sha'] != github_file['sha']:
                        files_to_update.append(github_file)
                else:
                    new_files.append(github_file)
            total_files = len(files_to_update) + len(new_files)
            if total_files == 0:
                self.update_progress(100, 100, "No updates needed")
                return True
            self.update_progress(60, 100, f"Found {total_files} files to update")
            strategy, added_count, changed_count = self.determine_update_strategy(files_to_update, new_files)
            if strategy == "patch":
                self.update_progress(70, 100, f"Patching {total_files} files...")
                current = 0
                for file_info in files_to_update + new_files:
                    current += 1
                    progress = 70 + (current / total_files) * 25
                    self.update_progress(progress, 100, f"Downloading {file_info['path']}...")
                    if not self.download_file(file_info['path'], file_info['sha']):
                        print(f"Failed to download {file_info['path']}")
                self.update_progress(100, 100, "Patch update complete")
                return True
            elif strategy == "exe":
                if self.exe_files:
                    exe_file = self.exe_files[0]
                    self.update_progress(70, 100, f"Using exe update: {exe_file['path']}")
                    success = self.download_and_run_exe(exe_file)
                    if success:
                        self.update_progress(100, 100, "Exe update completed - launcher will exit")
                        return "exit"
                    else:
                        return False
                else:
                    self.update_progress(100, 100, "No exe files found for update")
                    return False
            else:
                self.update_progress(100, 100, "No suitable update method available")
                return False
        except Exception as e:
            print(f"Error during update: {e}")
            self.update_progress(100, 100, f"Error: {str(e)}")
            return False
    
    def launch_y1_helper(self):
        """Launch y1_helper.py and show real-time output in the progress modal (single line)"""
        try:
            y1_helper_path = os.path.join(self.base_dir, "y1_helper.py")
            python_path = os.path.join(self.base_dir, "assets", "python", "python.exe")
            if not os.path.exists(y1_helper_path) or not os.path.exists(python_path):
                return False
            process = subprocess.Popen([python_path, y1_helper_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            if not self.progress_window or not self.progress_window.winfo_exists():
                self.create_progress_window()
            status_var = self.progress_window.status_var
            def read_output():
                for line in process.stdout:
                    status_var.set(line.strip())
                    self.progress_window.update()
                process.stdout.close()
                process.wait()
                self.progress_window.after(0, lambda: self.progress_window.title("Y1 Helper Finished - Close this window"))
                self.progress_window.after(0, lambda: self.progress_window.grab_release())
                self.progress_window.after(0, lambda: self.progress_window.focus_force())
                # Add a close button when done
                def close_modal():
                    self.progress_window.destroy()
                close_btn = ttk.Button(self.progress_window, text="Close", command=close_modal)
                close_btn.pack(pady=8)
                self.progress_window.protocol("WM_DELETE_WINDOW", close_modal)
                # Exit launcher after launching y1_helper.py
                sys.exit(0)
            threading.Thread(target=read_output, daemon=True).start()
            return True
        except Exception as e:
            print(f"Error launching y1_helper.py: {e}")
            sys.exit(1)
    
    def run(self):
        """Main launcher function"""
        try:
            print("Creating progress window...")
            # Create progress window
            self.create_progress_window()
            print("Progress window created successfully")
            
            # Run update in a separate thread to keep UI responsive
            def update_thread():
                print("Starting update thread...")
                result = self.check_and_update()
                print(f"Update completed with result: {result}")
                
                # Handle result
                if result == "exit":
                    # Exe update completed, show completion message and exit launcher
                    print("Exe update completed, exiting launcher...")
                    self.update_progress(100, 100, "Update completed successfully! Launcher will close.")
                    time.sleep(2)  # Brief delay to show completion
                    if self.progress_window:
                        self.progress_window.after(2000, lambda: self.progress_window.destroy())
                        self.progress_window.after(2500, sys.exit)
                elif result:
                    # Patch update completed, launch y1_helper.py
                    print("Patch update completed, launching y1_helper.py...")
                    self.update_progress(100, 100, "Patch update completed! Launching Y1 Helper...")
                    time.sleep(1)  # Brief delay to show completion
                    self.launch_y1_helper()
                else:
                    print("Update failed, launching y1_helper.py anyway...")
                    self.update_progress(100, 100, "No updates needed. Launching Y1 Helper...")
                    time.sleep(1)
                    self.launch_y1_helper()
            
            # Start update thread
            thread = threading.Thread(target=update_thread)
            thread.daemon = True
            thread.start()
            
            # Run main loop with timeout protection
            try:
                self.progress_window.mainloop()
            except Exception as e:
                print(f"Main loop error: {e}")
                # Fallback: try to launch y1_helper.py directly
                print("Attempting fallback launch...")
                self.launch_y1_helper()
            
        except Exception as e:
            print(f"Launcher error: {e}")
            messagebox.showerror("Launcher Error", f"An error occurred: {str(e)}")

def main():
    """Main entry point"""
    try:
        parser = argparse.ArgumentParser(description="Y1 Helper Launcher")
        parser.add_argument("-old", action="store_true", help="Launch an older version from .old")
        args = parser.parse_args()
        if args.old:
            import tkinter as tk
            from tkinter import messagebox
            messagebox.showinfo("Old Version", "Launching old version is not implemented in this launcher.")
            return
        # --- Show progress window immediately ---
        launcher = Y1Launcher()
        launcher.create_progress_window()  # Show modal as soon as possible
        # --- Start update/patching in a thread ---
        def update_thread():
            result = launcher.check_and_update()
            if result == "exit":
                # Exe update completed, show completion message and exit launcher
                launcher.update_progress(100, 100, "Update completed successfully! Launcher will close.")
                time.sleep(2)  # Brief delay to show completion
                launcher.progress_window.after(2000, lambda: launcher.progress_window.destroy())
                launcher.progress_window.after(2500, sys.exit)
            elif result:
                launcher.launch_y1_helper()
            else:
                launcher.launch_y1_helper()
        thread = threading.Thread(target=update_thread, daemon=True)
        thread.start()
        # --- Run modal mainloop ---
        try:
            launcher.progress_window.mainloop()
        except Exception as e:
            print(f"Main loop error: {e}")
            launcher.launch_y1_helper()
    except Exception as e:
        print(f"Launcher error: {e}")
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Launcher Error", f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main() 