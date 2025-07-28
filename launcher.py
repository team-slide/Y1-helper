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
import configparser
import random

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
        self.api_tokens = []
        self.config_loaded = False
        
        # Load config and tokens
        self.load_config_and_tokens()
    
    def download_and_extract_config(self):
        """Download config.zip from GitHub and extract config.ini"""
        try:
            config_url = "https://github.com/team-slide/Y1-helper/raw/refs/tags/0.7.0/config.zip"
            config_zip_path = os.path.join(self.base_dir, "config.zip")
            config_ini_path = os.path.join(self.base_dir, "config.ini")
            
            print("Downloading config.zip...")
            
            # Download config.zip
            with urllib.request.urlopen(config_url) as response:
                with open(config_zip_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
            
            print("Extracting config.ini from config.zip...")
            
            # Extract config.ini from the zip
            with zipfile.ZipFile(config_zip_path, 'r') as zip_ref:
                zip_ref.extract('config.ini', self.base_dir)
            
            # Clean up the zip file
            os.remove(config_zip_path)
            
            print("Config.ini extracted successfully")
            return True
            
        except Exception as e:
            print(f"Error downloading/extracting config: {e}")
            return False
    
    def load_config_and_tokens(self):
        """Load config.ini and extract API tokens"""
        try:
            config_path = os.path.join(self.base_dir, "config.ini")
            
            # Try to download config if it doesn't exist
            if not os.path.exists(config_path):
                print("Config.ini not found, attempting to download...")
                if not self.download_and_extract_config():
                    print("Failed to download config.ini, using default settings")
                    return
            
            # Load config
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Extract API tokens
            self.api_tokens = []
            
            # Check for api_keys section (new format)
            if 'api_keys' in config:
                try:
                    for key, value in config['api_keys'].items():
                        if isinstance(value, str) and key.startswith('key_') and value.strip():
                            self.api_tokens.append(value.strip())
                except Exception as e:
                    print(f"Error processing api_keys section: {e}")
            
            # Check for legacy token
            if 'github' in config and 'token' in config['github']:
                try:
                    legacy_token = config['github']['token'].strip()
                    if legacy_token and legacy_token not in self.api_tokens:
                        self.api_tokens.append(legacy_token)
                except Exception as e:
                    print(f"Error processing legacy token: {e}")
            
            # Check for individual api_key entries (api_key0 - api_key1000)
            if 'api_keys' in config:
                try:
                    for i in range(1001):  # 0 to 1000
                        key_name = f'api_key{i}'
                        if key_name in config['api_keys']:
                            token = config['api_keys'][key_name].strip()
                            if token and token not in self.api_tokens:
                                self.api_tokens.append(token)
                except Exception as e:
                    print(f"Error processing api_key entries: {e}")
            
            print(f"Loaded {len(self.api_tokens)} API tokens")
            self.config_loaded = True
            
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config_loaded = False
    
    def get_random_token(self):
        """Get a random API token from the loaded tokens"""
        if self.api_tokens:
            return random.choice(self.api_tokens)
        return None
    
    def has_tokens_available(self):
        """Check if any API tokens are available"""
        return len(self.api_tokens) > 0
    
    def create_github_request(self, url):
        """Create a urllib request with GitHub API headers and token"""
        token = self.get_random_token()
        headers = {
            'User-Agent': 'Y1-Helper-Launcher/0.7.0'
        }
        
        if token:
            headers['Authorization'] = f'token {token}'
            print(f"Using authenticated request with token")
        else:
            print(f"Using unauthenticated request (60 requests/hour limit)")
        
        return urllib.request.Request(url, headers=headers)
    
    def handle_rate_limit_error(self, response, url):
        """Handle rate limit errors and provide fallback options"""
        if response.status == 403:  # Rate limit exceeded
            print(f"Rate limit exceeded for {url}")
            
            # Check if we have tokens available
            if self.has_tokens_available():
                print("Retrying with a different token...")
                # Try again with a different token
                return self.create_github_request(url)
            else:
                print("No tokens available, using unauthenticated request as fallback")
                # Use unauthenticated request as last resort
                headers = {
                    'User-Agent': 'Y1-Helper-Launcher/0.7.0'
                }
                return urllib.request.Request(url, headers=headers)
        
        return None  # Not a rate limit error
        
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
            request = self.create_github_request(api_url)
            
            try:
                with urllib.request.urlopen(request) as response:
                    data = json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                # Handle rate limit errors
                fallback_request = self.handle_rate_limit_error(e, api_url)
                if fallback_request:
                    with urllib.request.urlopen(fallback_request) as response:
                        data = json.loads(response.read().decode('utf-8'))
                else:
                    raise e
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
    
    def check_releases_for_exe_requirement(self):
        """Check all releases after current version to see if any require exe update"""
        try:
            # Get current version first
            current_version = self.get_current_version()
            current_parts = self.parse_version(current_version)
            print(f"Current version: {current_version} ({current_parts})")
            
            # Fetch releases with pagination support (up to 1000 releases)
            all_releases = []
            page = 1
            max_pages = 10  # Limit to 1000 releases (10 pages * 100 per page)
            
            while page <= max_pages:
                api_url = f"https://api.github.com/repos/{self.github_repo}/releases?per_page=100&page={page}"
                print(f"Fetching releases page {page}...")
                
                request = self.create_github_request(api_url)
                try:
                    with urllib.request.urlopen(request) as response:
                        releases_data = json.loads(response.read().decode('utf-8'))
                except urllib.error.HTTPError as e:
                    # Handle rate limit errors
                    fallback_request = self.handle_rate_limit_error(e, api_url)
                    if fallback_request:
                        with urllib.request.urlopen(fallback_request) as response:
                            releases_data = json.loads(response.read().decode('utf-8'))
                    else:
                        raise e
                
                if not releases_data:  # No more releases
                    break
                    
                all_releases.extend(releases_data)
                print(f"Fetched {len(releases_data)} releases from page {page}")
                
                # Check if we got less than 100 releases (last page)
                if len(releases_data) < 100:
                    break
                    
                page += 1
            
            print(f"Total releases fetched: {len(all_releases)}")
            
            # Find the first exe-only release that's newer than current version
            for release in all_releases:
                release_tag = release.get('tag_name', 'unknown')
                release_version = self.get_version_from_release_tag(release_tag)
                release_parts = self.parse_version(release_version)
                
                print(f"Checking release: {release_tag} ({release_version})")
                
                # Skip if this release is older than or equal to current version
                if release_parts <= current_parts:
                    print(f"Skipping {release_tag} - older than or equal to current version")
                    continue
                
                # Check if this release requires exe update
                assets = release.get('assets', [])
                exe_assets = [asset for asset in assets if asset['name'].endswith('.exe')]
                py_assets = [asset for asset in assets if asset['name'].endswith('.py')]
                
                print(f"  Assets: {len(assets)} total, {len(exe_assets)} exe, {len(py_assets)} py")
                
                # Check if this is an exe-only release (only exe files, no py files)
                if len(exe_assets) > 0 and len(py_assets) == 0:
                    # This release requires exe update
                    exe_asset = exe_assets[0]  # Take the first exe
                    
                    print(f"Found exe-only release: {release_tag} ({release_version})")
                    print(f"Current: {current_version} -> Target: {release_version}")
                    
                    # Check if version jump is reasonable
                    is_compatible = self.is_version_compatible(current_version, release_version)
                    print(f"Version compatibility: {is_compatible}")
                    
                    if is_compatible:
                        return {
                            'type': 'exe_required',
                            'asset': exe_asset,
                            'release_tag': release_tag,
                            'release_name': release.get('name', ''),
                            'release_body': release.get('body', ''),
                            'release_version': release_version,
                            'current_version': current_version,
                            'reason': f"Release {release_tag} requires exe update"
                        }
                    else:
                        # Version jump too large - return info for logging
                        return {
                            'type': 'exe_required_incompatible',
                            'asset': exe_asset,
                            'release_tag': release_tag,
                            'release_version': release_version,
                            'current_version': current_version,
                            'reason': f"Release {release_tag} requires exe but version jump too large: {current_version} -> {release_version}"
                        }
                elif len(exe_assets) > 0 and len(py_assets) > 0:
                    # This is a mixed release - can be patched normally
                    print(f"Mixed release {release_tag} - can be patched normally")
                    continue
                else:
                    # No exe files in this release - can be patched normally
                    print(f"No exe in release {release_tag} - can be patched normally")
                    continue
            
            # No exe-only releases found that require update
            print("No exe-only releases found that require update")
            return {
                'type': 'no_exe_required',
                'current_version': current_version,
                'reason': "All releases after current version can be patched normally"
            }
                
        except Exception as e:
            print(f"Error checking releases for exe requirement: {e}")
            return None
    
    def check_latest_release_for_exe(self):
        """Check the latest release for exe-only updates with version compatibility (legacy method)"""
        try:
            # Get current version first
            current_version = self.get_current_version()
            print(f"Current version: {current_version}")
            
            # Get the latest release
            api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            request = self.create_github_request(api_url)
            with urllib.request.urlopen(request) as response:
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
            
            request = self.create_github_request(api_url)
            with urllib.request.urlopen(request) as response:
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
            
            # Verify the exe file exists and is executable
            if not os.path.exists(local_exe_path):
                print(f"Error: Exe file not found at {local_exe_path}")
                self.update_progress(100, 100, f"Error: Exe file not found at {local_exe_path}")
                return False
            
            print(f"Exe file found at: {local_exe_path}")
            print(f"File size: {os.path.getsize(local_exe_path)} bytes")
            
            # Check if file is actually an executable
            if not local_exe_path.lower().endswith('.exe'):
                print(f"Warning: File {local_exe_path} does not have .exe extension")
            
            self.update_progress(50, 100, f"Running {exe_file['path']} for user installation...")
            
            # Run the exe file as a detached process with proper error handling
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 1  # SW_SHOWNORMAL = 1
            
            try:
                print(f"Attempting to launch exe with command: {[local_exe_path]}")
                process = subprocess.Popen(
                    [local_exe_path],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )
                
                print(f"Launched {exe_file['path']} with PID: {process.pid}")
                
                # Give the process a moment to start
                time.sleep(0.5)
                
                # Check if process is still running
                if process.poll() is None:
                    print(f"Exe process is running successfully (PID: {process.pid})")
                else:
                    print(f"Warning: Exe process exited immediately with code: {process.returncode}")
                
                # Close the launcher window immediately
                if self.progress_window and self.progress_window.winfo_exists():
                    self.progress_window.destroy()
                
                # Exit the launcher process
                print("Exiting launcher after successful exe launch")
                sys.exit(0)
                
            except subprocess.SubprocessError as e:
                print(f"Subprocess error with DETACHED_PROCESS: {e}")
                # Try alternative method without DETACHED_PROCESS
                print("Trying alternative launch method...")
                process = subprocess.Popen(
                    [local_exe_path],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                print(f"Launched {exe_file['path']} with PID: {process.pid} (alternative method)")
                
                # Give the process a moment to start
                time.sleep(0.5)
                
                # Check if process is still running
                if process.poll() is None:
                    print(f"Exe process is running successfully (PID: {process.pid})")
                else:
                    print(f"Warning: Exe process exited immediately with code: {process.returncode}")
                
                # Close the launcher window immediately
                if self.progress_window and self.progress_window.winfo_exists():
                    self.progress_window.destroy()
                
                # Exit the launcher process
                print("Exiting launcher after successful exe launch (alternative method)")
                sys.exit(0)
            
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
            
            # Verify the exe file exists and is executable
            if not os.path.exists(local_exe_path):
                print(f"Error: Exe file not found at {local_exe_path}")
                self.update_progress(100, 100, f"Error: Exe file not found at {local_exe_path}")
                return False
            
            print(f"Exe file found at: {local_exe_path}")
            print(f"File size: {os.path.getsize(local_exe_path)} bytes")
            
            # Check if file is actually an executable
            if not local_exe_path.lower().endswith('.exe'):
                print(f"Warning: File {local_exe_path} does not have .exe extension")
            
            self.update_progress(50, 100, f"Running {asset_name} for installation...")
            
            # Run the exe file as a detached process with proper error handling
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 1  # SW_SHOWNORMAL = 1
            
            try:
                print(f"Attempting to launch exe with command: {[local_exe_path]}")
                process = subprocess.Popen(
                    [local_exe_path],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )
                
                print(f"Launched {asset_name} with PID: {process.pid}")
                
                # Give the process a moment to start
                time.sleep(0.5)
                
                # Check if process is still running
                if process.poll() is None:
                    print(f"Exe process is running successfully (PID: {process.pid})")
                else:
                    print(f"Warning: Exe process exited immediately with code: {process.returncode}")
                
                # Close the launcher window immediately
                if self.progress_window and self.progress_window.winfo_exists():
                    self.progress_window.destroy()
                
                # Exit the launcher process
                print("Exiting launcher after successful exe launch")
                sys.exit(0)
                
            except subprocess.SubprocessError as e:
                print(f"Subprocess error with DETACHED_PROCESS: {e}")
                # Try alternative method without DETACHED_PROCESS
                print("Trying alternative launch method...")
                process = subprocess.Popen(
                    [local_exe_path],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                print(f"Launched {asset_name} with PID: {process.pid} (alternative method)")
                
                # Give the process a moment to start
                time.sleep(0.5)
                
                # Check if process is still running
                if process.poll() is None:
                    print(f"Exe process is running successfully (PID: {process.pid})")
                else:
                    print(f"Warning: Exe process exited immediately with code: {process.returncode}")
                
                # Close the launcher window immediately
                if self.progress_window and self.progress_window.winfo_exists():
                    self.progress_window.destroy()
                
                # Exit the launcher process
                print("Exiting launcher after successful exe launch (alternative method)")
                sys.exit(0)
            
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
            # Check if updates should be skipped due to version restore
            if self.is_version_restored():
                print("Updates skipped - version was restored")
                return False
            
            self.update_progress(0, 100, f"Checking for updates from branch: {self.github_branch}")
            
            # Refresh config.ini from config.zip
            self.update_progress(5, 100, "Refreshing config.ini...")
            if self.download_and_extract_config():
                # Reload tokens after config refresh
                self.load_config_and_tokens()
                self.update_progress(10, 100, "Config refreshed successfully")
            else:
                self.update_progress(10, 100, "Config refresh skipped")
            
            self.parse_gitignore()
            
            # First, check for exe-only releases that require update
            self.update_progress(15, 100, "Checking all releases for exe requirements...")
            release_info = self.check_releases_for_exe_requirement()
            
            if release_info and release_info['type'] == 'exe_required':
                # An exe-only release is required for update
                self.update_progress(25, 100, f"Exe update required: {release_info['release_tag']}")
                self.update_progress(30, 100, f"Release: {release_info['release_name'] or release_info['release_tag']}")
                self.update_progress(35, 100, f"Version: {release_info['current_version']} -> {release_info['release_version']}")
                self.update_progress(40, 100, f"Reason: {release_info['reason']}")
                
                # Archive current version before running exe
                archive_dir = self.archive_current_version()
                if not archive_dir:
                    print("Warning: Failed to archive current version")
                
                # Download and run the exe (this will exit the launcher immediately)
                success = self.download_and_run_release_exe(release_info)
                # If we get here, the exe launch failed
                return False
            elif release_info and release_info['type'] == 'exe_required_incompatible':
                # Exe-only release required but version is incompatible
                self.update_progress(25, 100, f"Exe update required but version incompatible")
                self.update_progress(30, 100, f"Current: {release_info['current_version']} -> Release: {release_info['release_version']}")
                self.update_progress(35, 100, f"Reason: {release_info['reason']}")
                self.update_progress(40, 100, "Proceeding with normal patch updates...")
                print(f"Version incompatible for exe update: {release_info['reason']}")
            elif release_info and release_info['type'] == 'no_exe_required':
                # No exe-only releases required - can patch normally
                self.update_progress(25, 100, f"No exe updates required")
                self.update_progress(30, 100, f"Current: {release_info['current_version']}")
                self.update_progress(35, 100, f"Reason: {release_info['reason']}")
                self.update_progress(40, 100, "Proceeding with normal patch updates...")
                print(f"No exe updates required: {release_info['reason']}")
            
            # If not an exe-only release, proceed with normal repository file checking
            archive_dir = self.archive_current_version()
            if not archive_dir:
                print("Warning: Failed to archive current version")
            self.update_progress(45, 100, "Fetching repository information...")
            github_files = self.get_github_files()
            if not github_files:
                self.update_progress(100, 100, "No files found in repository")
                return False
            
            # Check for exe-only in repository files (legacy support)
            if len(self.exe_files) == 1 and len(github_files) == 1 and self.exe_files[0]['path'].endswith('.exe'):
                self.update_progress(75, 100, f"Detected exe-only release in repository: {self.exe_files[0]['path']}")
                success = self.download_and_run_exe(self.exe_files[0])
                # If we get here, the exe launch failed
                return False
            
            self.update_progress(50, 100, "Scanning local files...")
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
                    self.update_progress(75, 100, f"Using exe update: {exe_file['path']}")
                    success = self.download_and_run_exe(exe_file)
                    # If we get here, the exe launch failed
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
        """Launch y1_helper.py and monitor for failures with automatic rollback"""
        try:
            y1_helper_path = os.path.join(self.base_dir, "y1_helper.py")
            python_path = os.path.join(self.base_dir, "assets", "python", "python.exe")
            
            if not os.path.exists(y1_helper_path):
                print(f"Error: y1_helper.py not found at {y1_helper_path}")
                return self.handle_launch_failure("y1_helper.py not found")
            
            if not os.path.exists(python_path):
                print(f"Error: Python not found at {python_path}")
                return self.handle_launch_failure("Python interpreter not found")
            
            print(f"Launching y1_helper.py with Python: {python_path}")
            
            # Launch y1_helper.py with monitoring
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 1  # SW_SHOWNORMAL = 1
            
            process = subprocess.Popen(
                [python_path, y1_helper_path], 
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print(f"Launched y1_helper.py with PID: {process.pid}")
            
            # Monitor the process for a short time to detect immediate failures
            self.monitor_y1_helper_process(process)
            
            # Start background monitoring (optional - can be disabled)
            self.start_background_monitoring(process)
            
            # Close the launcher window
            if self.progress_window and self.progress_window.winfo_exists():
                self.progress_window.destroy()
            
            # Exit the launcher process
            sys.exit(0)
            
        except Exception as e:
            print(f"Error launching y1_helper.py: {e}")
            return self.handle_launch_failure(f"Launch error: {str(e)}")
    
    def monitor_y1_helper_process(self, process):
        """Monitor y1_helper.py process for failures and handle rollback if needed"""
        try:
            # Wait a short time to detect immediate failures
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                print("y1_helper.py is running successfully")
                # Clear version restored flag if it was set (newer version is working)
                if self.is_version_restored():
                    print("Clearing version restored flag - newer version is working")
                    self.clear_version_restored()
                return True
            else:
                # Process has exited, check exit code
                exit_code = process.returncode
                print(f"y1_helper.py exited with code: {exit_code}")
                
                # Get any error output
                try:
                    stdout, stderr = process.communicate(timeout=1)
                    if stderr:
                        print(f"y1_helper.py stderr: {stderr.decode('utf-8', errors='ignore')}")
                except:
                    pass
                
                # Handle the failure
                if exit_code != 0:
                    return self.handle_y1_helper_failure(exit_code)
                else:
                    print("y1_helper.py exited normally")
                    # Clear version restored flag if it was set (newer version worked)
                    if self.is_version_restored():
                        print("Clearing version restored flag - newer version worked")
                        self.clear_version_restored()
                    return True
                    
        except Exception as e:
            print(f"Error monitoring y1_helper.py process: {e}")
            return self.handle_y1_helper_failure(-1)
    
    def handle_y1_helper_failure(self, exit_code):
        """Handle y1_helper.py failure with automatic rollback and retry options"""
        print(f"y1_helper.py failed with exit code: {exit_code}")
        
        # Record the failure
        self.record_launch_failure(exit_code)
        
        # Check if we have backup versions to restore from
        backup_versions = self.get_available_backup_versions()
        if backup_versions:
            print(f"Found {len(backup_versions)} backup versions available")
            
            # Show recovery dialog with version selection
            action, selected_backup = self.show_recovery_dialog(None)
            
            if action == "restore" and selected_backup:
                print(f"User chose to restore version: {selected_backup}")
                if self.progress_window and self.progress_window.winfo_exists():
                    self.update_progress(0, 100, "Restoring selected version...")
                
                success = self.restore_from_backup(selected_backup)
                if success:
                    # Mark that we've restored to an older version
                    self.mark_version_restored(selected_backup)
                    print("Version restored successfully, launching y1_helper.py...")
                    if self.progress_window and self.progress_window.winfo_exists():
                        self.update_progress(100, 100, "Version restored! Launching Y1 Helper...")
                        time.sleep(1)
                    return self.launch_y1_helper()
                else:
                    print("Version restore failed")
                    if self.progress_window and self.progress_window.winfo_exists():
                        self.update_progress(100, 100, "Version restore failed!")
                        time.sleep(2)
                    return self.handle_launch_failure("Version restore failed")
            
            else:
                print("User cancelled recovery")
                return self.handle_launch_failure("User cancelled recovery")
        else:
            print("No backup versions available for recovery")
            return self.handle_launch_failure("No backup versions available")
    
    def get_latest_backup_dir(self):
        """Get the most recent backup directory"""
        try:
            backup_base = os.path.join(self.base_dir, ".old")
            if not os.path.exists(backup_base):
                return None
            
            # Find the most recent backup directory
            backup_dirs = []
            for item in os.listdir(backup_base):
                item_path = os.path.join(backup_base, item)
                if os.path.isdir(item_path):
                    backup_dirs.append(item_path)
            
            if not backup_dirs:
                return None
            
            # Sort by modification time (newest first)
            backup_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            return backup_dirs[0]
            
        except Exception as e:
            print(f"Error finding backup directory: {e}")
            return None
    
    def get_available_backup_versions(self):
        """Get list of available backup versions with metadata"""
        try:
            backup_base = os.path.join(self.base_dir, ".old")
            if not os.path.exists(backup_base):
                return []
            
            backup_versions = []
            for item in os.listdir(backup_base):
                item_path = os.path.join(backup_base, item)
                if os.path.isdir(item_path):
                    # Get version info
                    version_name = item
                    version_path = item_path
                    version_time = os.path.getmtime(item_path)
                    version_date = datetime.fromtimestamp(version_time).strftime("%Y-%m-%d %H:%M")
                    
                    # Check if this version has y1_helper.py
                    y1_helper_path = os.path.join(item_path, "y1_helper.py")
                    if os.path.exists(y1_helper_path):
                        backup_versions.append({
                            'name': f"{version_name} ({version_date})",
                            'path': version_path,
                            'timestamp': version_time,
                            'date': version_date
                        })
            
            # Sort by timestamp (newest first)
            backup_versions.sort(key=lambda x: x['timestamp'], reverse=True)
            return backup_versions
            
        except Exception as e:
            print(f"Error getting backup versions: {e}")
            return []
    
    def mark_version_restored(self, backup_path):
        """Mark that a version was restored to pause updates"""
        try:
            restore_file = os.path.join(self.base_dir, "version_restored.json")
            restore_data = {
                "timestamp": time.time(),
                "restored_version": os.path.basename(backup_path),
                "restored_path": backup_path,
                "current_version": self.get_current_version()
            }
            
            with open(restore_file, 'w') as f:
                json.dump(restore_data, f, indent=2)
            
            print(f"Marked version restored: {os.path.basename(backup_path)}")
            
        except Exception as e:
            print(f"Error marking version restored: {e}")
    
    def is_version_restored(self):
        """Check if a version was restored and updates should be paused"""
        try:
            restore_file = os.path.join(self.base_dir, "version_restored.json")
            if os.path.exists(restore_file):
                with open(restore_file, 'r') as f:
                    data = json.load(f)
                return data
            return None
        except Exception as e:
            print(f"Error checking version restore status: {e}")
            return None
    
    def clear_version_restored(self):
        """Clear the version restored flag to resume updates"""
        try:
            restore_file = os.path.join(self.base_dir, "version_restored.json")
            if os.path.exists(restore_file):
                os.remove(restore_file)
                print("Cleared version restored flag")
        except Exception as e:
            print(f"Error clearing version restored flag: {e}")
    
    def show_try_newer_version_dialog(self):
        """Show dialog asking if user wants to try the newer version again"""
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            # Create dialog
            dialog = tk.Toplevel()
            dialog.title("Y1 Helper - Update Available")
            dialog.geometry("450x200")
            dialog.resizable(False, False)
            dialog.grab_set()  # Make modal
            
            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
            y = (dialog.winfo_screenheight() // 2) - (200 // 2)
            dialog.geometry(f"450x200+{x}+{y}")
            
            # Add content
            frame = tk.Frame(dialog, padx=20, pady=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            tk.Label(frame, text="🔄 Update Available", font=("Segoe UI", 14, "bold")).pack(pady=(0, 15))
            
            # Message
            tk.Label(frame, text="A newer version of Y1 Helper is available.\n\nWould you like to try the newer version again?", 
                    font=("Segoe UI", 10), wraplength=410, justify=tk.CENTER).pack(pady=(0, 20))
            
            # Buttons
            button_frame = tk.Frame(frame)
            button_frame.pack()
            
            result = [None]  # Use list to store result
            
            def on_yes():
                result[0] = True
                dialog.destroy()
            
            def on_no():
                result[0] = False
                dialog.destroy()
            
            # Buttons
            tk.Button(button_frame, text="Yes, Try Newer Version", command=on_yes, 
                     bg="#0078d4", fg="white", font=("Segoe UI", 10), width=18).pack(side=tk.LEFT, padx=(0, 10))
            tk.Button(button_frame, text="No, Keep Current", command=on_no, 
                     font=("Segoe UI", 10), width=15).pack(side=tk.LEFT)
            
            # Wait for user response
            dialog.wait_window()
            return result[0] if result[0] is not None else False
            
        except Exception as e:
            print(f"Error showing try newer version dialog: {e}")
            return False
    
    def record_launch_failure(self, exit_code):
        """Record a launch failure for tracking"""
        try:
            failure_file = os.path.join(self.base_dir, "launch_failure.json")
            failure_data = {
                "timestamp": time.time(),
                "exit_code": exit_code,
                "version": self.get_current_version(),
                "branch": self.github_branch
            }
            
            # Read existing failures
            failures = []
            if os.path.exists(failure_file):
                try:
                    with open(failure_file, 'r') as f:
                        failures = json.load(f)
                except:
                    failures = []
            
            # Add new failure
            failures.append(failure_data)
            
            # Keep only last 10 failures
            if len(failures) > 10:
                failures = failures[-10:]
            
            # Write back to file
            with open(failure_file, 'w') as f:
                json.dump(failures, f, indent=2)
            
            print(f"Recorded launch failure (exit code: {exit_code})")
            
        except Exception as e:
            print(f"Error recording launch failure: {e}")
    
    def get_failure_history(self):
        """Get history of recent launch failures"""
        try:
            failure_file = os.path.join(self.base_dir, "launch_failure.json")
            if os.path.exists(failure_file):
                with open(failure_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error reading failure history: {e}")
            return []
    
    def show_recovery_dialog(self, backup_dir):
        """Show simplified recovery dialog with version selection"""
        try:
            import tkinter as tk
            from tkinter import ttk, messagebox
            
            # Get available backup versions
            backup_versions = self.get_available_backup_versions()
            
            # Create dialog
            dialog = tk.Toplevel()
            dialog.title("Y1 Helper - Recovery")
            dialog.geometry("400x300")
            dialog.resizable(False, False)
            dialog.grab_set()  # Make modal
            
            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (dialog.winfo_screenheight() // 2) - (300 // 2)
            dialog.geometry(f"400x300+{x}+{y}")
            
            # Add content
            frame = tk.Frame(dialog, padx=20, pady=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            tk.Label(frame, text="Y1 Helper Recovery", font=("Segoe UI", 14, "bold")).pack(pady=(0, 15))
            
            # Message
            tk.Label(frame, text="Select a working version to restore:", 
                    font=("Segoe UI", 10), wraplength=360).pack(pady=(0, 15))
            
            # Version selection
            version_frame = tk.Frame(frame)
            version_frame.pack(fill=tk.X, pady=(0, 20))
            
            tk.Label(version_frame, text="Version:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
            
            # Create dropdown
            version_var = tk.StringVar()
            version_combo = ttk.Combobox(version_frame, textvariable=version_var, 
                                       font=("Segoe UI", 10), state="readonly", width=30)
            version_combo.pack(fill=tk.X, pady=(5, 0))
            
            # Populate dropdown with available versions
            if backup_versions:
                version_combo['values'] = [v['name'] for v in backup_versions]
                version_combo.current(0)  # Select first version
            else:
                version_combo['values'] = ['No backup versions available']
                version_combo.current(0)
            
            # Buttons
            button_frame = tk.Frame(frame)
            button_frame.pack(pady=(0, 10))
            
            result = [None]  # Use list to store result
            
            def on_restore():
                if backup_versions and version_var.get() in [v['name'] for v in backup_versions]:
                    selected_version = next(v for v in backup_versions if v['name'] == version_var.get())
                    result[0] = ("restore", selected_version['path'])
                else:
                    result[0] = ("cancel", None)
                dialog.destroy()
            
            def on_cancel():
                result[0] = ("cancel", None)
                dialog.destroy()
            
            # Buttons
            tk.Button(button_frame, text="Restore Version", command=on_restore, 
                     bg="#0078d4", fg="white", font=("Segoe UI", 10), width=15).pack(side=tk.LEFT, padx=(0, 10))
            tk.Button(button_frame, text="Cancel", command=on_cancel, 
                     font=("Segoe UI", 10), width=15).pack(side=tk.LEFT)
            
            # Wait for user response
            dialog.wait_window()
            return result[0] if result[0] else ("cancel", None)
            
        except Exception as e:
            print(f"Error showing recovery dialog: {e}")
            # Default to cancel if dialog fails
            return ("cancel", None)
    

    
    def restore_from_backup(self, backup_dir):
        """Restore files from backup directory"""
        try:
            print(f"Restoring from backup: {backup_dir}")
            
            # Get list of files to restore
            files_to_restore = []
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), backup_dir)
                    backup_file = os.path.join(backup_dir, rel_path)
                    target_file = os.path.join(self.base_dir, rel_path)
                    files_to_restore.append((backup_file, target_file))
            
            print(f"Found {len(files_to_restore)} files to restore")
            
            # Restore each file
            for backup_file, target_file in files_to_restore:
                try:
                    # Ensure target directory exists
                    target_dir = os.path.dirname(target_file)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    
                    # Copy file
                    shutil.copy2(backup_file, target_file)
                    print(f"Restored: {os.path.relpath(target_file, self.base_dir)}")
                    
                except Exception as e:
                    print(f"Error restoring {backup_file}: {e}")
            
            print("Restore completed successfully")
            return True
            
        except Exception as e:
            print(f"Error during restore: {e}")
            return False
    
    def handle_launch_failure(self, reason):
        """Handle launch failure with user notification"""
        print(f"Launch failure: {reason}")
        
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            # Show error dialog
            messagebox.showerror("Y1 Helper Launcher Error", 
                               f"Failed to launch Y1 Helper:\n{reason}\n\nPlease check the installation.")
            
        except Exception as e:
            print(f"Error showing failure dialog: {e}")
        
        # Exit with error code
        sys.exit(1)
    
    def should_skip_updates_due_to_failures(self):
        """Check for recent failures and ask user if they want to skip updates"""
        try:
            failures = self.get_failure_history()
            
            # Check for failures in the last 24 hours
            recent_failures = [f for f in failures if time.time() - f.get('timestamp', 0) < 86400]  # 24 hours
            
            if len(recent_failures) >= 3:  # 3 or more failures in 24 hours
                return self.show_skip_updates_dialog(len(recent_failures))
            
            return False
            
        except Exception as e:
            print(f"Error checking for recent failures: {e}")
            return False
    
    def show_skip_updates_dialog(self, failure_count):
        """Show dialog asking if user wants to skip updates due to recent failures"""
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            # Create dialog
            dialog = tk.Toplevel()
            dialog.title("Y1 Helper - Recent Failures Detected")
            dialog.geometry("450x250")
            dialog.resizable(False, False)
            dialog.grab_set()  # Make modal
            
            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
            y = (dialog.winfo_screenheight() // 2) - (250 // 2)
            dialog.geometry(f"450x250+{x}+{y}")
            
            # Add content
            frame = tk.Frame(dialog, padx=20, pady=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            tk.Label(frame, text="⚠️ Recent Failures Detected", font=("Segoe UI", 14, "bold"), fg="orange").pack(pady=(0, 15))
            
            # Message
            message = f"Y1 Helper has encountered {failure_count} failures in the last 24 hours.\n\nThis may indicate an issue with recent updates.\n\nWould you like to skip updates for now and continue with the current version?"
            
            tk.Label(frame, text=message, font=("Segoe UI", 10), wraplength=410, justify=tk.LEFT).pack(pady=(0, 20))
            
            # Buttons
            button_frame = tk.Frame(frame)
            button_frame.pack(pady=(0, 10))
            
            result = [False]  # Use list to store result
            
            def on_skip():
                result[0] = True
                dialog.destroy()
            
            def on_continue():
                result[0] = False
                dialog.destroy()
            
            # Buttons with styling
            tk.Button(button_frame, text="Skip Updates", command=on_skip, 
                     bg="#ff8c00", fg="white", font=("Segoe UI", 10), width=12).pack(side=tk.LEFT, padx=(0, 10))
            tk.Button(button_frame, text="Continue with Updates", command=on_continue, 
                     bg="#0078d4", fg="white", font=("Segoe UI", 10), width=15).pack(side=tk.LEFT)
            
            # Wait for user response
            dialog.wait_window()
            return result[0]
            
        except Exception as e:
            print(f"Error showing skip updates dialog: {e}")
            return False
    
    def start_background_monitoring(self, process):
        """Start background monitoring of y1_helper.py process (optional)"""
        try:
            # Only enable if user wants it (can be controlled by config)
            # For now, disabled by default to avoid complexity
            enable_monitoring = False
            
            if enable_monitoring:
                def monitor_thread():
                    try:
                        # Monitor for up to 5 minutes
                        for _ in range(300):  # 300 seconds = 5 minutes
                            if process.poll() is not None:
                                # Process has exited
                                exit_code = process.returncode
                                if exit_code != 0:
                                    print(f"Background monitoring detected y1_helper.py failure (code: {exit_code})")
                                    # Could implement automatic restart here
                                    break
                            time.sleep(1)
                    except Exception as e:
                        print(f"Background monitoring error: {e}")
                
                # Start monitoring thread
                monitor_thread = threading.Thread(target=monitor_thread, daemon=True)
                monitor_thread.start()
                print("Background monitoring started")
            else:
                print("Background monitoring disabled")
                
        except Exception as e:
            print(f"Error starting background monitoring: {e}")
    
    def run(self):
        """Main launcher function with comprehensive error handling and fallback"""
        try:
            print("Creating progress window...")
            
            # Create progress window with error handling
            try:
                self.create_progress_window()
                print("Progress window created successfully")
                window_created = True
            except Exception as e:
                print(f"Failed to create progress window: {e}")
                window_created = False
            
            # Run update in a separate thread to keep UI responsive
            def update_thread():
                try:
                    print("Starting update thread...")
                    
                    # Check if a version was restored and updates should be paused
                    restored_version = self.is_version_restored()
                    if restored_version:
                        print(f"Version was restored: {restored_version.get('restored_version', 'unknown')}")
                        
                        # Show dialog asking if user wants to try newer version
                        if window_created:
                            self.update_progress(10, 100, "Checking for updates...")
                        
                        try_again = self.show_try_newer_version_dialog()
                        if try_again:
                            print("User chose to try newer version again")
                            # Clear the restored flag to allow updates
                            self.clear_version_restored()
                            if window_created:
                                self.update_progress(20, 100, "Checking for updates...")
                        else:
                            print("User chose to keep current version")
                            if window_created:
                                self.update_progress(100, 100, "Keeping current version. Launching Y1 Helper...")
                                time.sleep(1)
                            self.launch_y1_helper()
                            return
                    
                    # Check for recent failures and ask user if they want to skip updates
                    if self.should_skip_updates_due_to_failures():
                        print("User chose to skip updates due to recent failures")
                        if window_created:
                            self.update_progress(100, 100, "Skipping updates due to recent failures. Launching Y1 Helper...")
                            time.sleep(1)
                        self.launch_y1_helper()
                        return
                    
                    # Update progress if window is available
                    if window_created:
                        self.update_progress(30, 100, "Checking for updates...")
                    
                    result = self.check_and_update()
                    print(f"Update completed with result: {result}")
                    
                    # Handle result
                    if result is True:
                        # Patch update completed successfully, launch y1_helper.py
                        print("Patch update completed, launching y1_helper.py...")
                        if window_created:
                            self.update_progress(100, 100, "Patch update completed! Launching Y1 Helper...")
                            time.sleep(1)  # Brief delay to show completion
                        self.launch_y1_helper()
                    elif result is False:
                        # Update failed or exe was launched (launcher should have exited)
                        print("Update failed or exe was launched, launching y1_helper.py...")
                        if window_created:
                            self.update_progress(100, 100, "No updates needed. Launching Y1 Helper...")
                            time.sleep(1)
                        self.launch_y1_helper()
                    else:
                        # Unexpected result
                        print(f"Unexpected update result: {result}")
                        if window_created:
                            self.update_progress(100, 100, "Update completed. Launching Y1 Helper...")
                            time.sleep(1)
                        self.launch_y1_helper()
                        
                except Exception as e:
                    print(f"Error in update thread: {e}")
                    # Always try to launch y1_helper.py even if update fails
                    if window_created:
                        self.update_progress(100, 100, f"Update error: {str(e)}. Launching Y1 Helper...")
                        time.sleep(1)
                    self.launch_y1_helper()
            
            # Start update thread
            thread = threading.Thread(target=update_thread)
            thread.daemon = True
            thread.start()
            
            # Run main loop with timeout protection
            if window_created:
                try:
                    # Set a timeout for the main loop
                    self.progress_window.after(30000, self.timeout_handler)  # 30 second timeout
                    self.progress_window.mainloop()
                except Exception as e:
                    print(f"Main loop error: {e}")
                    # Fallback: try to launch y1_helper.py directly
                    print("Attempting fallback launch...")
                    self.launch_y1_helper()
            else:
                # No window, just wait for update thread to complete
                print("No progress window, waiting for update to complete...")
                thread.join(timeout=30)  # Wait up to 30 seconds
                if thread.is_alive():
                    print("Update thread timed out, launching y1_helper.py...")
                self.launch_y1_helper()
            
        except Exception as e:
            print(f"Launcher error: {e}")
            try:
                import tkinter as tk
                from tkinter import messagebox
                messagebox.showerror("Launcher Error", f"An error occurred: {str(e)}")
            except:
                print(f"Could not show error dialog: {e}")
            
            # Always try to launch y1_helper.py as last resort
            print("Attempting final fallback launch...")
            self.launch_y1_helper()
    
    def timeout_handler(self):
        """Handle timeout in main loop"""
        print("Main loop timeout, launching y1_helper.py...")
        if self.progress_window and self.progress_window.winfo_exists():
            self.progress_window.destroy()
        self.launch_y1_helper()

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
            if result is True:
                launcher.launch_y1_helper()
            elif result is False:
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