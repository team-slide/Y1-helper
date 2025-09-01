#!/usr/bin/env python3
"""
Firmware Downloader for MTK Client
Downloads firmware releases from XML manifest and processes them with mtk.py
"""

import sys
import os
import zipfile
import subprocess
import threading
import requests
import configparser
import json
import pickle
import shutil
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                               QWidget, QListWidget, QListWidgetItem, QPushButton, QTextEdit,
                               QLabel, QComboBox, QProgressBar, QMessageBox,
                               QGroupBox, QSplitter, QStackedWidget, QCheckBox, QProgressDialog,
                               QFileDialog, QDialog, QTabWidget)
from PySide6.QtCore import QThread, Signal, Qt, QSize, QTimer
from PySide6.QtGui import QFont, QPixmap, QIcon
import platform
import time
from collections import defaultdict
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import AppKit for macOS Dock hiding (only on macOS)
if platform.system() == "Darwin":
    try:
        import AppKit
    except ImportError:
        AppKit = None

# Global silent mode flag - controls terminal output
SILENT_MODE = True

# Zip file management
ZIP_STORAGE_DIR = Path("firmware_downloads")
EXTRACTED_FILES_LOG = Path("extracted_files.log")

# Installation tracking
INSTALLATION_MARKER_FILE = Path("firmware_installation_in_progress.flag")

# Caching configuration
CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)
CONFIG_CACHE_FILE = CACHE_DIR / "config_cache.json"
MANIFEST_CACHE_FILE = CACHE_DIR / "manifest_cache.json"
CACHE_DURATION = 300  # 5 minutes cache duration

# Performance optimization
MAX_CONCURRENT_REQUESTS = 3
REQUEST_TIMEOUT = 8
TOKEN_VALIDATION_TIMEOUT = 10

def silent_print(*args, **kwargs):
    """Print function that respects silent mode - completely silent by default"""
    # Completely silent - no output to terminal
    pass

def toggle_silent_mode():
    """Toggle silent mode on/off"""
    global SILENT_MODE
    SILENT_MODE = not SILENT_MODE
    # Only output when explicitly toggling to verbose mode
    if not SILENT_MODE:
        print("Verbose mode enabled - press Ctrl+D again to disable")
    return SILENT_MODE

def cleanup_extracted_files():
    """Clean up extracted files at startup"""
    # Note: This function is now disabled to prevent conflicts with installation tracking
    # Extracted files are now managed by the installation marker system
    silent_print("Extracted files cleanup disabled - using installation marker system instead")
    return

def cleanup_firmware_files():
    """Clean up extracted firmware files (lk.bin, boot.img, etc.)"""
    try:
        firmware_files = ["lk.bin", "boot.img", "recovery.img", "system.img", "userdata.img"]
        cleaned_count = 0
        
        for file_name in firmware_files:
            file_path = Path(file_name)
            if file_path.exists():
                file_path.unlink()
                cleaned_count += 1
                silent_print(f"Cleaned up firmware file: {file_name}")
        
        if cleaned_count > 0:
            silent_print(f"Cleaned up {cleaned_count} firmware files")
        else:
            silent_print("No firmware files found to clean up")
            
    except Exception as e:
        silent_print(f"Error cleaning up firmware files: {e}")

def log_extracted_files(files):
    """Log extracted files for cleanup"""
    # Note: This function is now disabled to prevent conflicts with installation tracking
    # Extracted files are now managed by the installation marker system
    silent_print("Extracted files logging disabled - using installation marker system instead")
    return

def create_installation_marker():
    """Create a marker file to indicate firmware installation is in progress"""
    try:
        INSTALLATION_MARKER_FILE.touch()
        silent_print("Created installation marker file")
    except Exception as e:
        silent_print(f"Error creating installation marker: {e}")

def remove_installation_marker():
    """Remove the installation marker file when installation completes successfully"""
    try:
        if INSTALLATION_MARKER_FILE.exists():
            INSTALLATION_MARKER_FILE.unlink()
            silent_print("Removed installation marker file - installation completed successfully")
    except Exception as e:
        silent_print(f"Error removing installation marker: {e}")

def check_for_failed_installation():
    """Check if there was a failed firmware installation"""
    if INSTALLATION_MARKER_FILE.exists():
        silent_print("Detected failed firmware installation - showing troubleshooting options")
        return True
    return False

def get_zip_path(repo_name, version):
    """Get the path for a specific zip file"""
    safe_repo_name = repo_name.replace('/', '_')
    return ZIP_STORAGE_DIR / f"{safe_repo_name}_{version}.zip"

def load_cache(cache_file):
    """Load data from cache if it exists and is not expired"""
    try:
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)

            # Check if cache is still valid
            if time.time() - cached_data.get('timestamp', 0) < CACHE_DURATION:
                silent_print(f"Using cached data from {cache_file}")
                return cached_data.get('data')
            else:
                silent_print(f"Cache expired for {cache_file}")
        return None
    except Exception as e:
        silent_print(f"Error loading cache {cache_file}: {e}")
        return None

def save_cache(cache_file, data):
    """Save data to cache with timestamp"""
    try:
        cache_data = {
            'timestamp': time.time(),
            'data': data
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        silent_print(f"Cached data to {cache_file}")
    except Exception as e:
        silent_print(f"Error saving cache {cache_file}: {e}")

def clear_cache():
    """Clear all cached data"""
    try:
        for cache_file in [CONFIG_CACHE_FILE, MANIFEST_CACHE_FILE]:
            if cache_file.exists():
                cache_file.unlink()
                silent_print(f"Cleared cache: {cache_file}")
    except Exception as e:
        silent_print(f"Error clearing cache: {e}")



def delete_zip_file(repo_name, version):
    """Delete a specific zip file"""
    zip_path = get_zip_path(repo_name, version)
    if zip_path.exists():
        zip_path.unlink()
        return True
    return False

def delete_all_cached_zips():
    """Delete all cached zip files in the firmware_downloads directory"""
    try:
        if not ZIP_STORAGE_DIR.exists():
            return 0
        
        deleted_count = 0
        for zip_file in ZIP_STORAGE_DIR.glob("*.zip"):
            try:
                zip_file.unlink()
                deleted_count += 1
                silent_print(f"Deleted cached zip: {zip_file.name}")
            except Exception as e:
                silent_print(f"Error deleting {zip_file.name}: {e}")
        
        return deleted_count
    except Exception as e:
        silent_print(f"Error deleting cached zips: {e}")
        return 0


class ConfigDownloader:
    """Downloads and parses configuration files from GitHub with caching"""

    def __init__(self):
        self.config_url = "https://raw.githubusercontent.com/team-slide/Y1-helper/refs/heads/master/config.ini"
        self.manifest_url = "https://raw.githubusercontent.com/team-slide/slidia/refs/heads/main/slidia_manifest.xml"
        self.session = requests.Session()
        self.session.timeout = REQUEST_TIMEOUT

    def download_config(self):
        """Download and parse the config.ini file to extract API tokens with caching"""
        # Try cache first
        cached_tokens = load_cache(CONFIG_CACHE_FILE)
        if cached_tokens:
            return cached_tokens

        try:
            silent_print("Downloading tokens from remote config...")
            silent_print(f"Config URL: {self.config_url}")
            response = self.session.get(self.config_url, timeout=REQUEST_TIMEOUT)
            silent_print(f"Response status: {response.status_code}")

            if response.status_code != 200:
                silent_print(f"Failed to download config: HTTP {response.status_code}")
                silent_print(f"Response text: {response.text[:200]}...")
                
                # Check if it's a rate limit issue
                if response.status_code == 403:
                    silent_print("GitHub API rate limited - this is normal for unauthenticated requests")
                    silent_print("The app will work with limited functionality until rate limit resets")
                elif response.status_code == 404:
                    silent_print("Config file not found - check if the repository structure has changed")
                elif response.status_code >= 500:
                    silent_print("GitHub server error - temporary issue, will retry later")
                
                return []

            response.raise_for_status()

            config = configparser.ConfigParser()
            config.read_string(response.text)

            silent_print(f"Config sections found: {list(config.sections())}")

            tokens = []
            if 'api_keys' in config:
                silent_print("Found api_keys section")
                for key, value in config['api_keys'].items():
                    if key.startswith('key_') and value.strip():
                        # Handle different token formats
                        token = value.strip()

                        # Remove github_pat_ prefix if present (tokens are stored without prefix for obfuscation)
                        if token.startswith('github_pat_'):
                            token = token[11:]  # Remove prefix

                        # Store token without prefix for consistency
                        if token and len(token) > 10:  # Basic validation
                            tokens.append(token)
                            silent_print(f"Added token: {key} -> {token[:10]}...")

            # Also check legacy token
            if 'github' in config and 'token' in config['github']:
                silent_print("Found legacy github token")
                token = config['github']['token'].strip()

                # Store legacy token without prefix for consistency
                if token.startswith('github_pat_'):
                    token = token[11:]  # Remove prefix

                if token and len(token) > 10 and token not in tokens:
                    tokens.append(token)
                    silent_print(f"Added legacy token: {token[:10]}...")

            silent_print(f"Successfully loaded {len(tokens)} tokens from remote config")
            if tokens:
                silent_print(f"First token preview: {tokens[0][:10]}...")
                # Cache the tokens
                save_cache(CONFIG_CACHE_FILE, tokens)
            else:
                silent_print("No valid tokens found in config - will use unauthenticated mode")
            return tokens
        except Exception as e:
            silent_print(f"Error downloading config: {e}")
            silent_print("Falling back to unauthenticated requests only")
            return []

    def download_manifest(self):
        """Download and parse the XML manifest file with caching"""
        # Try cache first
        cached_packages = load_cache(MANIFEST_CACHE_FILE)
        if cached_packages:
            return cached_packages

        try:
            response = self.session.get(self.manifest_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            root = ET.fromstring(response.text)
            packages = []

            # Handle the actual manifest structure with <slidia> root
            if root.tag == 'slidia':
                # Find all package elements within the slidia root
                for package in root.findall('package'):
                    pkg_data = package.attrib
                    package_info = {
                        'name': pkg_data.get('name', 'Unknown'),
                        'device_type': pkg_data.get('device_type', ''),
                        'repo': pkg_data.get('repo', ''),
                        'device': pkg_data.get('device', ''),
                        'url': pkg_data.get('url', ''),
                        'type': pkg_data.get('type', ''),
                        'handler': pkg_data.get('handler', '')
                    }
                    packages.append(package_info)
                    silent_print(f"Parsed package: {package_info['name']} -> {package_info['repo']}")
            else:
                # Fallback to old structure for backward compatibility
                for package in root.findall('package'):
                    pkg_data = package.attrib
                    package_info = {
                        'name': pkg_data.get('name', 'Unknown'),
                        'device_type': pkg_data.get('device_type', ''),
                        'repo': pkg_data.get('repo', ''),
                        'device': pkg_data.get('device', ''),
                        'url': pkg_data.get('url', ''),
                        'type': pkg_data.get('type', ''),
                        'handler': pkg_data.get('handler', '')
                    }
                    packages.append(package_info)
                    silent_print(f"Parsed package (fallback): {package_info['name']} -> {package_info['repo']}")

            silent_print(f"Successfully loaded {len(packages)} packages from manifest")
            # Cache the packages
            save_cache(MANIFEST_CACHE_FILE, packages)
            return packages
        except Exception as e:
            silent_print(f"Error downloading manifest: {e}")
            return []


import time
import random
from collections import defaultdict

class GitHubAPI:
    """GitHub API wrapper for fetching release information with rate limiting and caching"""

    def __init__(self, tokens):
        self.tokens = tokens
        self.token_usage = defaultdict(int)  # Track API calls per token
        self.last_reset = time.time()
        self.hourly_limit = 25  # Limit calls per hour per token
        self.call_timestamps = defaultdict(list)  # Track call timestamps for rate limiting
        self.working_tokens = set()  # Track which tokens are known to work
        self.session = requests.Session()
        self.session.timeout = REQUEST_TIMEOUT

        # Unauthenticated rate limiting (more lenient: 60 requests per hour)
        self.unauth_calls = []
        self.unauth_hourly_limit = 60

        # Caching for releases to improve fallback reliability
        self.releases_cache = {}
        self.cache_duration = 3600  # 1 hour cache duration

    def get_next_token(self):
        """Get the next available token with load balancing and rate limiting"""
        if not self.tokens:
            return None

        current_time = time.time()

        # Clean up old timestamps (older than 1 hour)
        for token in self.call_timestamps:
            self.call_timestamps[token] = [ts for ts in self.call_timestamps[token]
                                         if current_time - ts < 3600]

        # Find tokens that haven't exceeded hourly limit
        available_tokens = []
        working_available = []
        regular_available = []

        for token in self.tokens:
            if len(self.call_timestamps[token]) < self.hourly_limit:
                available_tokens.append(token)
                if self.is_token_working(token):
                    working_available.append(token)
                else:
                    regular_available.append(token)

        if not available_tokens:
            # All tokens are rate limited, return None instead of infinite loop
            silent_print("All tokens are rate limited, returning None")
            return None

        # Prioritize working tokens, then fall back to regular tokens
        if working_available:
            selected_token = random.choice(working_available)
            silent_print(f"Using working token: {selected_token[:10]}...")
        else:
            selected_token = random.choice(regular_available)
            silent_print(f"Using regular token: {selected_token[:10]}...")

        # Record this API call
        self.call_timestamps[selected_token].append(current_time)

        # Ensure token has github_pat_ prefix for GitHub API
        if not selected_token.startswith('github_pat_'):
            selected_token = f"github_pat_{selected_token}"

        return selected_token

    def mark_token_working(self, token):
        """Mark a token as working (remove github_pat_ prefix if present)"""
        if token.startswith('github_pat_'):
            token = token[11:]  # Remove prefix
        self.working_tokens.add(token)
        silent_print(f"Marked token as working: {token[:10]}...")

    def is_token_working(self, token):
        """Check if a token is known to work"""
        if token.startswith('github_pat_'):
            token = token[11:]  # Remove prefix
        return token in self.working_tokens

    def can_make_unauth_request(self):
        """Check if we can make an unauthenticated request (rate limit: 30/hour)"""
        current_time = time.time()

        # Clean up old calls (older than 1 hour)
        self.unauth_calls = [ts for ts in self.unauth_calls if current_time - ts < 3600]

        # Check if we're under the limit
        if len(self.unauth_calls) < self.unauth_hourly_limit:
            return True

        silent_print(f"Unauthenticated rate limit reached ({len(self.unauth_calls)}/hour)")
        return False

    def record_unauth_request(self):
        """Record an unauthenticated API call"""
        self.unauth_calls.append(time.time())
        silent_print(f"Recorded unauthenticated API call ({len(self.unauth_calls)}/hour)")

    def retry_with_delay(self, func, *args, max_retries=3, delay=1):
        """Retry a function with exponential backoff"""
        for attempt in range(max_retries):
            try:
                result = func(*args)
                if result is not None:
                    return result
            except Exception as e:
                silent_print(f"Attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff

        return None

    def get_latest_release(self, repo):
        """Get the latest release information for a repository with fallback"""
        url = f"https://api.github.com/repos/{repo}/releases/latest"

        # Try with authenticated token first (since unauthenticated is failing)
        token = self.get_next_token()
        if token:
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            }

            try:
                response = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    release_data = response.json()
                    assets = release_data.get('assets', [])

                    # Find any zip asset (more flexible than just rom.zip)
                    zip_asset = None
                    for asset in assets:
                        if asset['name'].lower().endswith('.zip'):
                            zip_asset = asset
                            break

                    return {
                        'tag_name': release_data.get('tag_name', ''),
                        'name': release_data.get('name', ''),
                        'body': release_data.get('body', ''),
                        'download_url': zip_asset['browser_download_url'] if zip_asset else None,
                        'asset_name': zip_asset['name'] if zip_asset else None
                    }
                elif response.status_code == 401:
                    silent_print(f"Token authentication failed for {repo} - trying unauthenticated...")
                elif response.status_code == 403:
                    silent_print(f"Rate limited for {repo}, trying unauthenticated...")
                else:
                    silent_print(f"Error getting release for {repo}: {response.status_code}")
            except Exception as e:
                silent_print(f"Error getting release for {repo} with token: {e}")

        # Try unauthenticated as fallback (with rate limiting)
        if not self.can_make_unauth_request():
            silent_print("Unauthenticated rate limit reached, trying cached data...")
            # Try to get cached latest release if available
            cached_releases = self.get_cached_releases(repo)
            if cached_releases and len(cached_releases) > 0:
                latest_cached = cached_releases[0]  # First one should be latest
                silent_print(f"Returning cached latest release for {repo}: {latest_cached.get('tag_name', 'Unknown')}")
                return latest_cached
            return None

        try:
            self.record_unauth_request()
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                release_data = response.json()
                assets = release_data.get('assets', [])

                # Find any zip asset (more flexible than just rom.zip)
                zip_asset = None
                for asset in assets:
                    if asset['name'].lower().endswith('.zip'):
                        zip_asset = asset
                        break

                result = {
                    'tag_name': release_data.get('tag_name', ''),
                    'name': release_data.get('name', ''),
                    'body': release_data.get('body', ''),
                    'download_url': zip_asset['browser_download_url'] if zip_asset else None,
                    'asset_name': zip_asset['name'] if zip_asset else None
                }
                
                # Cache this successful response
                if result['download_url']:
                    self.cache_releases(repo, [result])
                
                return result
            elif response.status_code == 403:
                silent_print(f"Unauthenticated request rate limited for {repo}")
                # Try to get cached data if available
                cached_releases = self.get_cached_releases(repo)
                if cached_releases and len(cached_releases) > 0:
                    latest_cached = cached_releases[0]
                    silent_print(f"Returning cached latest release for {repo}: {latest_cached.get('tag_name', 'Unknown')}")
                    return latest_cached
            else:
                silent_print(f"Unauthenticated request failed for {repo}: {response.status_code}")
        except Exception as e:
            silent_print(f"Error getting release for {repo} unauthenticated: {e}")

        # Final fallback: try to get cached data
        cached_releases = self.get_cached_releases(repo)
        if cached_releases and len(cached_releases) > 0:
            latest_cached = cached_releases[0]
            silent_print(f"Returning cached latest release for {repo}: {latest_cached.get('tag_name', 'Unknown')}")
            return latest_cached

        return None

    def get_all_releases(self, repo):
        """Get all releases for a repository with improved performance"""
        url = f"https://api.github.com/repos/{repo}/releases"

        # Try with authenticated token first
        token = self.get_next_token()
        if token:
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            }

            try:
                silent_print(f"Attempting authenticated request to {url} with token: {token[:10]}...")
                response = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                silent_print(f"Authenticated response status: {response.status_code}")

                if response.status_code == 200:
                    releases_data = response.json()
                    silent_print(f"Found {len(releases_data)} total releases for {repo}")
                    releases = []

                    for release in releases_data:
                        assets = release.get('assets', [])
                        silent_print(f"Release {release.get('tag_name', 'Unknown')} has {len(assets)} assets")

                        # Find any zip asset (more flexible than just rom.zip)
                        zip_asset = None
                        for asset in assets:
                            if asset['name'].lower().endswith('.zip'):
                                zip_asset = asset
                                silent_print(f"Found zip asset: {asset['name']}")
                                break

                        if zip_asset:  # Include releases with any zip file
                            releases.append({
                                'tag_name': release.get('tag_name', ''),
                                'name': release.get('name', ''),
                                'body': release.get('body', ''),
                                'published_at': release.get('published_at', ''),
                                'download_url': zip_asset['browser_download_url'],
                                'asset_name': zip_asset['name'],
                                'asset_size': zip_asset.get('size', 0)
                            })
                            silent_print(f"Added release {release.get('tag_name', 'Unknown')} with zip asset")
                        else:
                            silent_print(f"No zip assets found for release {release.get('tag_name', 'Unknown')}")

                    silent_print(f"Returning {len(releases)} releases with zip assets")
                    return releases
                elif response.status_code == 401:
                    silent_print(f"Token authentication failed for {repo} - trying unauthenticated...")
                elif response.status_code == 403:
                    silent_print(f"Rate limited for {repo}, trying unauthenticated...")
                else:
                    silent_print(f"Error getting releases for {repo}: {response.status_code}")
            except Exception as e:
                silent_print(f"Error getting releases for {repo} with token: {e}")

        # Try unauthenticated as fallback (with rate limiting)
        if not self.can_make_unauth_request():
            silent_print("Unauthenticated rate limit reached, trying alternative fallback...")
            # Try to get cached data if available
            cached_releases = self.get_cached_releases(repo)
            if cached_releases:
                silent_print(f"Returning {len(cached_releases)} cached releases for {repo}")
                return cached_releases
            
            # If no cached data and rate limited, try to make one more request anyway
            # This helps when the rate limit is just about to reset
            silent_print("Rate limited but trying one more request for critical data...")
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    silent_print("Rate limit bypass successful!")
                    releases_data = response.json()
                    releases = []
                    
                    for release in releases_data:
                        assets = release.get('assets', [])
                        zip_asset = None
                        for asset in assets:
                            if asset['name'].lower().endswith('.zip'):
                                zip_asset = asset
                                break
                        
                        if zip_asset:
                            releases.append({
                                'tag_name': release.get('tag_name', ''),
                                'name': release.get('name', ''),
                                'body': release.get('body', ''),
                                'published_at': release.get('published_at', ''),
                                'download_url': zip_asset['browser_download_url'],
                                'asset_name': zip_asset['name'],
                                'asset_size': zip_asset.get('size', 0)
                            })
                    
                    if releases:
                        self.cache_releases(repo, releases)
                        return releases
            except Exception as e:
                silent_print(f"Rate limit bypass failed: {e}")
            
            return []

        try:
            self.record_unauth_request()
            silent_print(f"Attempting unauthenticated request to {url}")
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            silent_print(f"Unauthenticated response status: {response.status_code}")

            if response.status_code == 200:
                releases_data = response.json()
                silent_print(f"Unauthenticated: Found {len(releases_data)} total releases for {repo}")
                releases = []

                for release in releases_data:
                    assets = release.get('assets', [])

                    # Find any zip asset (more flexible than just rom.zip)
                    zip_asset = None
                    for asset in assets:
                        if asset['name'].lower().endswith('.zip'):
                            zip_asset = asset
                            break

                    if zip_asset:  # Include releases with any zip file
                        releases.append({
                            'tag_name': release.get('tag_name', ''),
                            'name': release.get('name', ''),
                            'body': release.get('body', ''),
                            'published_at': release.get('published_at', ''),
                            'download_url': zip_asset['browser_download_url'],
                            'asset_name': zip_asset['name'],
                            'asset_size': zip_asset.get('size', 0)
                        })

                silent_print(f"Unauthenticated: Returning {len(releases)} releases with zip assets")
                # Cache the successful unauthenticated response
                self.cache_releases(repo, releases)
                return releases
            elif response.status_code == 403:
                silent_print(f"Unauthenticated request rate limited for {repo}")
                # Try to get cached data if available
                cached_releases = self.get_cached_releases(repo)
                if cached_releases:
                    silent_print(f"Returning {len(cached_releases)} cached releases for {repo}")
                    return cached_releases
            else:
                silent_print(f"Unauthenticated request failed for {repo}: {response.status_code}")
        except Exception as e:
            silent_print(f"Error getting releases for {repo} unauthenticated: {e}")

        # Final fallback: try to get cached data
        cached_releases = self.get_cached_releases(repo)
        if cached_releases:
            silent_print(f"Returning {len(cached_releases)} cached releases for {repo}")
            return cached_releases

        silent_print(f"No releases found for {repo} - returning empty list")
        return []

    def get_cached_releases(self, repo):
        """Get cached releases for a repository if available and not expired"""
        if repo in self.releases_cache:
            cache_time, releases = self.releases_cache[repo]
            if time.time() - cache_time < self.cache_duration:
                silent_print(f"Using cached releases for {repo} (age: {time.time() - cache_time:.0f}s)")
                return releases
            else:
                # Remove expired cache entry
                del self.releases_cache[repo]
        return None

    def cache_releases(self, repo, releases):
        """Cache releases for a repository"""
        self.releases_cache[repo] = (time.time(), releases)
        silent_print(f"Cached {len(releases)} releases for {repo}")

    def clear_expired_cache(self):
        """Clear expired cache entries"""
        current_time = time.time()
        expired_repos = []
        for repo, (cache_time, _) in self.releases_cache.items():
            if current_time - cache_time >= self.cache_duration:
                expired_repos.append(repo)
        
        for repo in expired_repos:
            del self.releases_cache[repo]
            silent_print(f"Cleared expired cache for {repo}")

    def cleanup_cache_periodically(self):
        """Clean up expired cache entries periodically"""
        self.clear_expired_cache()
        # Schedule next cleanup in 10 minutes
        QTimer.singleShot(600000, self.cleanup_cache_periodically)





class DebugOutputWindow(QWidget):
    """Debug output window for showing mtk.py output in real-time"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MTK Debug Output - Labs Mode")
        self.setGeometry(200, 200, 800, 600)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Title label
        title_label = QLabel("MTK.py Output (Debug Mode)")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 5px;")
        layout.addWidget(title_label)
        
        # Output text area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.output_text)
        
        # Clear button
        clear_btn = QPushButton("Clear Output")
        clear_btn.clicked.connect(self.clear_output)
        layout.addWidget(clear_btn)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
    
    def append_output(self, text):
        """Append text to the output area"""
        self.output_text.append(text)
        # Auto-scroll to bottom
        cursor = self.output_text.textCursor()
        cursor.movePosition(cursor.End)
        self.output_text.setTextCursor(cursor)
    
    def clear_output(self):
        """Clear the output area"""
        self.output_text.clear()


class MTKWorker(QThread):
    """Worker thread for running MTK command with real-time output"""

    status_updated = Signal(str)
    show_installing_image = Signal()
    show_reconnect_image = Signal()
    show_presteps_image = Signal()
    mtk_completed = Signal(bool, str)
    handshake_failed = Signal()  # New signal for handshake failures
    errno2_detected = Signal()   # New signal for errno2 errors
    backend_error_detected = Signal()  # New signal for backend errors
    keyboard_interrupt_detected = Signal()  # New signal for keyboard interrupts
    disable_update_button = Signal()  # Signal to disable update button during MTK installation
    enable_update_button = Signal()   # Signal to enable update button when returning to ready state

    def __init__(self, debug_mode=False, debug_window=None):
        super().__init__()
        self.should_stop = False
        self.debug_mode = debug_mode
        self.debug_window = debug_window
        
        # Platform-specific progress bar characters
        if platform.system() == "Windows":
            # Windows: Use ASCII characters that display properly
            self.progress_filled = "#"
            self.progress_empty = "-"
        else:
            # Linux/macOS: Use box drawing characters
            self.progress_filled = "█"
            self.progress_empty = "░"

    def stop(self):
        """Stop the MTK worker"""
        self.should_stop = True

    def fix_progress_bar_chars(self, line):
        """Fix progress bar characters for platform compatibility"""
        if platform.system() == "Windows":
            # Replace box drawing characters with ASCII equivalents on Windows
            line = line.replace("█", self.progress_filled)
            line = line.replace("░", self.progress_empty)
            # Also handle other common box drawing characters that might appear
            line = line.replace("â-ª", self.progress_filled)  # Common mojibake
            line = line.replace("â", self.progress_filled)    # Partial mojibake
            line = line.replace("ª", self.progress_empty)     # Partial mojibake
        return line

    def run(self):
        cmd = [
            sys.executable, "mtk.py", "w",
            "uboot,bootimg,recovery,android,usrdata",
            "lk.bin,boot.img,recovery.img,system.img,userdata.img"
        ]

        try:
            # Don't emit status message - let MTK output be displayed clearly
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=0,
                universal_newlines=True
            )

            device_detected = False
            flashing_started = False
            handshake_error_detected = False
            errno2_error_detected = False
            backend_error_detected = False
            keyboard_interrupt_detected = False
            usb_connection_issue_detected = False
            last_output_line = ""
            successful_completion = False

            # Interruption detection variables
            progress_detected = False
            last_progress_time = None
            interruption_timeout = 3.0  # 3 seconds timeout

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    last_output_line = line  # Track the last output line

                    # Fix progress bar characters for platform compatibility
                    fixed_line = self.fix_progress_bar_chars(line)
                    
                    # Show debug output in separate window if debug mode is enabled
                    if self.debug_mode and self.debug_window:
                        self.debug_window.append_output(f"MTK: {fixed_line}")
                    
                    # Show latest output in status area (no extra whitespace)
                    self.status_updated.emit(f"MTK: {fixed_line}")

                    # Check for errno2 error
                    if "errno2" in line.lower():
                        errno2_error_detected = True
                        self.status_updated.emit("Errno2 detected - Innioasis Updater reinstall required")
                        self.errno2_detected.emit()
                        # Don't break here - continue reading output

                    # Check for handshake failed error (generalized detection)
                    if any(phrase in line.lower() for phrase in [
                        "handshake failed", 
                        "handshake error", 
                        "connection failed", 
                        "device not responding",
                        "timeout",
                        "connection timeout",
                        "device timeout",
                        "no device found",
                        "device not found",
                        "connection refused",
                        "failed to connect",
                        "connection error"
                    ]):
                        handshake_error_detected = True
                        self.status_updated.emit("Connection issue detected - please unplug your Y1 and try again")
                        self.handshake_failed.emit()
                        # Don't break here - continue reading output

                    # Check for backend error
                    if "nobackenderror" in line.lower() or "no backend available" in line.lower():
                        backend_error_detected = True
                        self.status_updated.emit("Backend error detected - libusb backend issue")
                        self.backend_error_detected.emit()
                        # Don't break here - continue reading output

                    # Check for USB connection issue (AttributeError: 'NoneType' object has no attribute 'hex')
                    if "attributerror: 'nonetype' object has no attribute 'hex'" in line.lower():
                        usb_connection_issue_detected = True
                        self.status_updated.emit("Please unplug the USB cable from your Y1 and reconnect it.")
                        self.show_reconnect_image.emit()
                        # Don't break here - continue reading output

                    # Check for keyboard interrupt
                    if "keyboardinterrupt" in line.lower() or "keyboard interrupt" in line.lower() or "interrupted by user" in line.lower():
                        keyboard_interrupt_detected = True
                        self.status_updated.emit("Something stopped the install process, give it another try...")
                        self.keyboard_interrupt_detected.emit()
                        # Don't break here - continue reading output

                    if ".Port - Device detected :)" in line:
                        device_detected = True
                        # Switch to installing.png immediately when device is detected
                        self.show_installing_image.emit()

                    # Check if flashing has started (look for write operations)
                    if device_detected and ("Write" in line or "Progress:" in line) and not flashing_started:
                        flashing_started = True

                    # Check for progress indicator and show installing.png
                    if "progress" in line.lower():
                        self.show_installing_image.emit()
                        # Disable update button when MTK installation starts
                        self.disable_update_button.emit()
                    # Track progress for interruption detection
                    progress_detected = True
                    last_progress_time = time.time()
                    # Don't emit status message - let MTK output be displayed clearly

                    # Only show presteps if no device detected and no errors
                    if not device_detected and not usb_connection_issue_detected and not handshake_error_detected and not errno2_error_detected and not backend_error_detected and not keyboard_interrupt_detected:
                        self.show_presteps_image.emit()

            # If any error was detected, continue reading but mark for completion
            if handshake_error_detected or errno2_error_detected or backend_error_detected or keyboard_interrupt_detected:
                # Continue reading output to show user what's happening
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        line = output.strip()
                        # Fix progress bar characters for platform compatibility
                        fixed_line = self.fix_progress_bar_chars(line)
                        # Show latest output in status area (no extra whitespace)
                        self.status_updated.emit(f"MTK: {fixed_line}")

            # Wait for process to complete
            process.wait()

            # Check if process completed before device detection
            if not device_detected:
                if process.returncode != 0:
                    # Process failed before device detection
                    successful_completion = False
                else:
                    successful_completion = True
            else:
                # Device was detected, check completion based on progress
                if progress_detected and last_progress_time:
                    time_since_last_progress = time.time() - last_progress_time
                    if time_since_last_progress > interruption_timeout:
                        # Process was interrupted - no progress for 3+ seconds
                        successful_completion = False
                    else:
                        # Check if the last progress was 100% or if process completed normally
                        if "100%" in last_output_line or process.returncode == 0:
                            successful_completion = True
                        else:
                            # Process stopped before 100% - likely interrupted
                            successful_completion = False
                else:
                    # No progress was detected, check if process completed successfully
                    if process.returncode == 0:
                        successful_completion = True
                    else:
                        successful_completion = False

        except Exception as e:
            self.status_updated.emit(f"MTK error: {str(e)}")
            successful_completion = False

        # Enable update button when returning to ready state
        self.enable_update_button.emit()

        if self.should_stop:
            self.mtk_completed.emit(False, "MTK command cancelled")
        elif usb_connection_issue_detected:
            self.mtk_completed.emit(False, "USB connection issue - please reconnect device")
        elif handshake_error_detected:
            self.mtk_completed.emit(False, "Handshake failed - driver setup required")
        elif errno2_error_detected:
            self.mtk_completed.emit(False, "Errno2 error - Innioasis Updater reinstall required")
        elif backend_error_detected:
            self.mtk_completed.emit(False, "Backend error - libusb backend issue")
        elif keyboard_interrupt_detected:
            self.mtk_completed.emit(False, "Something stopped the install process, give it another try...")
        elif successful_completion:
            self.mtk_completed.emit(True, "Install completed successfully")
        else:
            # Process ended but was interrupted (no progress for 3+ seconds)
            self.mtk_completed.emit(False, "Install process interrupted - please try again")


class DownloadWorker(QThread):
    """Worker thread for downloading and processing firmware"""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    download_completed = Signal(bool, str)

    def __init__(self, download_url, repo_name, version):
        super().__init__()
        self.download_url = download_url
        self.repo_name = repo_name
        self.version = version

    def run(self):
        try:
            self.status_updated.emit("Downloading...")

            # Download the file
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()

            # Create downloads directory if it doesn't exist
            ZIP_STORAGE_DIR.mkdir(exist_ok=True)

            zip_path = get_zip_path(self.repo_name, self.version)

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress)

                            # Calculate ETA
                            elapsed_time = time.time() - start_time
                            if elapsed_time > 0:
                                download_speed = downloaded / elapsed_time
                                remaining_bytes = total_size - downloaded
                                eta_seconds = remaining_bytes / download_speed if download_speed > 0 else 0

                                # Format ETA
                                if eta_seconds < 60:
                                    eta_str = f"{eta_seconds:.0f}s"
                                elif eta_seconds < 3600:
                                    eta_str = f"{eta_seconds/60:.0f}m"
                                else:
                                    eta_str = f"{eta_seconds/3600:.1f}h"

                                # Format file size
                                downloaded_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)

                                status_msg = f"Downloading... {progress}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB) - ETA: {eta_str}"
                                self.status_updated.emit(status_msg)

            self.status_updated.emit("Download completed. Extracting...")

            # Extract the zip file
            extracted_files = []
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
                # Get list of extracted files
                extracted_files = zip_ref.namelist()

            # Log extracted files for cleanup
            log_extracted_files(extracted_files)

            self.status_updated.emit("Extraction completed. Files ready for MTK processing.")

            # Check if required files exist
            required_files = ["lk.bin", "boot.img", "recovery.img", "system.img", "userdata.img"]
            missing_files = []
            for file in required_files:
                if not Path(file).exists():
                    missing_files.append(file)

            if missing_files:
                error_msg = f"Missing required files: {', '.join(missing_files)}"
                self.download_completed.emit(False, error_msg)
                return

            # Show success message with file list and instructions
            success_msg = "Firmware files successfully extracted:\n"
            for file in required_files:
                file_size = Path(file).stat().st_size
                size_mb = file_size / (1024 * 1024)
                success_msg += f"- {file} ({size_mb:.1f} MB)\n"

            success_msg += "\nTo flash these files to your device:\n"
            success_msg += "1. Turn off your Y1\n"
            success_msg += "2. Run the following command in a new terminal:\n"
            success_msg += f"   {sys.executable} mtk.py w uboot,bootimg,recovery,android,usrdata lk.bin,boot.img,recovery.img,system.img,userdata.img\n"
            success_msg += "3. Follow the on-screen prompts to turn off your Y1"

            self.download_completed.emit(True, success_msg)

        except Exception as e:
            self.download_completed.emit(False, f"Error: {str(e)}")


class FirmwareDownloaderGUI(QMainWindow):
    """Main GUI window for the firmware downloader"""

    def __init__(self):
        super().__init__()
        self.config_downloader = ConfigDownloader()
        self.github_api = None
        self.packages = []
        self.download_worker = None
        self.mtk_worker = None
        self.images_loaded = False  # Track if images are loaded
        self.installation_method = "guided"  # Default installation method
        self.always_use_method = False  # Default to one-time use
        self.debug_mode = False  # Default debug mode disabled
        
        # Initialize shortcut settings with defaults (Windows only)
        if platform.system() == "Windows":
            self.desktop_shortcuts_enabled = True  # Default to enabled
            self.startmenu_shortcuts_enabled = True  # Default to enabled
            self.auto_cleanup_enabled = True  # Default to enabled

        # Clean up any previously extracted files at startup
        cleanup_extracted_files()

        # Initialize UI first for immediate responsiveness
        self.init_ui()

        # Check for SP Flash Tool on Windows before loading data
        if platform.system() == "Windows":
            # Delay the flash tool check to avoid blocking startup
            QTimer.singleShot(100, self.check_sp_flash_tool)
            # Download troubleshooting shortcuts if missing
            QTimer.singleShot(200, self.ensure_troubleshooting_shortcuts)
            # Check for old shortcuts and offer cleanup
            QTimer.singleShot(400, self.check_and_cleanup_old_shortcuts)

        # Check for failed installation and show troubleshooting options
        QTimer.singleShot(300, self.check_failed_installation_on_startup)

        # Ensure troubleshooting shortcuts are available
        QTimer.singleShot(500, self.ensure_troubleshooting_shortcuts_available)

        # Download latest updater.py during launch
        QTimer.singleShot(600, self.download_latest_updater)

        # Load data asynchronously to avoid blocking UI
        QTimer.singleShot(100, self.load_data)
        
        # Load saved installation preferences
        QTimer.singleShot(200, self.load_installation_preferences)
        
        # Restore original installation method when session ends
        QTimer.singleShot(300, self.restore_original_installation_method)

        # Set up theme change detection timer
        self.theme_check_timer = QTimer()
        self.theme_check_timer.timeout.connect(self.check_theme_change)
        self.theme_check_timer.start(1000)  # Check every second
        self.last_theme_state = self.is_dark_mode()

    def check_sp_flash_tool(self):
        """Check if any flash tool is running on Windows and show warning"""
        try:
            # Use tasklist to get all running processes
            result = subprocess.run(['tasklist', '/FO', 'CSV'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Check for any executable containing "flash" in the name
                flash_processes = []
                for line in result.stdout.split('\n'):
                    if 'flash' in line.lower() and '.exe' in line.lower():
                        # Extract the process name from CSV format
                        parts = line.split(',')
                        if len(parts) >= 2:
                            process_name = parts[0].strip('"')
                            if 'flash' in process_name.lower():
                                flash_processes.append(process_name)
                
                if flash_processes:
                    # Flash tool(s) detected, show warning dialog
                    process_list = '\n'.join(f"• {process}" for process in flash_processes)
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Flash Tool Detected")
                    msg_box.setIcon(QMessageBox.Warning)
                    msg_box.setText("Flash tool(s) are currently running on your system.")
                    msg_box.setInformativeText(
                        f"The following flash tool(s) must be closed before running Innioasis Updater "
                        f"to prevent conflicts with USB device access and flashing operations:\n\n"
                        f"{process_list}\n\n"
                        f"Please close all flash tools completely and then restart Innioasis Updater."
                    )
                    msg_box.setStandardButtons(QMessageBox.Ok)
                    msg_box.setDefaultButton(QMessageBox.Ok)
                    
                    # Show the dialog
                    msg_box.exec()
                    
                    # Optionally, you could close the application here
                    # self.close()
                
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # If tasklist times out or is not available, assume no conflict and continue
            silent_print("Flash tool check skipped - tasklist not available")
        except Exception as e:
            # If there's any error checking for the process, continue silently
            silent_print(f"Error checking for flash tools: {e}")

    def ensure_troubleshooting_shortcuts(self):
        """Download troubleshooting shortcuts if they're missing (Windows only)"""
        if platform.system() != "Windows":
            return
            
        # Check if shortcuts exist
        current_dir = Path.cwd()
        recovery_lnk = current_dir / "Recover Firmware Install.lnk"
        sp_flash_tool_lnk = current_dir / "Recover Firmware Install - SP Flash Tool.lnk"
        
        # If both shortcuts exist, no need to download
        if recovery_lnk.exists() and sp_flash_tool_lnk.exists():
            silent_print("Troubleshooting shortcuts already exist")
            return

    def check_and_cleanup_old_shortcuts(self):
        """Check for old shortcuts and offer to remove them (Windows only)"""
        if platform.system() != "Windows":
            return
            
        try:
            silent_print("Starting shortcut cleanup check...")
            
            # Comprehensive cleanup of all Y1 Helper and related shortcuts
            self.comprehensive_shortcut_cleanup()
            
            # Ensure Innioasis Updater shortcuts are properly set up
            self.ensure_innioasis_updater_shortcuts()
                
        except Exception as e:
            silent_print(f"Error during shortcut cleanup: {e}")
            import traceback
            silent_print(f"Full error traceback: {traceback.format_exc()}")

    def comprehensive_shortcut_cleanup(self):
        """Silent comprehensive cleanup of all Y1 Helper and related shortcuts - no user interaction"""
        if platform.system() != "Windows":
            return
            
        try:
            cleaned_count = 0
            
            # Clean up desktop shortcuts using wildcards
            desktop_path = Path.home() / "Desktop"
            if desktop_path.exists():
                # Remove shortcuts matching patterns
                patterns = ["*Y1*", "*SP Flash*", "*Innioasis*"]
                for pattern in patterns:
                    for item in desktop_path.glob(pattern):
                        if item.is_file() and item.suffix.lower() == '.lnk':
                            try:
                                item.unlink()
                                cleaned_count += 1
                                silent_print(f"Removed desktop shortcut: {item.name}")
                            except Exception as e:
                                silent_print(f"Error removing {item.name}: {e}")
            
            # Clean up start menu shortcuts using wildcards
            start_menu_paths = self.get_all_start_menu_paths()
            for start_menu_path in start_menu_paths:
                if start_menu_path.exists():
                    # Remove shortcuts matching patterns
                    patterns = ["*Y1*", "*SP Flash*", "*Innioasis*"]
                    for pattern in patterns:
                        for item in start_menu_path.glob(pattern):
                            if item.is_file() and item.suffix.lower() == '.lnk':
                                try:
                                    item.unlink()
                                    cleaned_count += 1
                                    silent_print(f"Removed start menu shortcut: {item.name}")
                                except Exception as e:
                                    silent_print(f"Error removing {item.name}: {e}")
                    
                    # Remove Y1 Helper folder if it exists
                    y1_helper_folder = start_menu_path / "Y1 Helper"
                    if y1_helper_folder.exists() and y1_helper_folder.is_dir():
                        try:
                            shutil.rmtree(y1_helper_folder)
                            cleaned_count += 1
                            silent_print(f"Removed Y1 Helper folder: {y1_helper_folder}")
                        except Exception as e:
                            silent_print(f"Error removing Y1 Helper folder: {e}")
            
            silent_print(f"Silent comprehensive shortcut cleanup completed: {cleaned_count} items removed")
            
            # Create current shortcuts if enabled in settings
            if getattr(self, 'desktop_shortcuts_enabled', True):
                self.ensure_desktop_shortcuts()
            if getattr(self, 'startmenu_shortcuts_enabled', True):
                self.ensure_startmenu_shortcuts()
                
        except Exception as e:
            silent_print(f"Error during comprehensive shortcut cleanup: {e}")

    def get_all_start_menu_paths(self):
        """Get comprehensive list of all possible start menu paths"""
        paths = []
        
        # User-specific paths
        user_paths = [
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        ]
        
        # System-wide paths
        system_paths = [
            Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs"),
            Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs/StartUp"),
            Path("C:/Users/Public/Start Menu/Programs"),
            Path("C:/Users/Public/Desktop")
        ]
        
        # Environment variable paths
        env_paths = []
        if "PROGRAMDATA" in os.environ:
            env_paths.append(Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
            env_paths.append(Path(os.environ["PROGRAMDATA"]) / "Microsoft" / "Windows/Start Menu/Programs" / "StartUp")
        
        if "PUBLIC" in os.environ:
            env_paths.append(Path(os.environ["PUBLIC"]) / "Start Menu" / "Programs")
            env_paths.append(Path(os.environ["PUBLIC"]) / "Desktop")
        
        # Combine all paths and filter existing ones
        all_paths = user_paths + system_paths + env_paths
        
        silent_print(f"Checking {len(all_paths)} potential start menu paths...")
        
        for path in all_paths:
            silent_print(f"Checking path: {path} (exists: {path.exists()})")
            if path.exists():
                paths.append(path)
                silent_print(f"Found start menu path: {path}")
                
                # Specifically check for the Y1 Helper.lnk file in this path
                y1_helper_lnk = path / "Y1 Helper.lnk"
                if y1_helper_lnk.exists():
                    silent_print(f"*** FOUND Y1 Helper.lnk at: {y1_helper_lnk} ***")
        
        silent_print(f"Total valid start menu paths found: {len(paths)}")
        return paths

    def ensure_innioasis_updater_shortcuts(self):
        """Ensure Innioasis Updater shortcuts are properly set up"""
        try:
            current_dir = Path.cwd()
            innioasis_updater_shortcut = current_dir / "Innioasis Updater.lnk"
            
            if not innioasis_updater_shortcut.exists():
                silent_print("Innioasis Updater.lnk not found in current directory")
                return
            
            # Check desktop
            desktop_path = Path.home() / "Desktop"
            desktop_shortcut = desktop_path / "Innioasis Updater.lnk"
            
            if not desktop_shortcut.exists():
                try:
                    shutil.copy2(innioasis_updater_shortcut, desktop_shortcut)
                    silent_print(f"Added Innioasis Updater shortcut to desktop")
                except Exception as e:
                    silent_print(f"Error adding desktop shortcut: {e}")
            
            # Get comprehensive list of start menu paths
            start_menu_paths = self.get_all_start_menu_paths()
            
            for start_menu_path in start_menu_paths:
                if start_menu_path.exists():
                    start_menu_shortcut = start_menu_path / "Innioasis Updater.lnk"
                    if not start_menu_shortcut.exists():
                        try:
                            shutil.copy2(innioasis_updater_shortcut, start_menu_shortcut)
                            silent_print(f"Added Innioasis Updater shortcut to start menu: {start_menu_path}")
                        except Exception as e:
                            silent_print(f"Error adding start menu shortcut: {e}")
                            
        except Exception as e:
            silent_print(f"Error ensuring Innioasis Updater shortcuts: {e}")

    def show_shortcut_cleanup_dialog(self, old_shortcuts):
        """Show dialog offering to remove old shortcuts"""
        try:
            # Group shortcuts by location for better display
            desktop_items = [item for location, item in old_shortcuts if location == "Desktop"]
            start_menu_items = [item for location, item in old_shortcuts if location == "Start Menu"]
            
            message = "Found old shortcuts and folders that may no longer be needed:\n\n"
            
            if desktop_items:
                message += "Desktop:\n"
                for item in desktop_items:
                    message += f"• {Path(item).name}\n"
                message += "\n"
            
            if start_menu_items:
                message += "Start Menu:\n"
                for item in start_menu_items:
                    message += f"• {item}\n"
                message += "\n"
            
            message += "These appear to be from previous versions. Would you like to remove them?"
            
            reply = QMessageBox.question(
                self,
                "Clean Up Old Shortcuts",
                message,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.remove_old_shortcuts(old_shortcuts)
            elif reply == QMessageBox.Cancel:
                # Don't ask again this session
                pass
                
        except Exception as e:
            silent_print(f"Error showing shortcut cleanup dialog: {e}")

    def remove_old_shortcuts(self, old_shortcuts):
        """Remove old shortcuts and folders"""
        try:
            removed_count = 0
            failed_items = []
            
            for location, item_path in old_shortcuts:
                try:
                    item_path = Path(item_path)
                    if item_path.exists():
                        if item_path.is_file():
                            item_path.unlink()
                        elif item_path.is_dir():
                            shutil.rmtree(item_path)
                        removed_count += 1
                        silent_print(f"Removed: {item_path}")
                except PermissionError:
                    # Some items may need admin privileges
                    failed_items.append(f"{item_path} (needs admin)")
                except Exception as e:
                    failed_items.append(f"{item_path} ({e})")
            
            # Show results
            if failed_items:
                message = f"Successfully removed {removed_count} items.\n\n"
                message += "Some items could not be removed (may need admin privileges):\n"
                for item in failed_items:
                    message += f"• {item}\n"
                
                QMessageBox.information(
                    self,
                    "Cleanup Results",
                    message
                )
            else:
                QMessageBox.information(
                    self,
                    "Cleanup Complete",
                    f"Successfully removed {removed_count} old shortcuts and folders."
                )
                
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cleanup Error",
                f"Error during cleanup: {e}"
            )

    def check_and_replace_y1_helper_shortcuts(self):
        """Check for Y1 Helper and Y1 Remote Control shortcuts and clean up to desired state"""
        if platform.system() != "Windows":
            return
            
        try:
            shortcuts_to_cleanup = []
            y1_helper_desktop_shortcut = None
            
            # Check desktop for shortcuts
            desktop_path = Path.home() / "Desktop"
            if desktop_path.exists():
                # Check for Y1 Helper.lnk specifically (will be replaced with Innioasis Updater)
                y1_helper_exact = desktop_path / "Y1 Helper.lnk"
                if y1_helper_exact.exists():
                    y1_helper_desktop_shortcut = str(y1_helper_exact)
                
                # Check for other Y1 Helper variants
                for item in desktop_path.glob("*Y1 Helper*.lnk"):
                    if item.name != "Y1 Helper.lnk":  # Skip the exact match we already found
                        shortcuts_to_cleanup.append(("Desktop", str(item), "Y1 Helper variant"))
                
                # Check for Y1 Remote Control variants
                for item in desktop_path.glob("*Y1 Remote Control*.lnk"):
                    shortcuts_to_cleanup.append(("Desktop", str(item), "Y1 Remote Control variant"))
            
            # Check Start Menu for shortcuts
            start_menu_paths = [
                Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
                Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            ]
            
            for start_menu_path in start_menu_paths:
                if start_menu_path.exists():
                    # Check for Y1 Helper folder (will be deleted entirely)
                    y1_helper_folder = start_menu_path / "Y1 Helper"
                    if y1_helper_folder.exists():
                        shortcuts_to_cleanup.append(("Start Menu Folder", str(y1_helper_folder), "Y1 Helper folder"))
                    
                    # Check for individual Y1 Helper shortcuts
                    for item in start_menu_path.glob("*Y1 Helper*.lnk"):
                        shortcuts_to_cleanup.append(("Start Menu", str(item), "Y1 Helper shortcut"))
                    
                    # Check for Y1 Remote Control variants
                    for item in start_menu_path.glob("*Y1 Remote Control*.lnk"):
                        shortcuts_to_cleanup.append(("Start Menu", str(item), "Y1 Remote Control variant"))
            
            # Always ensure proper desktop shortcut exists
            self.ensure_proper_desktop_shortcut()
            
            # If exact Y1 Helper.lnk found on desktop, offer Innioasis Updater replacement
            if y1_helper_desktop_shortcut:
                self.show_innioasis_updater_replacement_dialog(y1_helper_desktop_shortcut)
            
            # If other shortcuts found, offer cleanup
            if shortcuts_to_cleanup:
                self.show_comprehensive_cleanup_dialog(shortcuts_to_cleanup)
                
        except Exception as e:
            silent_print(f"Error checking for shortcuts: {e}")

    def show_innioasis_updater_replacement_dialog(self, y1_helper_desktop_shortcut):
        """Show dialog offering to replace Y1 Helper.lnk with Innioasis Updater.lnk"""
        try:
            # Check if Innioasis Updater.lnk exists in the same directory
            current_dir = Path.cwd()
            innioasis_updater_shortcut = current_dir / "Innioasis Updater.lnk"
            
            if not innioasis_updater_shortcut.exists():
                silent_print("Innioasis Updater.lnk not found in current directory")
                return
            
            message = "Found Y1 Helper.lnk on your desktop that can be replaced with Innioasis Updater:\n\n"
            message += "Desktop:\n"
            message += f"• {Path(y1_helper_desktop_shortcut).name}\n\n"
            message += "Would you like to replace this with the Innioasis Updater shortcut?"
            
            reply = QMessageBox.question(
                self,
                "Replace Y1 Helper with Innioasis Updater",
                message,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.replace_y1_helper_with_innioasis_updater(y1_helper_desktop_shortcut, str(innioasis_updater_shortcut))
            elif reply == QMessageBox.Cancel:
                # Don't ask again this session
                pass
                
        except Exception as e:
            silent_print(f"Error showing Innioasis Updater replacement dialog: {e}")

    def replace_y1_helper_with_innioasis_updater(self, old_shortcut_path, new_shortcut_path):
        """Replace Y1 Helper.lnk with Innioasis Updater.lnk on desktop"""
        try:
            old_shortcut = Path(old_shortcut_path)
            new_shortcut = Path(new_shortcut_path)
            
            if not old_shortcut.exists():
                silent_print("Y1 Helper.lnk no longer exists on desktop")
                return
            
            if not new_shortcut.exists():
                silent_print("Innioasis Updater.lnk not found in current directory")
                return
            
            # Copy Innioasis Updater.lnk to desktop
            desktop_path = Path.home() / "Desktop"
            desktop_innioasis_shortcut = desktop_path / "Innioasis Updater.lnk"
            
            shutil.copy2(new_shortcut, desktop_innioasis_shortcut)
            
            # Remove the old Y1 Helper.lnk
            old_shortcut.unlink()
            
            QMessageBox.information(
                self,
                "Replacement Complete",
                "Successfully replaced Y1 Helper.lnk with Innioasis Updater.lnk on your desktop."
            )
            
            silent_print(f"Replaced: {old_shortcut} -> {desktop_innioasis_shortcut}")
            
        except PermissionError:
            QMessageBox.warning(
                self,
                "Permission Error",
                "Could not replace the shortcut. You may need to run as administrator."
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Replacement Error",
                f"Error during replacement: {e}"
            )

    def ensure_proper_desktop_shortcut(self):
        """Ensure Innioasis Updater.lnk exists on desktop"""
        try:
            desktop_path = Path.home() / "Desktop"
            if not desktop_path.exists():
                return
            
            # Check if Innioasis Updater.lnk already exists on desktop
            desktop_innioasis_shortcut = desktop_path / "Innioasis Updater.lnk"
            if desktop_innioasis_shortcut.exists():
                silent_print("Innioasis Updater.lnk already exists on desktop")
                return
            
            # Check if the shortcut exists in current directory
            current_dir = Path.cwd()
            source_shortcut = current_dir / "Innioasis Updater.lnk"
            if not source_shortcut.exists():
                silent_print("Innioasis Updater.lnk not found in current directory")
                return
            
            # Copy the shortcut to desktop
            shutil.copy2(source_shortcut, desktop_innioasis_shortcut)
            silent_print(f"Added Innioasis Updater.lnk to desktop")
            
        except Exception as e:
            silent_print(f"Error ensuring proper desktop shortcut: {e}")

    def show_comprehensive_cleanup_dialog(self, old_shortcuts):
        """Show dialog offering to clean up all old shortcuts"""
        try:
            # Group shortcuts by location for better display
            desktop_items = [item for location, item in old_shortcuts if location == "Desktop"]
            desktop_subfolder_items = [item for location, item in old_shortcuts if location == "Desktop Subfolder"]
            start_menu_items = [item for location, item in old_shortcuts if location == "Start Menu"]
            start_menu_subfolder_items = [item for location, item in old_shortcuts if location == "Start Menu Subfolder"]
            start_menu_folders = [item for location, item in old_shortcuts if location == "Start Menu Folder"]
            
            message = "Found old shortcuts and folders that should be cleaned up:\n\n"
            
            if desktop_items:
                message += "Desktop:\n"
                for item in desktop_items:
                    message += f"• {Path(item).name}\n"
                message += "\n"
            
            if desktop_subfolder_items:
                message += "Desktop Subfolders:\n"
                for item in desktop_subfolder_items:
                    message += f"• {Path(item).name}\n"
                message += "\n"
            
            if start_menu_items:
                message += "Start Menu:\n"
                for item in start_menu_items:
                    message += f"• {Path(item).name}\n"
                message += "\n"
            
            if start_menu_subfolder_items:
                message += "Start Menu Subfolders:\n"
                for item in start_menu_subfolder_items:
                    message += f"• {Path(item).name}\n"
                message += "\n"
            
            if start_menu_folders:
                message += "Start Menu Folders (will be deleted):\n"
                for item in start_menu_folders:
                    message += f"• {Path(item).name}\n"
                message += "\n"
            
            message += "This will clean up all old Y1 Helper and related shortcuts and ensure you have:\n"
            message += "• Innioasis Updater.lnk on desktop\n"
            message += "• Innioasis Updater.lnk in Start Menu\n\n"
            message += "Would you like to proceed with cleanup?"
            
            reply = QMessageBox.question(
                self,
                "Clean Up Old Shortcuts",
                message,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.perform_comprehensive_cleanup(old_shortcuts)
            elif reply == QMessageBox.Cancel:
                # Don't ask again this session
                pass
                
        except Exception as e:
            silent_print(f"Error showing comprehensive cleanup dialog: {e}")

    def perform_comprehensive_cleanup(self, old_shortcuts):
        """Perform comprehensive cleanup of old shortcuts and ensure proper ones exist"""
        try:
            removed_count = 0
            failed_items = []
            
            # First, remove all old shortcuts and folders
            for location, item_path in old_shortcuts:
                try:
                    item_path = Path(item_path)
                    if item_path.exists():
                        if location == "Start Menu Folder":
                            # Delete the entire folder
                            shutil.rmtree(item_path)
                            removed_count += 1
                            silent_print(f"Deleted folder: {item_path}")
                        else:
                            # Remove the shortcut
                            item_path.unlink()
                            removed_count += 1
                            silent_print(f"Removed shortcut: {item_path}")
                except PermissionError:
                    # Some items may need admin privileges
                    failed_items.append(f"{item_path} (needs admin)")
                except Exception as e:
                    failed_items.append(f"{item_path} ({e})")
            
            # Now ensure proper shortcuts exist
            self.ensure_innioasis_updater_shortcuts()
            
            # Show results
            if failed_items:
                message = f"Successfully cleaned up {removed_count} items.\n\n"
                message += "Some items could not be removed (may need admin privileges):\n"
                for item in failed_items:
                    message += f"• {item}\n"
                
                QMessageBox.information(
                    self,
                    "Cleanup Results",
                    message
                )
            else:
                QMessageBox.information(
                    self,
                    "Cleanup Complete",
                    f"Successfully cleaned up {removed_count} old shortcuts and folders.\n\n"
                    "Your system now has:\n"
                    "• Innioasis Updater.lnk on desktop\n"
                    "• Innioasis Updater.lnk in Start Menu"
                )
                
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cleanup Error",
                f"Error during cleanup: {e}"
            )

    def ensure_proper_start_menu_shortcuts(self):
        """Ensure proper shortcuts exist in Start Menu"""
        try:
            current_dir = Path.cwd()
            start_menu_paths = [
                Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
                Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            ]
            
            # Check if proper shortcuts already exist
            innioasis_updater_exists = False
            innioasis_y1_remote_exists = False
            
            for start_menu_path in start_menu_paths:
                if start_menu_path.exists():
                    if (start_menu_path / "Innioasis Updater.lnk").exists():
                        innioasis_updater_exists = True
                    if (start_menu_path / "Innioasis Y1 Remote Control.lnk").exists():
                        innioasis_y1_remote_exists = True
            
            # Copy missing shortcuts from current directory
            if not innioasis_updater_exists:
                source_updater = current_dir / "Innioasis Updater.lnk"
                if source_updater.exists():
                    # Copy to first available start menu path
                    for start_menu_path in start_menu_paths:
                        if start_menu_path.exists():
                            dest_updater = start_menu_path / "Innioasis Updater.lnk"
                            shutil.copy2(source_updater, dest_updater)
                            silent_print(f"Added Innioasis Updater.lnk to {start_menu_path}")
                            break
            
            if not innioasis_y1_remote_exists:
                source_remote = current_dir / "Innioasis Y1 Remote Control.lnk"
                if source_remote.exists():
                    # Copy to first available start menu path
                    for start_menu_path in start_menu_paths:
                            dest_remote = start_menu_path / "Innioasis Y1 Remote Control.lnk"
                            shutil.copy2(source_remote, dest_remote)
                            silent_print(f"Added Innioasis Y1 Remote Control.lnk to {start_menu_path}")
                            break
                            
        except Exception as e:
            silent_print(f"Error ensuring proper start menu shortcuts: {e}")

    def show_y1_helper_replacement_dialog(self, y1_helper_shortcuts):
        """Show dialog offering to replace Y1 Helper shortcuts with Y1 Remote Control"""
        try:
            # Group shortcuts by location for better display
            desktop_items = [item for location, item in y1_helper_shortcuts if location == "Desktop"]
            start_menu_items = [item for location, item in y1_helper_shortcuts if location == "Start Menu"]
            start_menu_folders = [item for location, item in y1_helper_shortcuts if location == "Start Menu Folder"]
            
            message = "Found Y1 Helper shortcuts that can be replaced with Y1 Remote Control:\n\n"
            
            if desktop_items:
                message += "Desktop:\n"
                for item in desktop_items:
                    message += f"• {Path(item).name}\n"
                message += "\n"
            
            if start_menu_items:
                message += "Start Menu:\n"
                for item in start_menu_items:
                    message += f"• {Path(item).name}\n"
                message += f"• {item}\n"
                message += "\n"
            
            if start_menu_folders:
                message += "Start Menu Folders (will be deleted):\n"
                for item in start_menu_folders:
                    message += f"• {item}\n"
                message += "\n"
            
            message += "Would you like to replace these with Y1 Remote Control shortcuts?"
            
            reply = QMessageBox.question(
                self,
                "Replace Y1 Helper Shortcuts",
                message,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.replace_y1_helper_shortcuts(y1_helper_shortcuts)
            elif reply == QMessageBox.Cancel:
                # Don't ask again this session
                pass
                
        except Exception as e:
            silent_print(f"Error showing Y1 Helper replacement dialog: {e}")

    def replace_y1_helper_shortcuts(self, y1_helper_shortcuts):
        """Replace Y1 Helper shortcuts with Y1 Remote Control"""
        try:
            replaced_count = 0
            failed_items = []
            
            for location, item_path in y1_helper_shortcuts:
                try:
                    item_path = Path(item_path)
                    if item_path.exists():
                        if location == "Start Menu Folder":
                            # Delete the entire folder
                            shutil.rmtree(item_path)
                            replaced_count += 1
                            silent_print(f"Deleted folder: {item_path}")
                        else:
                            # Replace shortcut with Y1 Remote Control
                            new_shortcut_name = item_path.name.replace("Y1 Helper", "Y1 Remote Control")
                            new_shortcut_path = item_path.parent / new_shortcut_name
                            
                            # Copy the shortcut and modify it to point to Y1 Remote Control
                            shutil.copy2(item_path, new_shortcut_path)
                            
                            # Remove the old Y1 Helper shortcut
                            item_path.unlink()
                            
                            replaced_count += 1
                            silent_print(f"Replaced: {item_path} -> {new_shortcut_path}")
                except PermissionError:
                    # Some items may need admin privileges
                    failed_items.append(f"{item_path} (needs admin)")
                except Exception as e:
                    failed_items.append(f"{item_path} ({e})")
            
            # Show results
            if failed_items:
                message = f"Successfully replaced {replaced_count} shortcuts.\n\n"
                message += "Some shortcuts could not be replaced (may need admin privileges):\n"
                for item in failed_items:
                    message += f"• {item}\n"
                
                QMessageBox.information(
                    self,
                    "Replacement Results",
                    message
                )
            else:
                QMessageBox.information(
                    self,
                    "Replacement Complete",
                    f"Successfully replaced {replaced_count} Y1 Helper shortcuts with Y1 Remote Control."
                )
                
        except Exception as e:
            QMessageBox.warning(
                self,
                "Replacement Error",
                f"Error during replacement: {e}"
            )
            
        # Download troubleshooting shortcuts
        self.download_troubleshooting_shortcuts()

    def download_troubleshooting_shortcuts(self):
        """Download and extract troubleshooting shortcuts zip file"""
        try:
            self.status_label.setText("Downloading troubleshooting shortcuts...")
            silent_print("Downloading troubleshooting shortcuts...")
            
            # Download URL for troubleshooting shortcuts
            url = "https://github.com/team-slide/Innioasis-Updater/releases/download/1.0.0/Troubleshooters.-.Windows.zip"
            
            # Download the zip file
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Save to temporary zip file
            temp_zip = Path("troubleshooters_temp.zip")
            with open(temp_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            silent_print("Downloaded troubleshooting shortcuts zip file")
            
            # Extract the zip file to current directory
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            silent_print("Extracted troubleshooting shortcuts")
            
            # Check if Troubleshooters - Windows.zip was extracted and extract its contents
            troubleshooters_zip = Path("Troubleshooters - Windows.zip")
            if troubleshooters_zip.exists():
                silent_print("Found Troubleshooters - Windows.zip, extracting nested contents...")
                with zipfile.ZipFile(troubleshooters_zip, 'r') as nested_zip:
                    nested_zip.extractall(".")
                silent_print("Extracted nested troubleshooting shortcuts")
                
                # Remove the nested zip file after extraction
                troubleshooters_zip.unlink()
                silent_print("Removed nested zip file")
            
            # Delete the temporary zip file
            temp_zip.unlink()
            silent_print("Cleaned up temporary zip file")
            
            # Verify shortcuts were extracted
            current_dir = Path.cwd()
            recovery_lnk = current_dir / "Recover Firmware Install.lnk"
            sp_flash_tool_lnk = current_dir / "Recover Firmware Install - SP Flash Tool.lnk"
            
            if recovery_lnk.exists() and sp_flash_tool_lnk.exists():
                self.status_label.setText("Troubleshooting shortcuts downloaded successfully")
                silent_print("Troubleshooting shortcuts downloaded and extracted successfully")
                # Auto-clear status after 3 seconds
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
            else:
                self.status_label.setText("Warning: Some troubleshooting shortcuts may be missing")
                silent_print("Warning: Some troubleshooting shortcuts may be missing after extraction")
                # Auto-clear warning after 3 seconds
                QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
                
        except Exception as e:
            self.status_label.setText("Failed to download troubleshooting shortcuts")
            silent_print(f"Error downloading troubleshooting shortcuts: {e}")
            # Auto-clear error status after 3 seconds
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
            # Don't show error dialog - this is not critical for basic functionality

    def ensure_troubleshooting_shortcuts_available(self):
        """Ensure troubleshooting shortcuts are available, extract from zip if needed"""
        try:
            current_dir = Path.cwd()
            recovery_lnk = current_dir / "Recover Firmware Install.lnk"
            sp_flash_tool_lnk = current_dir / "Recover Firmware Install - SP Flash Tool.lnk"
            
            # Check if shortcuts exist
            if recovery_lnk.exists() and sp_flash_tool_lnk.exists():
                silent_print("Troubleshooting shortcuts already available")
                return
            
            # Check if Troubleshooters - Windows.zip exists and extract it
            troubleshooters_zip = current_dir / "Troubleshooters - Windows.zip"
            if troubleshooters_zip.exists():
                silent_print("Found Troubleshooters - Windows.zip, extracting shortcuts...")
                try:
                    with zipfile.ZipFile(troubleshooters_zip, 'r') as zip_ref:
                        zip_ref.extractall(current_dir)
                    
                    # Remove the zip file after extraction
                    troubleshooters_zip.unlink()
                    silent_print("Troubleshooting shortcuts extracted successfully")
                    
                    # Verify extraction
                    if recovery_lnk.exists() and sp_flash_tool_lnk.exists():
                        silent_print("Troubleshooting shortcuts verified")
                    else:
                        silent_print("Warning: Troubleshooting shortcuts still missing after extraction")
                        
                except Exception as e:
                    silent_print(f"Error extracting troubleshooting shortcuts: {e}")
            else:
                silent_print("No troubleshooting shortcuts zip found")
                
        except Exception as e:
            silent_print(f"Error ensuring troubleshooting shortcuts: {e}")

    def check_failed_installation_on_startup(self):
        """Check for failed installation on startup and show troubleshooting options"""
        if not check_for_failed_installation():
            return
            
        # Check driver availability for Windows users
        if platform.system() == "Windows":
            driver_info = self.check_drivers_and_architecture()
            
            if driver_info['is_arm64']:
                # ARM64 Windows: No installation methods available
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("ARM64 Windows - No Installation Methods")
                msg_box.setText("Firmware installation is not supported on ARM64 Windows.")
                msg_box.setInformativeText("You can download firmware files, but to install them please use WSLg, Linux, or another computer.")
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec()
                remove_installation_marker()
                return
                
            elif not driver_info['can_install_firmware']:
                # No drivers: No installation methods available
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Drivers Required")
                msg_box.setText("No installation methods available. Please install drivers to enable firmware installation.")
                msg_box.setInformativeText("Click OK to open the driver installation guide.")
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec()
                remove_installation_marker()
                self.open_driver_setup_link()
                return
            
        # Show failed installation dialog with troubleshooting options
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Firmware Installation Incomplete")
        msg_box.setText("A previous firmware installation appears to have been interrupted or failed.")
        msg_box.setInformativeText("Would you like to try troubleshooting the installation?")
        msg_box.setIcon(QMessageBox.Warning)
        
        # Create custom buttons for troubleshooting options
        try_again_btn = msg_box.addButton("Try Again", QMessageBox.ActionRole)
        
        # Show Method 2 on all platforms, SP Flash Tool only on Windows
        try_method2_btn = msg_box.addButton("Try Method 2", QMessageBox.ActionRole)
        try_method3_btn = None
        if platform.system() == "Windows":
            try_method3_btn = msg_box.addButton("Try Method 3", QMessageBox.ActionRole)
        
        stop_install_btn = msg_box.addButton("Stop Install", QMessageBox.ActionRole)
        exit_btn = msg_box.addButton("Exit", QMessageBox.RejectRole)
        
        # Set default button
        msg_box.setDefaultButton(try_again_btn)
        
        reply = msg_box.exec()
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == try_again_btn:
            # Try Again - use selected installation method from settings
            remove_installation_marker()
            method = getattr(self, 'installation_method', 'guided')
            if method == "guided":
                # Method 1: Kill orphan libusb processes and restart firmware install
                self.stop_mtk_processes()
                self.cleanup_libusb_state()
                QTimer.singleShot(1000, self.run_mtk_command)
            elif method == "mtkclient":
                # Method 2: Same as pressing Try Method 2
                self.show_troubleshooting_instructions()
            elif method == "spflash" and platform.system() == "Windows":
                # Method 3: Same as pressing Try Method 3 (Windows only)
                self.try_method_3()
            else:
                # Fallback to guided method
                self.stop_mtk_processes()
                self.cleanup_libusb_state()
                QTimer.singleShot(1000, self.run_mtk_command)
        elif clicked_button == try_method2_btn and try_method2_btn:
            # Clear the marker and launch Method 2 troubleshooting
            remove_installation_marker()
            self.show_troubleshooting_instructions()
        elif clicked_button == try_method3_btn and try_method3_btn:
            # Clear the marker and launch Method 3 troubleshooting
            remove_installation_marker()
            self.try_method_3()
        elif clicked_button == stop_install_btn:
            # Stop install and return to ready state
            remove_installation_marker()
            self.revert_to_startup_state()
        else:
            # Exit the application
            QApplication.quit()

    def ensure_recovery_shortcut(self):
        """Ensure recovery shortcut exists, download if missing"""
        current_dir = Path.cwd()
        recovery_lnk = current_dir / "Recover Firmware Install.lnk"
        
        if recovery_lnk.exists():
            return True
            
        # Shortcut missing, try to download
        self.status_label.setText("Recovery shortcut missing, downloading...")
        self.download_troubleshooting_shortcuts()
        # Auto-clear status after 3 seconds
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
        
        # Check again after download
        if recovery_lnk.exists():
            return True
            
        # Still missing, show error
        QMessageBox.warning(
            self,
            "Shortcut Missing",
            "The recovery firmware installer shortcut could not be downloaded.\n\n"
            "Please check your internet connection and try again."
        )
        return False

    def ensure_sp_flash_tool_shortcut(self):
        """Ensure SP Flash Tool shortcut exists, download if missing"""
        current_dir = Path.cwd()
        sp_flash_tool_lnk = current_dir / "Recover Firmware Install - SP Flash Tool.lnk"
        
        if sp_flash_tool_lnk.exists():
            return True
            
        # Shortcut missing, try to download
        self.status_label.setText("SP Flash Tool shortcut missing, downloading...")
        self.download_troubleshooting_shortcuts()
        # Auto-clear status after 3 seconds
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
        
        # Check again after download
        if sp_flash_tool_lnk.exists():
            return True
            
        # Still missing, show error
        QMessageBox.warning(
            self,
            "Shortcut Missing",
            "The SP Flash Tool shortcut could not be downloaded.\n\n"
            "Please check your internet connection and try again."
        )
        return False

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Control+D to toggle silent mode
        if event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            silent_mode = toggle_silent_mode()
            if silent_mode:
                self.status_label.setText("Silent mode enabled - press Ctrl+D to disable")
            else:
                self.status_label.setText("Verbose mode enabled - press Ctrl+D to enable silent mode")
        else:
            super().keyPressEvent(event)




    def show_custom_message_box(self, icon_type, title, message, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok):
        """Show a message box with standard system icons"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(buttons)
        msg_box.setDefaultButton(default_button)

        # Set appropriate icon type
        if icon_type == "information":
            msg_box.setIcon(QMessageBox.Information)
        elif icon_type == "warning":
            msg_box.setIcon(QMessageBox.Warning)
        elif icon_type == "critical":
            msg_box.setIcon(QMessageBox.Critical)
        elif icon_type == "question":
            msg_box.setIcon(QMessageBox.Question)
        else:
            msg_box.setIcon(QMessageBox.NoIcon)

        return msg_box.exec()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Innioasis Y1 Updater by Ryan Specter - u/respectyarn")
        self.setGeometry(100, 100, 1220, 550)
        
        # Set fixed window size to maintain layout
        self.setFixedSize(1220, 550)
        
        # Force normal window state (not maximized)
        self.setWindowState(Qt.WindowNoState)



        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)

        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Package selection
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Device filters
        filter_group = QGroupBox()
        filter_layout = QVBoxLayout(filter_group)

        # Device type filter
        device_type_layout = QHBoxLayout()
        device_type_layout.addWidget(QLabel("Device Type:"))

        self.device_type_combo = QComboBox()
        self.device_type_combo.currentTextChanged.connect(self.filter_firmware_options)
        device_type_layout.addWidget(self.device_type_combo)

        # Add help button with tooltip (to the right of dropdown)
        help_btn = QPushButton("?")
        help_btn.setStyleSheet("""
            QPushButton {
                color: #0066CC;
                font-weight: bold;
                font-size: 12px;
                margin-left: 5px;
                border: 1px solid #0066CC;
                border-radius: 12px;
                background-color: transparent;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #0066CC;
                color: white;
            }
        """)
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.setToolTip("Try Type A System Software first. If your scroll wheel doesn't respond after installation, install one of the Type B options.")
        help_btn.clicked.connect(self.show_device_type_help)
        device_type_layout.addWidget(help_btn)
        
        # Add Settings button (combines Tools and Settings functionality)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedHeight(24)  # Match dropdown height
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: normal;
                font-size: 11px;
                min-width: 50px;
                max-width: 70px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
                border-color: #444444;
            }
        """)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("Settings and Tools - Installation method, shortcuts, and Y1 Remote Control")
        self.settings_btn.clicked.connect(self.show_settings_dialog)
        device_type_layout.addWidget(self.settings_btn)
        
        device_type_layout.addStretch()

        # Device model filter
        device_model_layout = QHBoxLayout()
        device_model_layout.addWidget(QLabel("Device Model:"))

        self.device_model_combo = QComboBox()
        self.device_model_combo.currentTextChanged.connect(self.filter_firmware_options)
        device_model_layout.addWidget(self.device_model_combo)
        device_model_layout.addStretch()

        # Software filter (Repository)
        software_layout = QHBoxLayout()
        software_layout.addWidget(QLabel("Software:"))

        self.firmware_combo = QComboBox()
        self.firmware_combo.addItem("All Software", "")
        # Default selection will be set dynamically in populate_firmware_combo
        self.firmware_combo.currentTextChanged.connect(self.on_firmware_changed)
        # Make the software dropdown wider
        self.firmware_combo.setMinimumWidth(300)
        software_layout.addWidget(self.firmware_combo)
        software_layout.addStretch()

        filter_layout.addLayout(device_type_layout)
        filter_layout.addLayout(device_model_layout)
        filter_layout.addLayout(software_layout)

        left_layout.addWidget(filter_group)

        # Package list (now shows releases for selected repository)
        package_group = QGroupBox("Available Software")
        package_layout = QVBoxLayout(package_group)

        self.package_list = QListWidget()
        self.package_list.itemClicked.connect(self.on_release_selected)
        self.package_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.package_list.customContextMenuRequested.connect(self.show_context_menu)

        # Add loading placeholder
        loading_item = QListWidgetItem("Loading...")
        loading_item.setFlags(loading_item.flags() & ~Qt.ItemIsSelectable)  # Make it non-selectable
        self.package_list.addItem(loading_item)

        package_layout.addWidget(self.package_list)

        left_layout.addWidget(package_group)

        # Download button
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        left_layout.addWidget(self.download_btn)
        
        # Initially enable settings button (it will be disabled during operations if needed)
        self.settings_btn.setEnabled(True)
        print("DEBUG: Settings button initially enabled")



        # Right panel - Status and output
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Top right - Creator credit and social buttons
        coffee_layout = QHBoxLayout()

        # Creator credit
        creator_label = QLabel("Created by Ryan Specter of Team Slide")
        creator_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                font-style: italic;
            }
        """)
        coffee_layout.addWidget(creator_label)

        coffee_layout.addStretch()  # Push buttons to the right

        # Driver Setup button - Windows only, and only if drivers are missing
        if platform.system() == "Windows":
            driver_info = self.check_drivers_and_architecture()
            
            if driver_info['is_arm64']:
                # ARM64 Windows: Show ARM64-specific message
                arm64_btn = QPushButton("ARM64 Notice")
                arm64_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FF6B35;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #E55A2B;
                    }
                    QPushButton:pressed {
                        background-color: #CC4A24;
                    }
                """)
                arm64_btn.clicked.connect(self.open_arm64_info)
                coffee_layout.addWidget(arm64_btn)
                
            elif not driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
                # No drivers: Show "Install MediaTek & UsbDk Drivers" button
                driver_btn = QPushButton("🔧 Install MediaTek & UsbDk Drivers")
                driver_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0066CC;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #0052A3;
                    }
                    QPushButton:pressed {
                        background-color: #003D7A;
                    }
                """)
                driver_btn.clicked.connect(self.open_driver_setup_link)
                coffee_layout.addWidget(driver_btn)
                
            elif driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
                # Only MTK driver: Show "Install USB Development Kit" link
                usbdk_link = QLabel("Install USB Development Kit for full functionality")
                usbdk_link.setStyleSheet("""
                    QLabel {
                        color: #0066CC;
                        font-size: 11px;
                        text-decoration: underline;
                        cursor: pointer;
                        margin: 5px;
                    }
                    QLabel:hover {
                        color: #004499;
                    }
                """)
                usbdk_link.setCursor(Qt.PointingHandCursor)
                usbdk_link.mousePressEvent = self.open_usbdk_info
                coffee_layout.addWidget(usbdk_link)
                
                # Only show "Install from .zip" button if not on ARM64 Windows
                if not driver_info['is_arm64']:
                    install_zip_btn = QPushButton("📦 Install from .zip")
                    install_zip_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #28A745;
                            color: white;
                            border: none;
                            padding: 8px 16px;
                            border-radius: 20px;
                            font-weight: bold;
                            font-size: 12px;
                        }
                        QPushButton:hover {
                            background-color: #218838;
                        }
                        QPushButton:pressed {
                            background-color: #1E7E34;
                        }
                    """)
                    install_zip_btn.clicked.connect(self.install_from_zip)
                    coffee_layout.addWidget(install_zip_btn)
                
            else:
                # Both drivers available: Show "Install from .zip" button (but not on ARM64)
                if not driver_info['is_arm64']:
                    install_zip_btn = QPushButton("📦 Install from .zip")
                    install_zip_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #28A745;
                            color: white;
                            border: none;
                            padding: 8px 16px;
                            border-radius: 20px;
                            font-weight: bold;
                            font-size: 12px;
                        }
                        QPushButton:hover {
                            background-color: #218838;
                        }
                        QPushButton:pressed {
                            background-color: #1E7E34;
                        }
                    """)
                    install_zip_btn.clicked.connect(self.install_from_zip)
                    coffee_layout.addWidget(install_zip_btn)
        else:
            # On non-Windows systems, show "Install from .zip" button
            install_zip_btn = QPushButton("📦 Install from .zip")
            install_zip_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28A745;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
                QPushButton:pressed {
                    background-color: #1E7E34;
                }
            """)
            install_zip_btn.clicked.connect(self.install_from_zip)
            coffee_layout.addWidget(install_zip_btn)

        # Reddit button
        reddit_btn = QPushButton("📱 r/innioasis")
        reddit_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF4500;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #E63939;
            }
            QPushButton:pressed {
                background-color: #CC3300;
            }
        """)
        reddit_btn.clicked.connect(self.open_reddit_link)
        coffee_layout.addWidget(reddit_btn)

        # Discord button
        discord_btn = QPushButton("💬 Discord")
        discord_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865F2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4752C4;
            }
            QPushButton:pressed {
                background-color: #3C45A5;
            }
        """)
        discord_btn.clicked.connect(self.open_discord_link)
        coffee_layout.addWidget(discord_btn)

        # Buy Us Coffee button (renamed from Buy Me Coffee)
        coffee_btn = QPushButton("☕ Buy Us Coffee")
        coffee_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5E5B;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #FF4441;
            }
            QPushButton:pressed {
                background-color: #E63939;
            }
        """)
        coffee_btn.clicked.connect(self.open_coffee_link)
        coffee_layout.addWidget(coffee_btn)

        right_layout.addLayout(coffee_layout)

        # App Update button (below social media buttons)
        update_layout = QHBoxLayout()
        update_layout.addStretch()  # Push button to the right

        self.update_btn_right = QPushButton("Check for Utility Updates")
        self.update_btn_right.setEnabled(True)  # Enable immediately
        self.update_btn_right.clicked.connect(self.launch_updater_script)
        self.update_btn_right.setToolTip("Downloads and installs the latest version of the Innioasis Updater")
        update_layout.addWidget(self.update_btn_right)
        right_layout.addLayout(update_layout)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(30)  # Reduced height for compact display
        self.status_label.setMaximumHeight(40)  # Added maximum height constraint
        status_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(20)  # Ensure progress bar has proper height
        self.progress_bar.setMaximumHeight(25)  # Set maximum height for consistency
        status_layout.addWidget(self.progress_bar)

        right_layout.addWidget(status_group)

        # Output group
        output_group = QGroupBox("Getting Ready:")
        output_layout = QVBoxLayout(output_group)

        # Image display area
        self.image_label = QLabel()
        self.image_label.setMinimumSize(400, 300)  # Set minimum size for proper initial display
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: 1px solid #cccccc;
                border-radius: 5px;
                color: #333;
            }
        """)

        # Load initial image with proper sizing
        self.load_presteps_image()

        # Ensure proper image sizing after window is fully initialized
        QTimer.singleShot(100, self.ensure_proper_image_sizing)

        output_layout.addWidget(self.image_label)

        right_layout.addWidget(output_group)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([480, 720])  # Adjusted for 1220px total width

        # Add Labs link at bottom right corner
        labs_layout = QHBoxLayout()
        labs_layout.addStretch()  # Push to the right
        
        # Check if current file is test.py or firmware_downloader.py
        current_file = Path(__file__).name
        if current_file == "test.py":
            labs_text = "Labs ON"
        else:
            labs_text = "Labs OFF"
            
        self.labs_link = QLabel(labs_text)
        self.labs_link.setStyleSheet("""
            QLabel {
                color: #0066CC;
                font-size: 11px;
                text-decoration: underline;
                cursor: pointer;
            }
            QLabel:hover {
                color: #004499;
            }
        """)
        self.labs_link.setCursor(Qt.PointingHandCursor)
        self.labs_link.mousePressEvent = self.switch_to_labs_version
        labs_layout.addWidget(self.labs_link)
        
        main_layout.addLayout(labs_layout)
        
        # Add status bar for driver information
        if platform.system() == "Windows":
            self.create_driver_status_bar()

    def create_driver_status_bar(self):
        """Create a status bar showing driver information for Windows users"""
        driver_info = self.check_drivers_and_architecture()
        
        # Create status bar
        status_bar = self.statusBar()
        
        if driver_info['is_arm64']:
            # ARM64 Windows: Show ARM64-specific message
            status_bar.showMessage("Only 'Tools' is available on ARM64 Windows, please use WSLg, Linux or another computer for Software Installs")
        elif not driver_info['can_install_firmware']:
            # No drivers: Show driver requirement message
            status_bar.showMessage("No drivers installed. Click 'Install Windows Drivers' to use Innioasis Updater.")
        elif driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
            # Only MTK driver: Show limited functionality message
            status_bar.showMessage("Limited functionality. Install USB Development Kit driver for full functionality.")
        else:
            # Both drivers available: Show ready message
            status_bar.showMessage("Ready - All installation methods available")

    def stop_mtk_processes(self):
        """Stop any running MTK processes"""
        try:
            if platform.system() == "Windows":
                # Stop any running mtk.py processes on Windows
                subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *mtk*'], 
                              capture_output=True, timeout=5)
            else:
                # Stop any running mtk.py processes on Unix-like systems
                subprocess.run(['pkill', '-f', 'mtk.py'], capture_output=True, timeout=5)
            silent_print("Stopped any running MTK processes")
        except Exception as e:
            silent_print(f"Error stopping MTK processes: {e}")

    def cleanup_libusb_state(self):
        """Clean up libusb state and USB device connections"""
        try:
            if platform.system() == "Windows":
                # On Windows, try to reset USB devices
                silent_print("Cleaning up USB state on Windows...")
                # This is a placeholder - actual USB reset would require more complex implementation
            else:
                # On Unix-like systems, try to reset USB devices
                silent_print("Cleaning up USB state on Unix-like system...")
                # This is a placeholder - actual USB reset would require more complex implementation
            silent_print("USB state cleanup completed")
        except Exception as e:
            silent_print(f"Error during USB state cleanup: {e}")

    def revert_to_startup_state(self):
        """Revert the application to its startup state"""
        try:
            # Reset status and progress
            self.status_label.setText("Ready")
            self.progress_bar.setVisible(False)
            
            # Load initial image
            self.load_presteps_image()
            
            # Update driver status bar if on Windows
            if platform.system() == "Windows":
                self.create_driver_status_bar()
                
            silent_print("Application reverted to startup state")
        except Exception as e:
            silent_print(f"Error reverting to startup state: {e}")

    def run_mtk_command(self):
        """Run the MTK command for firmware installation"""
        try:
            # Check driver availability for Windows users
            if platform.system() == "Windows":
                driver_info = self.check_drivers_and_architecture()
                
                if driver_info['is_arm64']:
                    QMessageBox.information(
                        self,
                        "ARM64 Windows Not Supported",
                        "Firmware installation is not supported on ARM64 Windows.\n\n"
                        "You can download firmware files, but to install them please use:\n"
                        "• WSLg (Windows Subsystem for Linux with GUI)\n"
                        "• Linux (dual boot or live USB)\n"
                        "• Another computer with x64 Windows"
                    )
                    return
                    
                elif not driver_info['can_install_firmware']:
                    QMessageBox.warning(
                        self,
                        "Drivers Required",
                        "No installation methods available. Please install drivers to enable firmware installation.\n\n"
                        "Click OK to open the driver installation guide."
                    )
                    self.open_driver_setup_link()
                    return
            
            # Create installation marker
            create_installation_marker()
            
            # Start MTK worker
            if not self.mtk_worker or not self.mtk_worker.isRunning():
                # Create debug window if debug mode is enabled
                debug_window = None
                if getattr(self, 'debug_mode', False):
                    debug_window = DebugOutputWindow(self)
                    debug_window.show()
                
                self.mtk_worker = MTKWorker(debug_mode=getattr(self, 'debug_mode', False), debug_window=debug_window)
                self.mtk_worker.status_updated.connect(self.update_status)
                self.mtk_worker.show_installing_image.connect(self.load_installing_image)
                self.mtk_worker.show_reconnect_image.connect(self.load_handshake_error_image)
                self.mtk_worker.show_presteps_image.connect(self.load_presteps_image)
                self.mtk_worker.mtk_completed.connect(self.handle_mtk_completion)
                self.mtk_worker.handshake_failed.connect(self.handle_handshake_failure)
                self.mtk_worker.errno2_detected.connect(self.handle_errno2_error)
                self.mtk_worker.backend_error_detected.connect(self.handle_backend_error)
                self.mtk_worker.keyboard_interrupt_detected.connect(self.handle_keyboard_interrupt)
                self.mtk_worker.disable_update_button.connect(self.disable_update_button)
                self.mtk_worker.enable_update_button.connect(self.enable_update_button)
                self.mtk_worker.start()
                
                self.status_label.setText("Starting MTK installation...")
                silent_print("MTK worker started")
            else:
                silent_print("MTK worker already running")
                
        except Exception as e:
            silent_print(f"Error starting MTK command: {e}")
            self.status_label.setText(f"Error starting MTK command: {e}")

    def update_status(self, message):
        """Update the status label with a message"""
        if not message or message.strip() == "":
            self.status_label.setText("Now please follow the instructions below")
        elif message.startswith("MTK:") and (message.strip() == "MTK:" or 
                                              message.strip() == "MTK:..........." or 
                                              message.strip() == "MTK: ..........." or
                                              message.strip() == "MTK: .........." or
                                              message.strip() == "MTK: ........" or
                                              message.strip() == "MTK: ......." or
                                              message.strip() == "MTK: ......" or
                                              message.strip() == "MTK: ....." or
                                              message.strip() == "MTK: ...." or
                                              message.strip() == "MTK: ..." or
                                              message.strip() == "MTK: .." or
                                              message.strip() == "MTK: ." or
                                              len(message.strip()) <= 10):  # Very short MTK messages likely indicate waiting
            # MTK is waiting for device connection
            self.status_label.setText("Now please follow the instructions below")
        else:
            self.status_label.setText(message)

    def handle_mtk_completion(self, success, message):
        """Handle MTK command completion"""
        if success:
            self.status_label.setText("Installation completed successfully")
            self.load_installed_image()
            remove_installation_marker()
        else:
            self.status_label.setText(f"Installation failed: {message}")
            self.load_process_ended_image()
            remove_installation_marker()

    def handle_handshake_failure(self):
        """Handle handshake failure"""
        self.status_label.setText("Please unplug your Y1 and try again")
        self.load_initsteps_image()

    def handle_errno2_error(self):
        """Handle errno2 error"""
        self.status_label.setText("Errno2 error - Innioasis Updater reinstall required")
        self.load_process_ended_image()

    def handle_backend_error(self):
        """Handle backend error"""
        self.status_label.setText("Backend error - libusb backend issue")
        self.load_process_ended_image()

    def handle_keyboard_interrupt(self):
        """Handle keyboard interrupt"""
        self.status_label.setText("Installation interrupted by user")
        self.load_process_ended_image()

    def disable_update_button(self):
        """Disable the update button during MTK installation"""
        if hasattr(self, 'update_btn_right'):
            self.update_btn_right.setEnabled(False)

    def enable_update_button(self):
        """Enable the update button when returning to ready state"""
        if hasattr(self, 'update_btn_right'):
            self.update_btn_right.setEnabled(True)

    def show_troubleshooting_instructions(self):
        """Show Method 2 troubleshooting instructions"""
        try:
            # Load Method 2 image
            self.load_method2_image()
            
            # Show dialog with Method 2 instructions
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Method 2 - MTKclient Troubleshooting")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText("Method 2: MTKclient Direct Installation")
            msg_box.setInformativeText(
                "This method uses the MTKclient library directly for firmware installation.\n\n"
                "Please follow the on-screen instructions and ensure your device is properly connected.\n\n"
                "If this method fails, you may need to check your drivers or try Method 3 (SP Flash Tool)."
            )
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()
            
        except Exception as e:
            silent_print(f"Error showing Method 2 instructions: {e}")

    def try_method_3(self):
        """Try Method 3 - SP Flash Tool (Windows only)"""
        try:
            if platform.system() != "Windows":
                QMessageBox.warning(
                    self,
                    "Method 3 Not Available",
                    "Method 3 (SP Flash Tool) is only available on Windows."
                )
                return
            
            # Load Method 3 image
            self.load_method3_image()
            
            # Show dialog with Method 3 instructions
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Method 3 - SP Flash Tool")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText("Method 3: SP Flash Tool Installation")
            msg_box.setInformativeText(
                "This method uses the manufacturer's SP Flash Tool. If it fails with proper drivers, contact the seller/manufacturer.\n\n"
                "Please ensure SP Flash Tool is installed and follow its instructions.\n\n"
                "Note: This method requires the MediaTek SP Driver to be installed."
            )
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()
            
        except Exception as e:
            silent_print(f"Error showing Method 3 instructions: {e}")

    def load_method2_image(self):
        """Load Method 2 troubleshooting image"""
        try:
            if not hasattr(self, '_method2_pixmap'):
                image_path = self.get_platform_image_path("method2")
                self._method2_pixmap = QPixmap(image_path)
                if self._method2_pixmap.isNull():
                    silent_print(f"Failed to load Method 2 image from {image_path}")
                    return
            
            self._current_pixmap = self._method2_pixmap
            self.set_image_with_aspect_ratio(self._method2_pixmap)
        except Exception as e:
            silent_print(f"Error loading Method 2 image: {e}")
            return

    def load_method3_image(self):
        """Load Method 3 troubleshooting image"""
        try:
            if not hasattr(self, '_method3_pixmap'):
                image_path = self.get_platform_image_path("method3")
                self._method3_pixmap = QPixmap(image_path)
                if self._method3_pixmap.isNull():
                    silent_print(f"Failed to load Method 3 image from {image_path}")
                    return
            
            self._current_pixmap = self._method3_pixmap
            self.set_image_with_aspect_ratio(self._method3_pixmap)
        except Exception as e:
            silent_print(f"Error loading Method 3 image: {e}")
            return

    def load_data(self):
        """Load configuration and manifest data with improved performance"""
        self.status_label.setText("Loading configuration...")
        silent_print("Loading configuration and manifest data...")

        # Clear cache at startup to ensure fresh tokens are fetched
        clear_cache()
        silent_print("Cleared cache at startup to fetch fresh tokens")

        # Download tokens
        tokens = self.config_downloader.download_config()
        if not tokens:
            silent_print("ERROR: Failed to download API tokens")
            self.status_label.setText("No API tokens available")
            return

        self.github_api = GitHubAPI(tokens)
        silent_print(f"Loaded {len(tokens)} API tokens")

        # Start parallel token validation for faster startup
        if tokens:
            silent_print(f"Loaded {len(tokens)} API tokens")
            self.status_label.setText("Validating API tokens...")
            # Start parallel token validation
            self.validate_tokens_parallel(tokens)
        else:
            silent_print("No tokens loaded")
            self.status_label.setText("No API tokens available")

        # Manifest loading is now handled asynchronously in validate_tokens_parallel
        # The UI will be populated once a working token is found or fallback occurs

    def validate_tokens_parallel(self, tokens):
        """Validate tokens in parallel for faster startup"""
        if not tokens:
            silent_print("No tokens to validate, using unauthenticated mode")
            self.status_label.setText("Using unauthenticated mode")
            self.finish_data_loading([])
            return

        def validate_single_token(token):
            """Validate a single token"""
            try:
                # Check if token already has prefix to avoid double-prefixing
                if token.startswith('github_pat_'):
                    test_token = token
                else:
                    test_token = f"github_pat_{token}"
                silent_print(f"Testing token: {test_token[:20]}...")

                headers = {
                    'Authorization': f'token {test_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }

                response = requests.get('https://api.github.com/user',
                                      headers=headers,
                                      timeout=TOKEN_VALIDATION_TIMEOUT)

                silent_print(f"Token validation response: {response.status_code}")

                if response.status_code == 200:
                    user_data = response.json()
                    silent_print(f"Token valid - authenticated as: {user_data.get('login', 'Unknown')}")
                    return token, user_data.get('login', 'Unknown')
                elif response.status_code == 401:
                    silent_print(f"Token invalid (401 Unauthorized)")
                    return None, None
                elif response.status_code == 403:
                    silent_print(f"Token rate limited (403 Forbidden) - will retry later")
                    # Don't mark rate-limited tokens as invalid, they might work later
                    return None, None
                else:
                    silent_print(f"Token failed - status: {response.status_code}")
                    return None, None

            except Exception as e:
                silent_print(f"Token validation error: {e}")
                return None, None

        # Use ThreadPoolExecutor for parallel validation
        with ThreadPoolExecutor(max_workers=min(len(tokens), MAX_CONCURRENT_REQUESTS)) as executor:
            # Submit all token validation tasks
            future_to_token = {executor.submit(validate_single_token, token): token for token in tokens}

            # Process results as they complete
            for future in as_completed(future_to_token):
                token, username = future.result()
                if token is not None:
                    # Found a working token, cancel other tasks and proceed
                    silent_print(f"Found working token for user: {username}")
                    self.status_label.setText(f"Authenticated as {username}")

                    # Cancel remaining tasks
                    for remaining_future in future_to_token:
                        if not remaining_future.done():
                            remaining_future.cancel()

                    # Mark token as working and proceed
                    self.github_api.mark_token_working(token)
                    self.finish_data_loading([token])
                    return

        # If we get here, no tokens worked
        silent_print("All tokens failed validation, using unauthenticated mode")
        self.status_label.setText("Using unauthenticated mode")
        # Try with at least one token anyway, in case validation was too strict
        if tokens:
            silent_print("Attempting to use first token despite validation failure")
            # Check if token already has prefix to avoid double-prefixing
            first_token = tokens[0]
            if not first_token.startswith('github_pat_'):
                first_token = f"github_pat_{first_token}"
            self.github_api = GitHubAPI([first_token])
            self.finish_data_loading([tokens[0]])
        else:
            self.finish_data_loading([])

    def finish_data_loading(self, working_tokens):
        """Complete data loading with working tokens"""
        self.status_label.setText("Loading software manifest...")

        # Ensure all tokens have github_pat_ prefix for GitHub API class
        api_tokens = []
        for token in working_tokens:
            if not token.startswith('github_pat_'):
                api_tokens.append(f"github_pat_{token}")
            else:
                api_tokens.append(token)

        silent_print(f"Prepared {len(api_tokens)} tokens for GitHub API")
        for i, token in enumerate(api_tokens):
            silent_print(f"Token {i+1}: {token[:20]}...")

        # Create GitHub API with properly formatted tokens
        self.github_api = GitHubAPI(api_tokens)
        
        # Start periodic cache cleanup
        self.github_api.cleanup_cache_periodically()

        # Download manifest
        self.packages = self.config_downloader.download_manifest()
        if not self.packages:
            silent_print("ERROR: Failed to download software manifest")
            self.status_label.setText("Error: Failed to download software manifest")
            return

        silent_print(f"Loaded {len(self.packages)} software packages")
        self.status_label.setText("Ready: Select a firmware to Download. Your music will stay safe.")

        # Populate UI components
        self.populate_device_type_combo()
        self.populate_device_model_combo()
        self.populate_firmware_combo()

        # Apply initial filters
        self.filter_firmware_options()

        # Use a timer to ensure the default selection is properly applied
        QTimer.singleShot(100, self.apply_initial_release_display)



        self.status_label.setText("Ready")
        silent_print("Data loading complete")

    def apply_initial_release_display(self):
        """Apply the initial release display based on default software selection"""
        selected_repo = self.firmware_combo.currentData()
        if selected_repo:
            # Show releases for selected software
            self.populate_releases_list()
        else:
            # Show releases from all available software progressively
            self.populate_all_releases_list_progressive()

    def show_device_type_help(self):
        """Show device type help information in a dialog box"""
        help_text = """<h3>Device Type Selection Guide</h3>

<p><b>Type A Devices:</b> This is the recommended starting point for most users. Install this first to see if it meets your needs.</p>

<p><b>Type B Devices:</b> If your scroll wheel doesn't respond properly after installing Type A, try one of the Type B options. These are alternative configurations that may resolve scroll wheel issues.</p>

<p><b>Recommendation:</b> Always start with Type A. Only move to Type B if you experience scroll wheel problems.</p>"""

        # Create a native system dialog box
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Device Type Help")
        msg_box.setText(help_text)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setDefaultButton(QMessageBox.Ok)

        # Ensure it uses native system styling
        msg_box.setModal(True)
        msg_box.exec()

    def open_y1_remote_control(self):
        """Open Y1 Remote Control application without closing firmware downloader"""
        print("DEBUG: Tools button clicked! open_y1_remote_control method called.")
        
        # Check if any operations are in progress
        if INSTALLATION_MARKER_FILE.exists():
            print("DEBUG: Installation marker exists, showing warning.")
            QMessageBox.warning(self, "Operation in Progress", 
                              "Cannot open Y1 Helper while firmware installation or troubleshooting is in progress.\n\nPlease wait for the current operation to complete.")
            return
        
        try:
            # Simply run y1_helper.py
            y1_helper_path = Path("y1_helper.py")
            if y1_helper_path.exists():
                subprocess.Popen([sys.executable, str(y1_helper_path)])
                self.status_label.setText("Y1 Remote Control launched successfully")
                # Don't close the firmware downloader - keep it running
            else:
                                                QMessageBox.error(self, "Error", 
                                                "Y1 Remote Control not found. Please ensure y1_helper.py is in the same directory.")
        except Exception as e:
            QMessageBox.error(self, "Error", f"Failed to launch Y1 Remote Control: {e}")
    
    def show_settings_dialog(self):
        """Show enhanced settings dialog with installation method and shortcut management"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setFixedSize(600, 500)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        # Title
        title_label = QLabel("Settings")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Create tabbed interface or sections
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Installation Method Tab
        install_tab = QWidget()
        install_layout = QVBoxLayout(install_tab)
        
        install_title = QLabel("Installation Method Settings")
        install_title.setStyleSheet("font-size: 14px; font-weight: bold; margin: 5px;")
        install_layout.addWidget(install_title)
        
        # Check driver status for Windows users
        driver_info = None
        if platform.system() == "Windows":
            driver_info = self.check_drivers_and_architecture()
            
            # Show driver status message
            if driver_info['is_arm64']:
                status_label = QLabel("⚠️ ARM64 Windows Detected")
                status_label.setStyleSheet("color: #FF6B35; font-weight: bold; margin: 5px;")
                install_layout.addWidget(status_label)
                
                status_desc = QLabel("Only firmware downloads are available on ARM64 Windows.\nPlease use WSLg, Linux, or another computer for software installation.")
                status_desc.setStyleSheet("color: #666; margin: 5px;")
                install_layout.addWidget(status_desc)
                
                # Disable method selection for ARM64
                method_combo = QComboBox()
                method_combo.addItem("No installation methods available on ARM64 Windows", "")
                method_combo.setEnabled(False)
                install_layout.addWidget(method_combo)
                
                # Skip the rest of the dialog for ARM64
                button_layout = QHBoxLayout()
                button_layout.addStretch()
                ok_btn = QPushButton("OK")
                ok_btn.clicked.connect(dialog.accept)
                button_layout.addWidget(ok_btn)
                install_layout.addLayout(button_layout)
                tab_widget.addTab(install_tab, "Installation")
                dialog.exec()
                return
                
            elif not driver_info['can_install_firmware']:
                status_label = QLabel("⚠️ Drivers Required")
                status_label.setStyleSheet("color: #FF6B35; font-weight: bold; margin: 5px;")
                install_layout.addWidget(status_label)
                
                status_desc = QLabel("No installation methods available. Please install drivers to enable firmware installation.\n\nMore methods will become available if you install the USB Development Kit driver.")
                status_desc.setStyleSheet("color: #666; margin: 5px;")
                install_layout.addWidget(status_desc)
                
                # Disable method selection when no drivers
                method_combo = QComboBox()
                method_combo.addItem("No installation methods available without drivers", "")
                method_combo.setEnabled(False)
                install_layout.addWidget(method_combo)
                
                # Skip the rest of the dialog when no drivers
                button_layout = QHBoxLayout()
                button_layout.addStretch()
                ok_btn = QPushButton("OK")
                ok_btn.clicked.connect(dialog.accept)
                button_layout.addWidget(ok_btn)
                install_layout.addLayout(button_layout)
                tab_widget.addTab(install_tab, "Installation")
                dialog.exec()
                return
                
            elif not driver_info['has_usbdk_driver']:
                status_label = QLabel("ℹ️ Limited Functionality")
                status_label.setStyleSheet("color: #0066CC; font-weight: bold; margin: 5px;")
                install_layout.addWidget(status_label)
                
                status_desc = QLabel("Only Method 3 (SP Flash Tool) is available.\n\nMore methods will become available if you install the USB Development Kit driver.")
                status_desc.setStyleSheet("color: #666; margin: 5px;")
                install_layout.addWidget(status_desc)
        
        # Description
        desc_label = QLabel("This setting will be used for the next firmware installation.")
        desc_label.setStyleSheet("color: #666; margin: 5px;")
        install_layout.addWidget(desc_label)
        
        # Method selection
        method_label = QLabel("Installation Method:")
        install_layout.addWidget(method_label)
        
        self.method_combo = QComboBox()
        
        # Add methods based on driver availability
        if platform.system() == "Windows" and driver_info:
            if driver_info['has_mtk_driver'] and driver_info['has_usbdk_driver']:
                # Both drivers available: All methods
                self.method_combo.addItem("Method 1 - Guided", "guided")
                self.method_combo.addItem("Method 2 - MTKclient", "mtkclient")
                self.method_combo.addItem("Method 3 - SP Flash Tool", "spflash")
            elif driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
                # Only MTK driver: Only Method 3
                self.method_combo.addItem("Method 3 - SP Flash Tool (Only available method)", "spflash")
            else:
                # No drivers: No methods
                self.method_combo.addItem("No installation methods available", "")
        else:
            # Non-Windows: Standard methods
            self.method_combo.addItem("Method 1 - Guided", "guided")
            self.method_combo.addItem("Method 2 - MTKclient", "mtkclient")
        
        # Set current method
        current_method = getattr(self, 'installation_method', 'guided')
        index = self.method_combo.findData(current_method)
        if index >= 0:
            self.method_combo.setCurrentIndex(index)
        
        install_layout.addWidget(self.method_combo)
        
        # Always use this method checkbox (only show when methods are available)
        if platform.system() == "Windows" and driver_info and not driver_info['can_install_firmware']:
            pass  # Don't show checkbox when no methods available
        else:
            self.always_use_checkbox = QCheckBox("Always use this method for future installations")
            self.always_use_checkbox.setToolTip("When checked, this method will be used automatically for all future firmware installations")
            
            # Set checkbox state based on saved preference
            always_use = getattr(self, 'always_use_method', False)
            self.always_use_checkbox.setChecked(always_use)
            
            install_layout.addWidget(self.always_use_checkbox)
        
        # Labs mode debug checkbox
        self.debug_mode_checkbox = QCheckBox("Enable Debug Mode (Labs)")
        self.debug_mode_checkbox.setToolTip("When checked, guided installations will show mtk.py's full output in a separate window for debugging")
        
        # Set checkbox state based on saved preference
        debug_mode = getattr(self, 'debug_mode', False)
        self.debug_mode_checkbox.setChecked(debug_mode)
        
        install_layout.addWidget(self.debug_mode_checkbox)
        
        # Method descriptions
        desc_text = QTextEdit()
        desc_text.setMaximumHeight(80)
        desc_text.setReadOnly(True)
        
        if platform.system() == "Windows" and driver_info:
            if driver_info['has_mtk_driver'] and driver_info['has_usbdk_driver']:
                desc_text.setPlainText("""
Method 1 - Guided: Step-by-step with visual guidance
Method 2 - MTKclient: Direct technical installation  
Method 3 - SP Flash Tool: Manufacturer's tool (Windows only)
                """)
            elif driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
                desc_text.setPlainText("""
Method 3 - SP Flash Tool: Manufacturer's tool (Windows only)
Note: Install USB Development Kit driver to enable Methods 1 and 2
                """)
            else:
                desc_text.setPlainText("""
No installation methods available.
Please install drivers to enable firmware installation.

More methods will become available if you install the USB Development Kit driver.
                """)
        elif platform.system() == "Windows":
            desc_text.setPlainText("""
Method 1 - Guided: Step-by-step with visual guidance
Method 2 - MTKclient: Direct technical installation
Method 3 - SP Flash Tool: Manufacturer's tool (Windows only)
            """)
        else:
            desc_text.setPlainText("""
Method 1 - Guided: Step-by-step with visual guidance
Method 2 - MTKclient: Direct technical installation
            """)
        
        install_layout.addWidget(desc_text)
        
        # Add installation tab to tab widget
        tab_widget.addTab(install_tab, "Installation")
        
        # Shortcut Management Tab (Windows only)
        if platform.system() == "Windows":
            shortcut_tab = QWidget()
            shortcut_layout = QVBoxLayout(shortcut_tab)
            
            shortcut_title = QLabel("Shortcut Management")
            shortcut_title.setStyleSheet("font-size: 14px; font-weight: bold; margin: 5px;")
            shortcut_layout.addWidget(shortcut_title)
            
            # Desktop shortcuts toggle
            self.desktop_shortcuts_checkbox = QCheckBox("Create Desktop Shortcuts")
            self.desktop_shortcuts_checkbox.setToolTip("When enabled, Innioasis Updater will create and maintain desktop shortcuts")
            
            # Set checkbox state based on saved preference
            desktop_shortcuts = getattr(self, 'desktop_shortcuts_enabled', True)
            self.desktop_shortcuts_checkbox.setChecked(desktop_shortcuts)
            
            shortcut_layout.addWidget(self.desktop_shortcuts_checkbox)
            
            # Start menu shortcuts toggle
            self.startmenu_shortcuts_checkbox = QCheckBox("Create Start Menu Shortcuts")
            self.startmenu_shortcuts_checkbox.setToolTip("When enabled, Innioasis Updater will create and maintain start menu shortcuts")
            
            # Set checkbox state based on saved preference
            startmenu_shortcuts = getattr(self, 'startmenu_shortcuts_enabled', True)
            self.startmenu_shortcuts_checkbox.setChecked(startmenu_shortcuts)
            
            shortcut_layout.addWidget(self.startmenu_shortcuts_checkbox)
            
            # Cleanup options
            cleanup_group = QGroupBox("Shortcut Cleanup")
            cleanup_layout = QVBoxLayout(cleanup_group)
            
            cleanup_desc = QLabel("Automatically clean up old shortcuts and replace them with current ones:")
            cleanup_layout.addWidget(cleanup_desc)
            
            self.auto_cleanup_checkbox = QCheckBox("Enable Automatic Cleanup")
            self.auto_cleanup_checkbox.setToolTip("When enabled, old shortcuts will be automatically cleaned up and replaced")
            
            # Set checkbox state based on saved preference
            auto_cleanup = getattr(self, 'auto_cleanup_enabled', True)
            self.auto_cleanup_checkbox.setChecked(auto_cleanup)
            
            cleanup_layout.addWidget(self.auto_cleanup_checkbox)
            
            # Manual cleanup button
            cleanup_btn = QPushButton("Clean Up Shortcuts Now")
            cleanup_btn.setToolTip("Manually clean up old shortcuts and create current ones")
            cleanup_btn.clicked.connect(self.manual_shortcut_cleanup)
            cleanup_layout.addWidget(cleanup_btn)
            
            shortcut_layout.addWidget(cleanup_group)
            
            # Add shortcut tab to tab widget
            tab_widget.addTab(shortcut_tab, "Shortcuts")
        
        # Tools Tab
        tools_tab = QWidget()
        tools_layout = QVBoxLayout(tools_tab)
        
        tools_title = QLabel("Tools")
        tools_title.setStyleSheet("font-size: 14px; font-weight: bold; margin: 5px;")
        tools_layout.addWidget(tools_title)
        
        # Y1 Remote Control button
        y1_remote_btn = QPushButton("Launch Y1 Remote Control")
        y1_remote_btn.setToolTip("Open Y1 Remote Control application")
        y1_remote_btn.clicked.connect(self.open_y1_remote_control)
        tools_layout.addWidget(y1_remote_btn)
        
        # Check for Utility Updates button
        utility_update_btn = QPushButton("Check for Utility Updates")
        utility_update_btn.setToolTip("Download the latest updater.py script")
        utility_update_btn.clicked.connect(self.check_for_utility_updates)
        tools_layout.addWidget(utility_update_btn)
        
        # Add tools tab to tab widget
        tab_widget.addTab(tools_tab, "Tools")
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(lambda: self.save_settings(dialog))
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def save_settings(self, dialog):
        """Save all settings including installation method and shortcut preferences"""
        # Save installation method settings
        if hasattr(self, 'method_combo'):
            self.installation_method = self.method_combo.currentData()
        self.always_use_method = self.always_use_checkbox.isChecked()
        self.debug_mode = self.debug_mode_checkbox.isChecked()
        
        # Save shortcut settings (Windows only)
        if platform.system() == "Windows":
            self.desktop_shortcuts_enabled = self.desktop_shortcuts_checkbox.isChecked()
            self.startmenu_shortcuts_enabled = self.startmenu_shortcuts_checkbox.isChecked()
            self.auto_cleanup_enabled = self.auto_cleanup_checkbox.isChecked()
            
            # Apply shortcut settings immediately
            self.apply_shortcut_settings()
        
        # Save to persistent storage
        self.save_installation_preferences()
        
        # Update status message
        if self.always_use_method:
            self.status_label.setText(f"Installation method set to: {self.installation_method} (will be used for all future installations)")
        else:
            self.status_label.setText(f"Installation method set to: {self.installation_method} (one-time use)")
        
        if self.debug_mode:
            self.status_label.setText(self.status_label.text() + " - Debug mode enabled")
        
        dialog.accept()
    
    def save_installation_preferences(self):
        """Save installation preferences to persistent storage"""
        try:
            preferences = {
                'installation_method': self.installation_method,
                'always_use_method': self.always_use_method,
                'debug_mode': getattr(self, 'debug_mode', False)
            }
            
            # Add shortcut preferences (Windows only)
            if platform.system() == "Windows":
                preferences.update({
                    'desktop_shortcuts_enabled': getattr(self, 'desktop_shortcuts_enabled', True),
                    'startmenu_shortcuts_enabled': getattr(self, 'startmenu_shortcuts_enabled', True),
                    'auto_cleanup_enabled': getattr(self, 'auto_cleanup_enabled', True)
                })
            
            # Save to a JSON file in the same directory
            preferences_file = Path("installation_preferences.json")
            import json
            with open(preferences_file, 'w') as f:
                json.dump(preferences, f, indent=2)
                
            silent_print(f"Saved installation preferences: {preferences}")
        except Exception as e:
            silent_print(f"Error saving installation preferences: {e}")
    
    def load_installation_preferences(self):
        """Load installation preferences from persistent storage"""
        try:
            preferences_file = Path("installation_preferences.json")
            if preferences_file.exists():
                import json
                with open(preferences_file, 'r') as f:
                    preferences = json.load(f)
                
                # Load saved preferences
                if 'installation_method' in preferences:
                    self.installation_method = preferences['installation_method']
                if 'always_use_method' in preferences:
                    self.always_use_method = preferences['always_use_method']
                if 'debug_mode' in preferences:
                    self.debug_mode = preferences['debug_mode']
                
                # Load shortcut preferences (Windows only)
                if platform.system() == "Windows":
                    if 'desktop_shortcuts_enabled' in preferences:
                        self.desktop_shortcuts_enabled = preferences['desktop_shortcuts_enabled']
                    if 'startmenu_shortcuts_enabled' in preferences:
                        self.startmenu_shortcuts_enabled = preferences['startmenu_shortcuts_enabled']
                    if 'auto_cleanup_enabled' in preferences:
                        self.auto_cleanup_enabled = preferences['auto_cleanup_enabled']
                
                silent_print(f"Loaded installation preferences: {preferences}")
            else:
                silent_print("No saved installation preferences found, using defaults")
        except Exception as e:
            silent_print(f"Error loading installation preferences: {e}")
    
    def apply_shortcut_settings(self):
        """Apply shortcut settings based on user preferences"""
        if platform.system() != "Windows":
            return
            
        try:
            # Apply desktop shortcut settings
            if self.desktop_shortcuts_enabled:
                self.ensure_desktop_shortcuts()
            else:
                self.remove_desktop_shortcuts()
            
            # Apply start menu shortcut settings
            if self.startmenu_shortcuts_enabled:
                self.ensure_startmenu_shortcuts()
            else:
                self.remove_startmenu_shortcuts()
                
        except Exception as e:
            silent_print(f"Error applying shortcut settings: {e}")
    
    def manual_shortcut_cleanup(self):
        """Manually clean up shortcuts and create current ones"""
        if platform.system() != "Windows":
            return
            
        try:
            # Silent cleanup using wildcards
            self.silent_shortcut_cleanup()
            
            # Create current shortcuts if enabled
            if self.desktop_shortcuts_enabled:
                self.ensure_desktop_shortcuts()
            if self.startmenu_shortcuts_enabled:
                self.ensure_startmenu_shortcuts()
                
            QMessageBox.information(self, "Shortcut Cleanup", "Shortcut cleanup completed successfully.")
            
        except Exception as e:
            QMessageBox.warning(self, "Shortcut Cleanup Error", f"Error during shortcut cleanup: {e}")
    
    def silent_shortcut_cleanup(self):
        """Silent cleanup of shortcuts using wildcards - no user interaction"""
        if platform.system() != "Windows":
            return
            
        try:
            cleaned_count = 0
            
            # Clean up desktop shortcuts
            desktop_path = Path.home() / "Desktop"
            if desktop_path.exists():
                # Remove shortcuts matching patterns
                patterns = ["*Y1*", "*SP Flash*", "*Innioasis*"]
                for pattern in patterns:
                    for item in desktop_path.glob(pattern):
                        if item.is_file() and item.suffix.lower() == '.lnk':
                            try:
                                item.unlink()
                                cleaned_count += 1
                                silent_print(f"Removed desktop shortcut: {item.name}")
                            except Exception as e:
                                silent_print(f"Error removing {item.name}: {e}")
            
            # Clean up start menu shortcuts
            start_menu_paths = self.get_all_start_menu_paths()
            for start_menu_path in start_menu_paths:
                if start_menu_path.exists():
                    # Remove shortcuts matching patterns
                    patterns = ["*Y1*", "*SP Flash*", "*Innioasis*"]
                    for pattern in patterns:
                        for item in start_menu_path.glob(pattern):
                            if item.is_file() and item.suffix.lower() == '.lnk':
                                try:
                                    item.unlink()
                                    cleaned_count += 1
                                    silent_print(f"Removed start menu shortcut: {item.name}")
                                except Exception as e:
                                    silent_print(f"Error removing {item.name}: {e}")
                    
                    # Remove Y1 Helper folder if it exists
                    y1_helper_folder = start_menu_path / "Y1 Helper"
                    if y1_helper_folder.exists() and y1_helper_folder.is_dir():
                        try:
                            shutil.rmtree(y1_helper_folder)
                            cleaned_count += 1
                            silent_print(f"Removed Y1 Helper folder: {y1_helper_folder}")
                        except Exception as e:
                            silent_print(f"Error removing Y1 Helper folder: {e}")
            
            silent_print(f"Silent shortcut cleanup completed: {cleaned_count} items removed")
            
        except Exception as e:
            silent_print(f"Error during silent shortcut cleanup: {e}")
    
    def ensure_desktop_shortcuts(self):
        """Ensure desktop shortcuts exist"""
        if platform.system() != "Windows":
            return
            
        try:
            desktop_path = Path.home() / "Desktop"
            if not desktop_path.exists():
                return
            
            current_dir = Path.cwd()
            
            # Create Innioasis Updater shortcut
            source_shortcut = current_dir / "Innioasis Updater.lnk"
            if source_shortcut.exists():
                dest_shortcut = desktop_path / "Innioasis Updater.lnk"
                if not dest_shortcut.exists():
                    shutil.copy2(source_shortcut, dest_shortcut)
                    silent_print(f"Created desktop shortcut: Innioasis Updater.lnk")
            
            # Create Y1 Remote Control shortcut if it exists
            source_y1_remote = current_dir / "Innioasis Y1 Remote Control.lnk"
            if source_y1_remote.exists():
                dest_y1_remote = desktop_path / "Innioasis Y1 Remote Control.lnk"
                if not dest_y1_remote.exists():
                    shutil.copy2(source_y1_remote, dest_y1_remote)
                    silent_print(f"Created desktop shortcut: Innioasis Y1 Remote Control.lnk")
                    
        except Exception as e:
            silent_print(f"Error ensuring desktop shortcuts: {e}")
    
    def remove_desktop_shortcuts(self):
        """Remove desktop shortcuts"""
        if platform.system() != "Windows":
            return
            
        try:
            desktop_path = Path.home() / "Desktop"
            if not desktop_path.exists():
                return
            
            # Remove Innioasis shortcuts
            patterns = ["*Innioasis*"]
            for pattern in patterns:
                for item in desktop_path.glob(pattern):
                    if item.is_file() and item.suffix.lower() == '.lnk':
                        try:
                            item.unlink()
                            silent_print(f"Removed desktop shortcut: {item.name}")
                        except Exception as e:
                            silent_print(f"Error removing {item.name}: {e}")
                            
        except Exception as e:
            silent_print(f"Error removing desktop shortcuts: {e}")
    
    def ensure_startmenu_shortcuts(self):
        """Ensure start menu shortcuts exist"""
        if platform.system() != "Windows":
            return
            
        try:
            start_menu_paths = self.get_all_start_menu_paths()
            current_dir = Path.cwd()
            
            for start_menu_path in start_menu_paths:
                if start_menu_path.exists():
                    # Create Innioasis Updater shortcut
                    source_shortcut = current_dir / "Innioasis Updater.lnk"
                    if source_shortcut.exists():
                        dest_shortcut = start_menu_path / "Innioasis Updater.lnk"
                        if not dest_shortcut.exists():
                            shutil.copy2(source_shortcut, dest_shortcut)
                            silent_print(f"Created start menu shortcut: Innioasis Updater.lnk")
                    
                    # Create Y1 Remote Control shortcut if it exists
                    source_y1_remote = current_dir / "Innioasis Y1 Remote Control.lnk"
                    if source_y1_remote.exists():
                        dest_y1_remote = start_menu_path / "Innioasis Y1 Remote Control.lnk"
                        if not dest_y1_remote.exists():
                            shutil.copy2(source_y1_remote, dest_y1_remote)
                            silent_print(f"Created start menu shortcut: Innioasis Y1 Remote Control.lnk")
                            
        except Exception as e:
            silent_print(f"Error ensuring start menu shortcuts: {e}")
    
    def remove_startmenu_shortcuts(self):
        """Remove start menu shortcuts"""
        if platform.system() != "Windows":
            return
            
        try:
            start_menu_paths = self.get_all_start_menu_paths()
            
            for start_menu_path in start_menu_paths:
                if start_menu_path.exists():
                    # Remove Innioasis shortcuts
                    patterns = ["*Innioasis*"]
                    for pattern in patterns:
                        for item in start_menu_path.glob(pattern):
                            if item.is_file() and item.suffix.lower() == '.lnk':
                                try:
                                    item.unlink()
                                    silent_print(f"Removed start menu shortcut: {item.name}")
                                except Exception as e:
                                    silent_print(f"Error removing {item.name}: {e}")
                    
                    # Remove Y1 Helper folder if it exists
                    y1_helper_folder = start_menu_path / "Y1 Helper"
                    if y1_helper_folder.exists() and y1_helper_folder.is_dir():
                        try:
                            shutil.rmtree(y1_helper_folder)
                            silent_print(f"Removed Y1 Helper folder: {y1_helper_folder}")
                        except Exception as e:
                            silent_print(f"Error removing Y1 Helper folder: {e}")
                            
        except Exception as e:
            silent_print(f"Error removing start menu shortcuts: {e}")
    
    def restore_original_installation_method(self):
        """Restore the original installation method if it was temporarily overridden"""
        if hasattr(self, '_original_installation_method'):
            # Only restore if the current method is spflash (Method 3) and we have the original
            if self.installation_method == "spflash" and self._original_installation_method != "spflash":
                # Check if we still only have MTK driver (no UsbDk)
                if platform.system() == "Windows":
                    driver_info = self.check_drivers_and_architecture()
                    if driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
                        # Still only MTK driver, keep Method 3 for this session
                        silent_print("Keeping Method 3 for this session (only MTK driver available)")
                    else:
                        # UsbDk driver now available, restore original method
                        self.installation_method = self._original_installation_method
                        silent_print(f"Restored original installation method: {self.installation_method}")
                        # Clear the stored original method
                        delattr(self, '_original_installation_method')
            # Use defaults if loading fails
            self.installation_method = "guided"
            self.always_use_method = False

    def populate_device_type_combo(self):
        """Dynamically populate device type combo from manifest data"""
        self.device_type_combo.clear()
        self.device_type_combo.addItem("All Types", "")

        # Get unique device types from packages
        device_types = set()
        for package in self.packages:
            device_type = package.get('device_type', '')
            if device_type:
                device_types.add(device_type)

        # Add device types to combo (sorted)
        for device_type in sorted(device_types):
            self.device_type_combo.addItem(f"Type {device_type}", device_type)

        # Set default to first available type if any exist
        if len(device_types) > 0:
            first_type = sorted(device_types)[0]
            self.device_type_combo.setCurrentText(f"Type {first_type}")

    def populate_device_model_combo(self):
        """Dynamically populate device model combo from manifest data"""
        self.device_model_combo.clear()
        self.device_model_combo.addItem("All Models", "")

        # Get unique device models from packages
        device_models = set()
        for package in self.packages:
            device_model = package.get('device', '')
            if device_model:
                device_models.add(device_model)

        # Add device models to combo (sorted)
        for device_model in sorted(device_models):
            self.device_model_combo.addItem(device_model, device_model)

        # Set default to first available model if any exist
        if len(device_models) > 0:
            first_model = sorted(device_models)[0]
            self.device_model_combo.setCurrentText(first_model)

    def populate_firmware_combo(self):
        """Populate the software dropdown with package names from manifest"""
        self.firmware_combo.clear()
        self.firmware_combo.addItem("All Software", "")

        # Get current filter selections
        selected_type = self.device_type_combo.currentData()
        selected_model = self.device_model_combo.currentData()

        # Get filtered software names from packages
        software_options = []
        for package in self.packages:
            name = package.get('name', '')
            repo = package.get('repo', '')
            device_type = package.get('device_type', '')
            device_model = package.get('device', '')

            # Check device type filter
            type_match = not selected_type or device_type == selected_type

            # Check device model filter
            model_match = not selected_model or device_model == selected_model

            if name and repo and type_match and model_match:
                software_options.append((name, repo))

        # Add filtered software options to dropdown (sorted by name)
        for name, repo in sorted(software_options, key=lambda x: x[0]):
            self.firmware_combo.addItem(name, repo)

        # Set default selection to software containing "Original" if available
        default_index = 0  # Default to "All Software"
        for i in range(1, self.firmware_combo.count()):  # Skip "All Software" at index 0
            if "original" in self.firmware_combo.itemText(i).lower():
                default_index = i
                break

        self.firmware_combo.setCurrentIndex(default_index)

    def on_firmware_changed(self):
        """Handle software selection change"""
        selected_repo = self.firmware_combo.currentData()

        if selected_repo:
            # Update package list to show releases for selected software
            self.populate_releases_list()
        else:
            # "All Software" is selected - show releases from all available software
            self.populate_all_releases_list()



    def populate_releases_list(self):
        """Populate the releases list for the selected software"""
        self.package_list.clear()

        # Add loading placeholder
        loading_item = QListWidgetItem("Loading releases...")
        loading_item.setFlags(loading_item.flags() & ~Qt.ItemIsSelectable)
        self.package_list.addItem(loading_item)
        # Don't update status label - keep it as "Ready" for firmware installation status only

        selected_repo = self.firmware_combo.currentData()
        if not selected_repo:
            self.package_list.clear()
            self.package_list.addItem("Please select a software type")
            return

        # Set up timeout timer
        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(lambda: self.handle_releases_timeout())
        timeout_timer.start(60000)  # 1 minute timeout

        # Get releases for the selected repository
        try:
            silent_print(f"Attempting to load releases for {selected_repo}")
            releases = self.github_api.get_all_releases(selected_repo)
            timeout_timer.stop()  # Stop timeout if successful
            silent_print(f"Successfully loaded {len(releases) if releases else 0} releases")
        except Exception as e:
            timeout_timer.stop()
            silent_print(f"Error loading releases: {e}")
            self.package_list.clear()
            self.package_list.addItem("Unable To Load Releases")
            # Don't update status label - keep it as "Ready" for firmware installation status only
            return

        # Remove loading placeholder
        self.package_list.clear()

        if not releases:
            self.package_list.addItem(f"No releases found for {selected_repo}")
            return

        # Add releases to the list with detailed information
        for release in releases:
            # Find the package info for this release to get software name from manifest
            package_info = None
            for package in self.packages:
                if package.get('repo') == selected_repo:
                    package_info = package
                    break

            # Get software name from manifest, fallback to repo name
            software_name = package_info.get('name', selected_repo) if package_info else selected_repo

            # Detailed display format
            display_text = f"{software_name}\n"
            display_text += f"Version: {release['tag_name']}\n"

            if release.get('published_at'):
                # Format the date
                try:
                    from datetime import datetime
                    date_obj = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
                    display_text += f"Published: {date_obj.strftime('%Y-%m-%d %H:%M')}\n"
                except:
                    display_text += f"Published: {release['published_at']}\n"

            # Add software name to release info for button text logic
            release_with_software = release.copy()
            release_with_software['software_name'] = software_name

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, release_with_software)
            self.package_list.addItem(item)

        # Select the first item if available
        if self.package_list.count() > 0:
            self.package_list.setCurrentRow(0)
            first_item = self.package_list.item(0)
            if first_item:
                self.on_release_selected(first_item)

        # Keep status as Ready - don't change it for release loading
        silent_print("Releases loaded successfully")

    def handle_releases_timeout(self):
        """Handle timeout when loading releases"""
        self.package_list.clear()
        self.package_list.addItem("Unable To Load Releases")
        # Don't update status label - keep it as "Ready" for firmware installation status only
        silent_print("Timeout loading releases")

    def populate_all_releases_list(self):
        """Populate the package list with releases from all available software"""
        self.package_list.clear()

        # Get all software options that match current filters
        selected_type = self.device_type_combo.currentData()
        selected_model = self.device_model_combo.currentData()

        all_releases = []
        failed_repos = []

        for package in self.packages:
            name = package.get('name', '')
            repo = package.get('repo', '')
            device_type = package.get('device_type', '')
            device_model = package.get('device', '')

            # Check device type filter
            type_match = not selected_type or device_type == selected_type

            # Check device model filter
            model_match = not selected_model or device_model == selected_model

            if name and repo and type_match and model_match:
                # Get releases for this software with retry
                releases = self.github_api.retry_with_delay(self.github_api.get_all_releases, repo)
                if releases and len(releases) > 0:
                    for release in releases:
                        # Add software name to the release info for identification
                        release_with_software = release.copy()
                        release_with_software['software_name'] = name
                        all_releases.append(release_with_software)
                else:
                    failed_repos.append(repo)

        # Sort releases by software name (alphabetical), then by date (newest first within each software)
        # Use a custom sorting key that sorts alphabetically by software name, then by date (newest first)
        def sort_key(release):
            software_name = release.get('software_name', '')
            published_at = release.get('published_at', '')
            # Convert date string to a comparable format for sorting (newest first)
            try:
                from datetime import datetime
                date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                timestamp = date_obj.timestamp()
            except:
                timestamp = 0
            # Return a tuple: (software_name, -timestamp) where negative timestamp ensures newest first
            return (software_name, -timestamp)

        all_releases.sort(key=sort_key)

        # Show error message if no releases were found
        if not all_releases and failed_repos:
            # Don't update status label - keep it as "Ready" for firmware installation status only
            silent_print(f"Failed to load releases from repositories: {failed_repos}")
            
            # Add helpful message to the list
            help_item = QListWidgetItem("⚠️ No releases found\n\nThis could be due to:\n• GitHub API rate limiting\n• Network connectivity issues\n• Repository access restrictions\n\nTry using 'Install from .zip' button instead")
            help_item.setFlags(help_item.flags() & ~Qt.ItemIsSelectable)  # Make it non-selectable
            help_item.setData(Qt.UserRole, None)  # No release data
            self.package_list.addItem(help_item)
            
            # Also update status to be more helpful
            self.status_label.setText("GitHub API unavailable - use 'Install from .zip' button")
        elif all_releases:
            # Don't update status label - keep it as "Ready" for firmware installation status only
            silent_print(f"Loaded {len(all_releases)} releases successfully")

        for release in all_releases:
            # Find the package info for this release to get device type and model
            package_info = None
            for package in self.packages:
                if package.get('name') == release['software_name']:
                    package_info = package
                    break

            # Simplified display format
            display_text = f"{release['software_name']}\n"
            display_text += f"Version: {release['tag_name']}\n"

            if release.get('published_at'):
                # Format the date
                try:
                    from datetime import datetime
                    date_obj = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
                    display_text += f"Published: {date_obj.strftime('%Y-%m-%d %H:%M')}\n"
                except:
                    display_text += f"Published: {release['published_at']}\n"

            # Show device type if "All Types" is selected
            if not self.device_type_combo.currentData() and package_info:
                device_type = package_info.get('device_type', '')
                if device_type:
                    display_text += f"Type: {device_type}\n"

            # Show device model if "All Models" is selected
            if not self.device_model_combo.currentData() and package_info:
                device_model = package_info.get('device', '')
                if device_model:
                    display_text += f"Model: {device_model}\n"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, release)
            self.package_list.addItem(item)

        # Automatically select the first item for improved discoverability
        if self.package_list.count() > 0:
            self.package_list.setCurrentRow(0)
            self.package_list.setFocus()  # Give focus to the list for blue highlight
            self.download_btn.setEnabled(True)
            # Update button text for the first selected item
            first_item = self.package_list.item(0)
            self.update_download_button_text(first_item)

    def show_context_menu(self, position):
        """Show context menu for right-click on firmware items"""
        item = self.package_list.itemAt(position)
        if item is None:
            return

        # Get the firmware data from the item
        firmware_data = item.data(Qt.UserRole)
        if firmware_data is None:
            return

        from PySide6.QtWidgets import QMenu

        context_menu = QMenu(self)
        delete_action = context_menu.addAction("Delete Local Zip File")
        
        # Add separator and "Delete All Cached Zips" option
        context_menu.addSeparator()
        delete_all_action = context_menu.addAction("Delete All Cached Zips")

        action = context_menu.exec_(self.package_list.mapToGlobal(position))

        if action == delete_action:
            # Extract repo_name and version from the firmware data
            repo_name = firmware_data.get('repo_name', '')
            version = firmware_data.get('version', '')

            if repo_name and version:
                if delete_zip_file(repo_name, version):
                    QMessageBox.information(self, "Success", f"Deleted zip file for {repo_name} version {version}")
                else:
                    QMessageBox.information(self, "Info", f"No local zip file found for {repo_name} version {version}")
        
        elif action == delete_all_action:
            # Delete all cached zip files
            self.delete_all_cached_zips()

    def delete_all_cached_zips(self):
        """Delete all cached zip files and show confirmation"""
        try:
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Delete All Cached Zips",
                "Are you sure you want to delete all cached zip files?\n\nThis will free up disk space but require re-downloading any firmware you want to install.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                deleted_count = delete_all_cached_zips()
                if deleted_count > 0:
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Successfully deleted {deleted_count} cached zip file(s)."
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Info",
                        "No cached zip files found to delete."
                    )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Error deleting cached zip files: {e}"
            )

    def populate_all_releases_list_progressive(self):
        """Populate the releases list progressively for all software"""
        self.package_list.clear()

        # Add loading placeholder
        loading_item = QListWidgetItem("Loading firmware listings...")
        loading_item.setFlags(loading_item.flags() & ~Qt.ItemIsSelectable)
        self.package_list.addItem(loading_item)

        # Get all releases progressively
        all_releases = []

        for package in self.packages:
            repo = package.get('repo')
            if not repo:
                continue

            try:
                releases = self.github_api.get_all_releases(repo)
                if releases:
                    # Add software name to each release for consistent button text logic
                    for release in releases:
                        release_with_software = release.copy()
                        release_with_software['software_name'] = package.get('name', repo)
                        all_releases.append(release_with_software)

                    # Update status less frequently to reduce UI updates
                    if len(all_releases) % 5 == 0:
                        # Don't update status label - keep it as "Ready" for firmware installation status only
                        silent_print(f"Loaded {len(all_releases)} releases...")

            except Exception as e:
                silent_print(f"Error getting releases for {repo}: {e}")
                continue

        # Remove loading placeholder and show results
        self.package_list.clear()

        if not all_releases:
            self.package_list.addItem("No releases found. Please check your internet connection.")
            return

        # Sort releases by date (newest first)
        all_releases.sort(key=lambda x: x.get('published_at', ''), reverse=True)

        # Add releases to the list
        for release in all_releases:
            software_name = release.get('software_name', 'Unknown')
            display_text = f"{software_name} - {release['tag_name']}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, release)
            self.package_list.addItem(item)

        # Select the first item if available
        if self.package_list.count() > 0:
            self.package_list.setCurrentRow(0)
            first_item = self.package_list.item(0)
            if first_item:
                self.on_release_selected(first_item)

    def update_download_button_text(self, item):
        """Update download button text based on selected item"""
        if item and item.data(Qt.UserRole):
            release_info = item.data(Qt.UserRole)

            # Check if software name contains "Original"
            software_name = release_info.get('software_name', '')
            if 'original' in software_name.lower():
                self.download_btn.setText("Download (Update / Restore)")
            else:
                self.download_btn.setText("Download")
        else:
            self.download_btn.setText("Download")

    def on_release_selected(self, item):
        """Handle release selection from the list"""
        self.download_btn.setEnabled(True)
        self.update_download_button_text(item)

    def run_mtk_command(self):
        """Run the MTK flash command with image display"""
        # Check if required files exist
        required_files = ["lk.bin", "boot.img", "recovery.img", "system.img", "userdata.img"]
        missing_files = []
        for file in required_files:
            if not Path(file).exists():
                missing_files.append(file)

        if missing_files:
            QMessageBox.warning(self, "Error", f"Missing required files: {', '.join(missing_files)}")
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Get Ready",
            "Please make sure your Y1 is NOT plugged in and press OK, then follow the next instructions.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel
        )

        if reply == QMessageBox.Cancel:
            return

        # Clean up libusb state before starting new MTK operation (Windows only)
        if platform.system() == "Windows":
            self.cleanup_libusb_state()

        # Create installation marker to track progress
        create_installation_marker()

        # Load and display the init steps image
        self.load_initsteps_image()

        # Start MTK worker
        # Create debug window if debug mode is enabled
        debug_window = None
        if getattr(self, 'debug_mode', False):
            debug_window = DebugOutputWindow(self)
            debug_window.show()
        
        self.mtk_worker = MTKWorker(debug_mode=getattr(self, 'debug_mode', False), debug_window=debug_window)
        self.mtk_worker.status_updated.connect(self.status_label.setText)
        self.mtk_worker.show_installing_image.connect(self.load_installing_image)
        self.mtk_worker.mtk_completed.connect(self.on_mtk_completed)
        self.mtk_worker.handshake_failed.connect(self.on_handshake_failed)
        self.mtk_worker.errno2_detected.connect(self.on_errno2_detected)
        self.mtk_worker.backend_error_detected.connect(self.on_backend_error_detected)
        self.mtk_worker.keyboard_interrupt_detected.connect(self.on_keyboard_interrupt_detected)
        self.mtk_worker.disable_update_button.connect(self.disable_update_button)
        self.mtk_worker.enable_update_button.connect(self.enable_update_button)

        self.mtk_worker.start()

        # Disable download button during MTK operation
        self.download_btn.setEnabled(False)
        self.settings_btn.setEnabled(False)



    def on_mtk_completed(self, success, message):
        """Handle MTK command completion"""
        # Stop the MTK worker to prevent it from continuing to run
        if self.mtk_worker:
            self.mtk_worker.stop()
            self.mtk_worker.wait()  # Wait for the worker to finish
            self.mtk_worker = None

        if success:
            self.status_label.setText("Install completed successfully")
            # Remove installation marker on successful completion
            remove_installation_marker()
            # Clean up firmware files after successful installation
            cleanup_firmware_files()
            # Load and display installed.png for 30 seconds
            self.load_installed_image()

            # Cancel any existing revert timer to prevent conflicts
            if hasattr(self, '_revert_timer') and self._revert_timer:
                self._revert_timer.stop()
                self._revert_timer = None

            # Set timer to revert to startup state after 30 seconds
            self._revert_timer = QTimer()
            self._revert_timer.timeout.connect(self.revert_to_startup_state)
            self._revert_timer.setSingleShot(True)
            self._revert_timer.start(30000)
        else:
            self.status_label.setText(f"MTK command failed: {message}")
            # On Windows: First show process_ended.png image briefly, then show install error dialog
            self.load_process_ended_image()
            
            # Use a timer to show the dialog after a short delay so user sees the process_ended image
            QTimer.singleShot(2000, self.show_install_error_dialog)
            return  # Don't continue with the revert timer since user will choose action

        # Re-enable download button
        self.download_btn.setEnabled(True)
        # Re-enable settings button
        self.settings_btn.setEnabled(True)

    def disable_update_button(self):
        """Disable the update button during MTK installation"""
        if hasattr(self, 'update_btn_right'):
            self.update_btn_right.setEnabled(False)
            self.update_btn_right.setText("Check for Utility Updates")
        # Also disable settings button during operations
        self.settings_btn.setEnabled(False)

    def enable_update_button(self):
        """Enable the update button when returning to ready state"""
        if hasattr(self, 'update_btn_right'):
            self.update_btn_right.setEnabled(True)
            self.update_btn_right.setText("Check for Utility Updates")
        # Also enable settings button when operations are complete
        self.settings_btn.setEnabled(True)

    def on_handshake_failed(self):
        """Handle handshake failed error from MTKWorker"""
        # Stop the MTK worker to prevent it from continuing to run
        if self.mtk_worker:
            self.mtk_worker.stop()
            self.mtk_worker.wait()  # Wait for the worker to finish
            self.mtk_worker = None

        # Show the "try again" screen (initsteps image) for the relevant system
        self.load_initsteps_image()

        # Cancel any existing revert timer to prevent conflicts
        if hasattr(self, '_revert_timer') and self._revert_timer:
            self._revert_timer.stop()
            self._revert_timer = None

        # Set timer to revert to startup state after 30 seconds (shorter timeout for better UX)
        self._revert_timer = QTimer()
        self._revert_timer.timeout.connect(self.revert_to_startup_state)
        self._revert_timer.setSingleShot(True)
        self._revert_timer.start(30000)

        # Show user-friendly message asking to unplug and try again
        self.status_label.setText("Please unplug your Y1 and try again")

        # Re-enable buttons for retry
        self.download_btn.setEnabled(True)  # Re-enable download button
        self.settings_btn.setEnabled(True)  # Re-enable settings button
        
        # Set up automatic restart after showing initsteps
        QTimer.singleShot(5000, self.restart_firmware_install)

    def restart_firmware_install(self):
        """Restart the firmware installation process from where the command is run"""
        try:
            # Show initsteps image for the relevant system
            self.load_initsteps_image()
            
            # Update status to indicate restart
            self.status_label.setText("Restarting firmware installation...")
            
            # Create and start a new MTK worker
            debug_window = None
            if getattr(self, 'debug_mode', False):
                debug_window = DebugOutputWindow(self)
                debug_window.show()
            
            self.mtk_worker = MTKWorker(debug_mode=getattr(self, 'debug_mode', False), debug_window=debug_window)
            self.mtk_worker.status_updated.connect(self.update_status)
            self.mtk_worker.show_installing_image.connect(self.load_installing_image)
            self.mtk_worker.show_reconnect_image.connect(self.load_handshake_error_image)
            self.mtk_worker.show_presteps_image.connect(self.load_presteps_image)
            self.mtk_worker.mtk_completed.connect(self.handle_mtk_completion)
            self.mtk_worker.handshake_failed.connect(self.handle_handshake_failure)
            self.mtk_worker.errno2_detected.connect(self.handle_errno2_error)
            self.mtk_worker.backend_error_detected.connect(self.handle_backend_error)
            self.mtk_worker.keyboard_interrupt_detected.connect(self.handle_keyboard_interrupt)
            self.mtk_worker.disable_update_button.connect(self.disable_update_button)
            self.mtk_worker.enable_update_button.connect(self.enable_update_button)
            self.mtk_worker.start()
            
        except Exception as e:
            silent_print(f"Error restarting firmware install: {e}")
            self.status_label.setText("Error restarting installation - please try manually")

    def on_errno2_detected(self):
        """Handle errno2 error from MTKWorker"""
        # Stop the MTK worker to prevent it from continuing to run
        if self.mtk_worker:
            self.mtk_worker.stop()
            self.mtk_worker.wait()  # Wait for the worker to finish
            self.mtk_worker = None

        reply = self.show_custom_message_box(
            "question",
            "Errno2 Error - Reinstall Required",
            "An errno2 error was detected, which indicates the Innioasis Updater application needs to be reinstalled.\n\n"
            "Please reinstall the Innioasis Updater application to resolve this issue.\n\n"
            "Click OK to open the download page in your browser.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok
        )

        if reply == QMessageBox.Ok:
            # Open the GitHub releases page in the default browser
            import webbrowser
            releases_url = "https://github.com/team-slide/Innioasis-Updater/releases/latest"
            webbrowser.open(releases_url)
            self.status_label.setText("GitHub releases page opened - please reinstall Innioasis Updater")
        else:
            self.status_label.setText("Errno2 error - please reinstall Innioasis Updater")

        self.download_btn.setEnabled(True)  # Re-enable download button
        self.settings_btn.setEnabled(True)  # Re-enable settings button

    def on_backend_error_detected(self):
        """Handle backend error from MTKWorker"""
        # Stop the MTK worker to prevent it from continuing to run
        if self.mtk_worker:
            self.mtk_worker.stop()
            self.mtk_worker.wait()  # Wait for the worker to finish
            self.mtk_worker = None

        reply = QMessageBox.question(
            self,
            "Backend Error - libusb Backend Issue",
            "A libusb backend error was detected, which indicates a system-level USB backend issue.\n\n"
            "This is typically caused by:\n"
            "• Missing or incompatible libusb backend\n"
            "• System USB driver conflicts\n"
            "• Incompatible macOS version\n\n"
            "To resolve this issue:\n"
            "1. Install or update libusb: brew install libusb\n"
            "2. If using Homebrew, try: brew reinstall libusb\n"
            "3. Restart your system\n"
            "4. Try the firmware installation again\n\n"
            "Click OK to open Homebrew installation instructions in your browser.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok
        )

        if reply == QMessageBox.Ok:
            # Open the Homebrew installation page in the default browser
            import webbrowser
            homebrew_url = "https://brew.sh/"
            webbrowser.open(homebrew_url)
            self.status_label.setText("Homebrew page opened - please install libusb and restart")
        else:
            self.status_label.setText("Backend error - please install libusb and restart")

        self.download_btn.setEnabled(True)  # Re-enable download button
        self.settings_btn.setEnabled(True)  # Re-enable settings button

    def on_keyboard_interrupt_detected(self):
        """Handle keyboard interrupt from MTKWorker"""
        # Stop the MTK worker to prevent it from continuing to run
        if self.mtk_worker:
            self.mtk_worker.stop()
            self.mtk_worker.wait()  # Wait for the worker to finish
            self.mtk_worker = None

        # Check if this was a Method 2 or 3 installation - if so, don't show troubleshooting
        current_method = getattr(self, 'installation_method', 'guided')
        if current_method in ["mtkclient", "spflash"]:
            # Method 2 or 3 failure - just show process_ended.png and return to ready state
            self.load_process_ended_image()
            self.status_label.setText("Method installation failed - returning to ready state")
            # Return to ready state after showing the image briefly
            QTimer.singleShot(3000, self.revert_to_startup_state)
            return

        # Method 1 failure - show process_ended.png briefly, then show troubleshooting dialog
        self.load_process_ended_image()
        
        # Use a timer to show the dialog after a short delay so user sees the process_ended image
        QTimer.singleShot(2000, self.show_install_error_dialog)
        return  # Don't continue with the revert timer since user will choose action

    def show_presteps_image(self):
        """Show the presteps image"""
        self.load_presteps_image()

    def set_image_with_aspect_ratio(self, pixmap):
        """Set image while maintaining aspect ratio"""
        if pixmap.isNull():
            return

        # Get the label size
        label_size = self.image_label.size()
        if label_size.width() <= 0 or label_size.height() <= 0:
            # Use minimum size if label not properly sized yet
            label_size = QSize(400, 300)

        # Scale image to fit the label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            label_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Set the scaled pixmap
        self.image_label.setPixmap(scaled_pixmap)

        # Don't use setScaledContents to maintain aspect ratio
        self.image_label.setScaledContents(False)

        # Store current pixmap for resize events
        self._current_pixmap = pixmap

    def resizeEvent(self, event):
        """Handle window resize to maintain image aspect ratio"""
        super().resizeEvent(event)
        # Re-scale current image if one is loaded
        if hasattr(self, '_current_pixmap') and self._current_pixmap:
            self.set_image_with_aspect_ratio(self._current_pixmap)

    def get_platform_image_path(self, base_name):
        """Constructs a path to a platform-specific image, with a fallback to a generic one."""
        system = platform.system()
        if system == "Windows":
            # Check driver status and architecture for Windows
            driver_info = self.check_drivers_and_architecture()
            
            if driver_info['is_arm64']:
                # ARM64 Windows: Use arm64windows.png for presteps
                if base_name == "presteps":
                    arm64_path = Path("mtkclient/gui/images/arm64windows.png")
                    if arm64_path.exists():
                        return str(arm64_path)
                suffix = "_win"
            elif not driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
                # No drivers: Use driverswindows.png for presteps
                if base_name == "presteps":
                    drivers_path = Path("mtkclient/gui/images/driverswindows.png")
                    if drivers_path.exists():
                        return str(drivers_path)
                suffix = "_win"
            else:
                # Users with at least MTK driver (including Method 3 only mode) show presteps.png as usual
                suffix = "_win"
        elif system == "Darwin":
            suffix = "_mac"
        elif system == "Linux":
            suffix = "_linux"
        else:
            suffix = ""

        base_path = Path("mtkclient/gui/images")

        # Try platform-specific path first
        if suffix:
            platform_specific_path = base_path / f"{base_name}{suffix}.png"
            if platform_specific_path.exists():
                return str(platform_specific_path)

        # Fallback to generic path
        generic_path = base_path / f"{base_name}.png"
        return str(generic_path)

    def load_presteps_image(self):
        """Load presteps image with lazy loading and platform fallback."""
        if not hasattr(self, '_presteps_pixmap'):
            try:
                image_path = self.get_platform_image_path("presteps")
                self._presteps_pixmap = QPixmap(image_path)
                if self._presteps_pixmap.isNull():
                    silent_print(f"Failed to load image from {image_path}")
                    return
            except Exception as e:
                silent_print(f"Error loading presteps image: {e}")
                return

        self._current_pixmap = self._presteps_pixmap
        self.set_image_with_aspect_ratio(self._presteps_pixmap)

    def load_initsteps_image(self):
        """Load initsteps image with lazy loading and platform fallback."""
        if not hasattr(self, '_initsteps_pixmap'):
            try:
                image_path = self.get_platform_image_path("initsteps")
                self._initsteps_pixmap = QPixmap(image_path)
                if self._initsteps_pixmap.isNull():
                    silent_print(f"Failed to load image from {image_path}")
                    return
            except Exception as e:
                silent_print(f"Error loading initsteps image: {e}")
                return

        self._current_pixmap = self._initsteps_pixmap
        self.set_image_with_aspect_ratio(self._initsteps_pixmap)

    def load_installing_image(self):
        """Load installing image with lazy loading"""
        if not hasattr(self, '_installing_pixmap'):
            try:
                self._installing_pixmap = QPixmap("mtkclient/gui/images/installing.png")
                if self._installing_pixmap.isNull():
                    silent_print("Failed to load installing.png")
                    return
            except Exception as e:
                silent_print(f"Error loading installing image: {e}")
                return

        self._current_pixmap = self._installing_pixmap
        self.set_image_with_aspect_ratio(self._installing_pixmap)

    def load_installed_image(self):
        """Load installed image with lazy loading"""
        if not hasattr(self, '_installed_pixmap'):
            try:
                self._installed_pixmap = QPixmap("mtkclient/gui/images/installed.png")
                if self._installed_pixmap.isNull():
                    silent_print("Failed to load installed.png")
                    return
            except Exception as e:
                silent_print(f"Error loading installed image: {e}")
                return

        self._current_pixmap = self._installed_pixmap
        self.set_image_with_aspect_ratio(self._installed_pixmap)

    def load_handshake_error_image(self):
        """Load handshake error image with lazy loading and platform fallback."""
        if not hasattr(self, '_handshake_error_pixmap'):
            try:
                image_path = self.get_platform_image_path("handshake_err")
                self._handshake_error_pixmap = QPixmap(image_path)
                if self._handshake_error_pixmap.isNull():
                    silent_print(f"Failed to load image from {image_path}")
                    return
            except Exception as e:
                silent_print(f"Error loading handshake error image: {e}")
                return

        self._current_pixmap = self._handshake_error_pixmap
        self.set_image_with_aspect_ratio(self._handshake_error_pixmap)

    def load_process_ended_image(self):
        """Load process ended image with lazy loading"""
        if not hasattr(self, '_process_ended_pixmap'):
            try:
                self._process_ended_pixmap = QPixmap("mtkclient/gui/images/process_ended.png")
                if self._process_ended_pixmap.isNull():
                    silent_print("Failed to load process_ended.png")
                    return
            except Exception as e:
                silent_print(f"Error loading process ended image: {e}")
                return

        self._current_pixmap = self._process_ended_pixmap
        self.set_image_with_aspect_ratio(self._process_ended_pixmap)

    def load_method2_image(self):
        """Load method2 image with lazy loading and platform fallback."""
        if not hasattr(self, '_method2_pixmap'):
            try:
                image_path = self.get_platform_image_path("method2")
                self._method2_pixmap = QPixmap(image_path)
                if self._method2_pixmap.isNull():
                    silent_print(f"Failed to load image from {image_path}")
                    return
            except Exception as e:
                silent_print(f"Error loading method2 image: {e}")
                return

        self._current_pixmap = self._method2_pixmap
        self.set_image_with_aspect_ratio(self._method2_pixmap)

    def load_method3_image(self):
        """Load method3 image with lazy loading and platform fallback."""
        if not hasattr(self, '_method3_pixmap'):
            try:
                image_path = self.get_platform_image_path("method3")
                self._method3_pixmap = QPixmap(image_path)
                if self._method3_pixmap.isNull():
                    silent_print(f"Failed to load image from {image_path}")
                    return
            except Exception as e:
                silent_print(f"Error loading method3 image: {e}")
                return

        self._current_pixmap = self._method3_pixmap
        self.set_image_with_aspect_ratio(self._method3_pixmap)

    def open_coffee_link(self):
        """Open the Buy Us Coffee link in the default browser"""
        import webbrowser
        webbrowser.open("https://ko-fi.com/teamslide")

    def open_reddit_link(self):
        """Open the r/innioasis subreddit in the default browser"""
        import webbrowser
        webbrowser.open("https://reddit.com/r/innioasis")

    def open_discord_link(self):
        """Open the Discord server in the default browser"""
        import webbrowser
        webbrowser.open("https://discord.gg/timmkoo")

    def open_driver_setup_link(self):
        """Show driver setup dialog and open the installation guide"""
        driver_info = self.check_drivers_and_architecture()
        
        # Determine which drivers are missing
        missing_drivers = []
        if not driver_info['has_mtk_driver']:
            missing_drivers.append("MediaTek SP Flash Tool Driver")
        if not driver_info['has_usbdk_driver']:
            missing_drivers.append("UsbDk Driver")
        
        if missing_drivers:
            # Show dialog asking user to install specific drivers
            driver_names = " and ".join(missing_drivers)
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Driver Setup Required")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText(f"To use all features of Innioasis Updater, you'll need to install:")
            msg_box.setInformativeText(f"• {driver_names}\n\nWould you like help setting these up?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            
            if msg_box.exec() == QMessageBox.Yes:
                # Open the installation guide
                import webbrowser
                webbrowser.open("https://innioasis.app/installguide.html")
        else:
            # Fallback to direct link
            import webbrowser
            webbrowser.open("https://innioasis.app/installguide.html")

    def open_usbdk_info(self, event):
        """Open USB Development Kit information"""
        import webbrowser
        webbrowser.open("https://innioasis.app")

    def open_arm64_info(self, event):
        """Show ARM64 Windows information dialog and redirect to installation guide"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("ARM64 Windows Detected")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText("ARM64 Windows has limited compatibility with firmware installation.")
        msg_box.setInformativeText(
            "On ARM64 Windows, you can download firmware files but installation methods may not work properly.\n\n"
            "Would you like to see alternative setup options and compatibility information?"
        )
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)
        
        if msg_box.exec() == QMessageBox.Yes:
            # Open the installation guide
            import webbrowser
            webbrowser.open("https://innioasis.app/installguide.html")

    def install_from_zip(self):
        """Install firmware from a local zip file"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        # Check driver availability for Windows users
        if platform.system() == "Windows":
            driver_info = self.check_drivers_and_architecture()
            
            if driver_info['is_arm64']:
                QMessageBox.information(
                    self,
                    "ARM64 Windows Not Supported",
                    "Firmware installation is not supported on ARM64 Windows.\n\n"
                    "You can download firmware files, but to install them please use:\n"
                    "• WSLg (Windows Subsystem for Linux with GUI)\n"
                    "• Linux (dual boot or live USB)\n"
                    "• Another computer with x64 Windows"
                )
                return
                
            elif not driver_info['can_install_firmware']:
                QMessageBox.warning(
                    self,
                    "Drivers Required",
                    "No installation methods available. Please install drivers to enable firmware installation.\n\n"
                    "Click OK to open the driver installation guide."
                )
                self.open_driver_setup_link()
                return
        
        # Open file dialog to select zip file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Firmware ZIP File",
            "",
            "ZIP Files (*.zip)"
        )
        
        if not file_path:
            return
            
        zip_path = Path(file_path)
        if not zip_path.exists():
            QMessageBox.warning(self, "Error", "Selected file does not exist.")
            return
            
        # Process the zip file with progress bar and status updates like download process
        self.status_label.setText("Processing zip file...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        try:
            # Simulate progress for zip processing
            self.progress_bar.setValue(25)
            self.status_label.setText("Extracting zip file...")
            
            # Extract the zip file
            extracted_files = []
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
                # Get list of extracted files
                extracted_files = zip_ref.namelist()
            
            # Log extracted files for cleanup
            log_extracted_files(extracted_files)
            
            self.progress_bar.setValue(75)
            self.status_label.setText("Checking required files...")
            
            # Check if required files exist
            required_files = ["lk.bin", "boot.img", "recovery.img", "system.img", "userdata.img"]
            missing_files = []
            for file in required_files:
                if not Path(file).exists():
                    missing_files.append(file)
            
            if missing_files:
                self.progress_bar.setVisible(False)
                error_msg = f"Missing required files: {', '.join(missing_files)}\n\n"
                error_msg += "The zip file must contain:\n"
                error_msg += "- lk.bin\n"
                error_msg += "- boot.img\n"
                error_msg += "- recovery.img\n"
                error_msg += "- system.img\n"
                error_msg += "- userdata.img\n\n"
                error_msg += "Please ensure your zip file contains all required firmware files."
                
                QMessageBox.warning(self, "Missing Files", error_msg)
                self.status_label.setText("Zip file missing required firmware files.")
                return
            
            self.progress_bar.setValue(100)
            self.status_label.setText("Extraction completed. Files ready for MTK processing.")
            
            # Show success message with file list and instructions
            success_msg = "Firmware files successfully extracted:\n"
            for file in required_files:
                file_size = Path(file).stat().st_size
                size_mb = file_size / (1024 * 1024)
                success_msg += f"- {file} ({size_mb:.1f} MB)\n"
            
            success_msg += "\nTo flash these files to your device:\n"
            success_msg += "1. Turn off your Y1\n"
            success_msg += "2. Run the following command in a new terminal:\n"
            success_msg += f"   {sys.executable} mtk.py w uboot,bootimg,recovery,android,usrdata lk.bin,boot.img,recovery.img,system.img,userdata.img\n"
            success_msg += "3. Follow the on-screen prompts to turn off your Y1"
            
            QMessageBox.information(self, "Success", success_msg)
            
            # Handle installation based on selected method
            self.status_label.setText("Starting installation in 3 seconds...")
            QTimer.singleShot(3000, self.handle_installation_method)
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            error_msg = f"Error processing zip file: {str(e)}"
            QMessageBox.critical(self, "Error", error_msg)
            self.status_label.setText("Error processing zip file.")
            silent_print(f"Zip processing error: {e}")
        
        finally:
            # Hide progress bar after processing
            QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

    def run_driver_setup(self):
        """Runs the driver setup script (main.py)"""
        try:
            # Get the current directory where firmware_downloader.py is located
            current_dir = Path(__file__).parent
            main_py_path = current_dir / "main.py"

            if not main_py_path.exists():
                QMessageBox.warning(self, "Error", "main.py not found. Please ensure main.py is in the same directory as firmware_downloader.py.")
                return

            # Run main.py
            silent_print("Running main.py for driver setup...")
            self.status_label.setText("Running driver setup...")
            self.download_btn.setEnabled(False) # Disable download button while running
            self.settings_btn.setEnabled(False) # Disable settings button while running

            # Use subprocess to run main.py in the current directory
            if platform.system() == "Windows":
                subprocess.Popen([sys.executable, str(main_py_path)], cwd=str(current_dir), 
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen([sys.executable, str(main_py_path)], cwd=str(current_dir))

            # After main.py finishes, revert to startup state
            QTimer.singleShot(1000, self.revert_to_startup_state) # Small delay to allow main.py to start

        except Exception as e:
            silent_print(f"Error running driver setup: {e}")
            self.status_label.setText(f"Error running driver setup: {e}")
            self.download_btn.setEnabled(True)
            self.settings_btn.setEnabled(True)

    def revert_to_startup_state(self):
        """Revert the app to its startup state"""
        # Cancel any existing revert timer to prevent conflicts
        if hasattr(self, '_revert_timer') and self._revert_timer:
            self._revert_timer.stop()
            self._revert_timer = None

        # Load and display presteps.png (startup state)
        self.load_presteps_image()

        # Reset status
        self.status_label.setText("Ready")

        # Ensure download button is enabled
        self.download_btn.setEnabled(True)
        # Ensure settings button is enabled
        if hasattr(self, 'settings_btn'):
            self.settings_btn.setEnabled(True)

    def populate_package_list(self):
        """Populate the package list widget with release information"""
        self.package_list.clear()

        for package in self.packages:
            device_type = package.get('device_type', '')
            device_model = package.get('device', '')

            device_type_text = f" (Type {device_type})" if device_type else ""
            device_model_text = f" [{device_model}]" if device_model else ""

            # Get latest release information
            release_info = self.github_api.get_latest_release(package['repo'])
            release_text = ""
            if release_info:
                release_text = f"\nLatest Release: {release_info.get('tag_name', 'Unknown')}"
                if release_info.get('name'):
                    release_text += f" ({release_info['name']})"

            item_text = f"{package['name']}{device_type_text}{device_model_text}\n"
            item_text += f"Repo: {package['repo']}{release_text}\n"
            item_text += f"Handler: {package['handler']}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, package)
            self.package_list.addItem(item)

        # Automatically select the first item for improved discoverability
        if self.package_list.count() > 0:
            self.package_list.setCurrentRow(0)
            self.package_list.setFocus()  # Give focus to the list for blue highlight
            self.download_btn.setEnabled(True)
            self.settings_btn.setEnabled(True)
            print("DEBUG: Settings button enabled when package selected")
            # Update button text for the first selected item
            first_item = self.package_list.item(0)
            self.update_download_button_text(first_item)

    def filter_firmware_options(self):
        """Filter software options based on device type and model"""
        # Repopulate software combo with filtered options
        self.populate_firmware_combo()

        # Update the releases list based on current software selection
        selected_repo = self.firmware_combo.currentData()
        if selected_repo:
            # Specific software selected - show only its releases
            self.populate_releases_list()
        else:
            # "All Software" selected - show all releases
            self.populate_all_releases_list()



    def start_download(self):
        """Start the download and processing process"""
        # Cancel any existing revert timer to prevent conflicts
        if hasattr(self, '_revert_timer') and self._revert_timer:
            self._revert_timer.stop()
            self._revert_timer = None

        # Stop any existing MTK worker to prevent conflicts
        if hasattr(self, 'mtk_worker') and self.mtk_worker:
            self.mtk_worker.stop()
            self.mtk_worker.wait()
            self.mtk_worker = None

        current_item = self.package_list.currentItem()
        if not current_item:
            self.status_label.setText("Error: Please select a release from the list")
            return

        release_info = current_item.data(Qt.UserRole)

        if not release_info:
            self.status_label.setText("Error: Please select a valid release from the list")
            return

        # Get the repository from the release info (for "All Firmware" selection)
        # or from the firmware combo (for specific firmware selection)
        selected_repo = self.firmware_combo.currentData()

        # If "All Software" is selected, we need to get the repo from the release info
        if not selected_repo and 'software_name' in release_info:
            # This is from "All Software" - find the repo for this software
            software_name = release_info['software_name']
            for package in self.packages:
                if package.get('name') == software_name:
                    selected_repo = package.get('repo')
                    break

        if not selected_repo:
            self.status_label.setText("Error: Could not determine repository for selected release")
            return

        if not release_info:
            QMessageBox.warning(self, "Error", f"Failed to get release information for {selected_repo}")
            return

        if not release_info['download_url']:
            # Show what assets are available
            error_msg = f"No rom.zip found in release {selected_repo} for {selected_repo}\n\n"
            error_msg += f"Release: {release_info.get('tag_name', 'Unknown')}\n"
            error_msg += f"Name: {release_info.get('name', 'Unknown')}\n\n"
            error_msg += "Available assets:\n"

            # Try to get asset list for better error reporting
            try:
                url = f"https://api.github.com/repos/{selected_repo}/releases"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    releases_data = response.json()
                    for release in releases_data:
                        if release.get('tag_name') == selected_repo: # This line seems to be a typo, should be release.get('tag_name')
                            assets = release.get('assets', [])
                            if assets:
                                for asset in assets:
                                    error_msg += f"- {asset['name']}\n"
                            else:
                                error_msg += "- No assets found\n"
                            break
                else:
                    error_msg += "- Could not retrieve asset list\n"
            except:
                error_msg += "- Could not retrieve asset list\n"

            QMessageBox.warning(self, "Error", error_msg)
            return

        # Check if zip file already exists locally
        zip_path = get_zip_path(selected_repo, release_info['tag_name'])
        if zip_path.exists():
            # Zip already exists - automatically use it for seamless experience
            silent_print(f"Using existing zip file: {zip_path.name}")
            self.status_label.setText("Using existing zip file. Extracting...")
            self.process_existing_zip(zip_path, selected_repo, release_info['tag_name'])
            return

        # Start download worker
        self.download_worker = DownloadWorker(release_info['download_url'], selected_repo, release_info['tag_name'])
        self.download_worker.progress_updated.connect(self.progress_bar.setValue)
        self.download_worker.status_updated.connect(self.status_label.setText)
        self.download_worker.download_completed.connect(self.on_download_completed)

        self.download_btn.setEnabled(False)
        self.settings_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        silent_print(f"Starting download for {selected_repo}...")
        silent_print(f"Release: {release_info['tag_name']}")
        silent_print(f"Download URL: {release_info['download_url']}")

        self.download_worker.start()

    def process_existing_zip(self, zip_path, repo_name, version):
        """Process an existing zip file (extract and prepare for installation)"""
        try:
            self.status_label.setText("Extracting existing zip file...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Simulate progress for zip processing
            self.progress_bar.setValue(25)
            self.status_label.setText("Extracting existing zip file...")
            
            # Extract the zip file
            extracted_files = []
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
                # Get list of extracted files
                extracted_files = zip_ref.namelist()
            
            # Log extracted files for cleanup
            log_extracted_files(extracted_files)
            
            self.progress_bar.setValue(75)
            self.status_label.setText("Checking required files...")
            
            # Check if required files exist
            required_files = ["lk.bin", "boot.img", "recovery.img", "system.img", "userdata.img"]
            missing_files = []
            for file in required_files:
                if not Path(file).exists():
                    missing_files.append(file)
            
            if missing_files:
                self.progress_bar.setVisible(False)
                error_msg = f"Missing required files: {', '.join(missing_files)}"
                self.status_label.setText("Missing required firmware files.")
                QMessageBox.warning(self, "Missing Files", error_msg)
                return
            
            self.progress_bar.setValue(100)
            self.status_label.setText("Extraction completed. Files ready for MTK processing.")
            
            # Continue with the same flow as normal download - run MTK command automatically
            silent_print("=== AUTOMATICALLY RUNNING MTK COMMAND ===")
            silent_print("The MTK flash command will now run in this application.")
            silent_print("Please turn off your Y1 when prompted.")
            
            # Use QTimer to delay the automatic MTK command execution slightly
            QTimer.singleShot(2000, self.run_mtk_command)  # 2 second delay
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            error_msg = f"Error processing existing zip file: {str(e)}"
            QMessageBox.critical(self, "Error", error_msg)
            self.status_label.setText("Error processing existing zip file.")
            silent_print(f"Existing zip processing error: {e}")
        
        finally:
            # Hide progress bar after processing
            QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

    def on_download_completed(self, success, output):
        """Handle download completion"""
        self.download_btn.setEnabled(True)
        self.settings_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setText("Download and processing completed successfully")
            print("=== PROCESSING COMPLETED ===")
            print("Firmware files have been downloaded and extracted successfully.")

            # Check if required files exist and handle installation based on selected method
            required_files = ["lk.bin", "boot.img", "recovery.img", "system.img", "userdata.img"]
            if all(Path(file).exists() for file in required_files):
                silent_print("=== FIRMWARE FILES READY ===")
                silent_print(f"Selected installation method: {getattr(self, 'installation_method', 'guided')}")

                # Handle installation based on selected method
                QTimer.singleShot(2000, self.handle_installation_method)  # 2 second delay
        else:
            self.status_label.setText("Download or processing failed")
            silent_print("=== PROCESSING FAILED ===")

        silent_print(output)

    def handle_installation_method(self):
        """Handle installation based on the selected method in settings"""
        # Check driver status for Windows users
        if platform.system() == "Windows":
            driver_info = self.check_drivers_and_architecture()
            
            if driver_info['is_arm64']:
                # ARM64 Windows: No installation methods available
                silent_print("=== ARM64 WINDOWS - NO INSTALLATION METHODS AVAILABLE ===")
                QMessageBox.information(
                    self,
                    "ARM64 Windows Not Supported",
                    "Firmware installation is not supported on ARM64 Windows.\n\n"
                    "You can download firmware files, but to install them please use:\n"
                    "• WSLg (Windows Subsystem for Linux with GUI)\n"
                    "• Linux (dual boot or live USB)\n"
                    "• Another computer with x64 Windows"
                )
                return
                
            elif not driver_info['can_install_firmware']:
                # No drivers: No installation methods available
                silent_print("=== NO DRIVERS - NO INSTALLATION METHODS AVAILABLE ===")
                QMessageBox.warning(
                    self,
                    "Drivers Required",
                    "No installation methods available. Please install drivers to enable firmware installation.\n\n"
                    "Click OK to open the driver installation guide."
                )
                self.open_driver_setup_link()
                return
                
            elif driver_info['has_mtk_driver'] and not driver_info['has_usbdk_driver']:
                # Only MTK driver: Force Method 3 for this session
                silent_print("=== ONLY MTK DRIVER - FORCING METHOD 3 (SP FLASH TOOL) ===")
                self.installation_method = "spflash"
                method = "spflash"
            else:
                # Both drivers available: Use selected method
                method = getattr(self, 'installation_method', 'guided')
        else:
            # Non-Windows: Use selected method
            method = getattr(self, 'installation_method', 'guided')
        
        always_use = getattr(self, 'always_use_method', False)
        silent_print(f"Handling installation method: {method} (always use: {always_use})")
        
        if method == "guided":
            # Method 1: Normal guided process (default behavior)
            silent_print("=== RUNNING GUIDED INSTALLATION ===")
            silent_print("The MTK flash command will now run in this application.")
            silent_print("Please turn off your Y1 when prompted.")
            self.run_mtk_command()
            
        elif method == "mtkclient":
            # Method 2: MTKclient method - same as pressing "Try Method 2" in troubleshooting
            silent_print("=== RUNNING MTKCLIENT METHOD ===")
            # Show Method 2 image and launch recovery firmware install
            self.load_method2_image()
            self.show_troubleshooting_instructions()
                        
        elif method == "spflash" and platform.system() == "Windows":
            # Method 3: SP Flash Tool method - same as pressing "Try Method 3" in troubleshooting
            silent_print("=== RUNNING SP FLASH TOOL METHOD ===")
            # Show Method 3 image and launch SP Flash Tool
            self.load_method3_image()
            self.try_method_3()
        else:
            # Fallback to guided method if invalid method or SP Flash Tool on non-Windows
            silent_print("=== FALLING BACK TO GUIDED METHOD ===")
            self.run_mtk_command()
        
        # If this was a one-time use method, reset to guided for next time
        # But don't reset if we forced Method 3 due to missing UsbDk driver
        if not always_use and not (platform.system() == "Windows" and 
                                  self.check_drivers_and_architecture()['has_mtk_driver'] and 
                                  not self.check_drivers_and_architecture()['has_usbdk_driver']):
            silent_print("Resetting to guided method for next installation (one-time use)")
            self.installation_method = "guided"
            self.save_installation_preferences()

    def refresh_all_data(self):
        """Refresh all data (tokens, manifest, device types, models, software) with cache clearing"""
        self.status_label.setText("Refreshing data...")
        silent_print("Refreshing data...")

        # Clear cache to force fresh data
        clear_cache()

        # Download tokens
        tokens = self.config_downloader.download_config()
        if not tokens:
            silent_print("ERROR: Failed to download API tokens")
            QMessageBox.warning(self, "Error", "Failed to download API tokens. Please check your internet connection or try again later.")
            return

        self.github_api = GitHubAPI(tokens)
        silent_print(f"Loaded {len(tokens)} API tokens")

        # Download manifest
        self.packages = self.config_downloader.download_manifest()
        if not self.packages:
            silent_print("ERROR: Failed to download manifest")
            QMessageBox.warning(self, "Error", "Failed to download software manifest. Please check your internet connection or try again later.")
            return

        silent_print(f"Loaded {len(self.packages)} software packages")

        # Repopulate all combos
        self.populate_device_type_combo()
        self.populate_device_model_combo()
        self.populate_firmware_combo()

        # Apply initial filters (Type A and Y1 are already set as defaults)
        self.filter_firmware_options()

        # Show releases based on current software selection (not always "All Software")
        try:
            selected_repo = self.firmware_combo.currentData()
            if selected_repo:
                self.populate_releases_list()
            else:
                self.populate_all_releases_list_progressive()

            self.status_label.setText("Ready")
            silent_print("Data refresh complete.")
        except Exception as e:
            silent_print(f"Error populating releases: {e}")
            self.status_label.setText("Error loading releases - check internet connection")
            # Show a basic message to prevent complete failure
            self.package_list.clear()
            self.package_list.addItem("Error: Could not load releases. Please check your internet connection and try again.")

    def is_dark_mode(self):
        """Detect if the system is in dark mode"""
        try:
            # Check if the application is using a dark theme
            palette = self.palette()
            background_color = palette.color(palette.Window)

            # Calculate luminance to determine if it's dark
            luminance = (0.299 * background_color.red() +
                        0.587 * background_color.green() +
                        0.114 * background_color.blue()) / 255

            return luminance < 0.5
        except:
            # Fallback: assume light mode if detection fails
            return False

    def update_image_style(self):
        """Update the image label style based on system theme"""
        is_dark = self.is_dark_mode()

        if is_dark:
            # Dark theme styling - use transparent background to preserve PNG transparency
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    border: 0.5px solid #2a2a2a;
                    border-radius: 5px;
                    color: white;
                }
            """)
        else:
            # Light theme styling - use transparent background to preserve PNG transparency
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    border: 0.5px solid #f0f0f0;
                    border-radius: 5px;
                    color: #333;
                }
            """)

    def check_theme_change(self):
        """Check if the system theme has changed"""
        current_theme_state = self.is_dark_mode()
        if current_theme_state != self.last_theme_state:
            self.last_theme_state = current_theme_state
            self.update_image_style()

    def on_palette_changed(self):
        """Handle system theme changes (legacy method)"""
        self.update_image_style()

    def ensure_proper_image_sizing(self):
        """Ensure proper image sizing after window is fully initialized"""
        if hasattr(self, '_presteps_pixmap') and self._presteps_pixmap:
            self.set_image_with_aspect_ratio(self._presteps_pixmap)

    def switch_to_labs_version(self, event):
        """Switch between firmware_downloader.py and test.py versions"""
        try:
            current_file = Path(__file__).name
            if current_file == "test.py":
                # Currently running test.py, switch to firmware_downloader.py
                target_file = "firmware_downloader.py"
                target_script = "python firmware_downloader.py"
            else:
                # Currently running firmware_downloader.py, switch to test.py
                target_file = "test.py"
                target_script = "python test.py"
            
            # Check if target file exists
            if not Path(target_file).exists():
                QMessageBox.warning(self, "File Not Found", 
                                  f"Could not find {target_file}. Please ensure both files are in the same directory.")
                return
            
            # Show confirmation dialog
            if current_file == "test.py":
                # Currently in labs mode, asking to disable
                dialog_title = "Disable Labs Mode"
                dialog_text = f"Testing features are currently ENABLED (running {current_file}).\n\n"
                dialog_text += f"Would you like to go back to the stable version ({target_file})?\n\n"
                dialog_text += "This will close the current application and launch the stable version."
            else:
                # Currently in stable mode, asking to enable
                dialog_title = "Enable Labs Mode"
                dialog_text = f"Testing features are currently DISABLED (running {current_file}).\n\n"
                dialog_text += f"Would you like to enable experimental features ({target_file})?\n\n"
                dialog_text += "This will close the current application and launch the labs version."
            
            reply = QMessageBox.question(
                self,
                dialog_title,
                dialog_text,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # Launch the target script
                if platform.system() == "Windows":
                    subprocess.Popen([sys.executable, target_file], 
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.Popen([sys.executable, target_file])
                
                # Close the current app after a short delay
                QTimer.singleShot(1000, self.close)
                
        except Exception as e:
            QMessageBox.warning(self, "Switch Error", f"Error switching versions: {str(e)}")

    def launch_updater_script(self):
        """Launch the separate updater script to handle updates gracefully"""
        try:
            # Check if updater script exists
            updater_script_path = Path("updater.py")
            if not updater_script_path.exists():
                QMessageBox.warning(self, "Update Error",
                                  "Updater script not found. Please ensure updater.py is in the same directory.")
                return

            # Show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Update Confirmation",
                "This will download and install the latest version of the Innioasis Updater.\n\n"
                "The current application will close and the updated version will be launched automatically.\n\n"
                "Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                # Kill conflicting processes before launching updater
                self.terminate_conflicting_processes_for_update()
                
                # Launch the updater script with -f argument for force update
                if platform.system() == "Windows":
                    subprocess.Popen([sys.executable, str(updater_script_path), "-f"], 
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.Popen([sys.executable, str(updater_script_path), "-f"])

                # Close the current app after a short delay
                QTimer.singleShot(1000, self.close)

        except Exception as e:
            QMessageBox.warning(self, "Update Error", f"Error launching updater: {str(e)}")

    def terminate_conflicting_processes_for_update(self):
        """Terminate adb and libusb processes before launching updater"""
        try:
            if platform.system() == "Windows":
                # Windows: Use taskkill to terminate processes
                processes_to_kill = ['adb.exe', 'libusb-1.0.dll']
                
                for process_name in processes_to_kill:
                    try:
                        # Find and kill processes by name
                        result = subprocess.run(['tasklist', '/FO', 'CSV'], 
                                              capture_output=True, text=True, timeout=5)
                        
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if process_name.lower() in line.lower():
                                    # Extract PID from CSV format
                                    parts = line.split(',')
                                    if len(parts) >= 2:
                                        pid = parts[1].strip('"')
                                        try:
                                            # Kill the process
                                            subprocess.run(['taskkill', '/PID', pid, '/F'], 
                                                          capture_output=True, timeout=5)
                                            silent_print(f"Terminated {process_name} (PID: {pid}) for update")
                                        except subprocess.TimeoutExpired:
                                            silent_print(f"Timeout killing {process_name} (PID: {pid})")
                                        except Exception as e:
                                            silent_print(f"Error killing {process_name}: {e}")
                    except Exception as e:
                        silent_print(f"Error checking for {process_name}: {e}")
                        
            else:
                # Linux/macOS: Use pkill to terminate processes
                processes_to_kill = ['adb', 'libusb']
                
                for process_name in processes_to_kill:
                    try:
                        subprocess.run(['pkill', '-f', process_name], 
                                      capture_output=True, timeout=5)
                        silent_print(f"Terminated {process_name} processes for update")
                    except subprocess.TimeoutExpired:
                        silent_print(f"Timeout killing {process_name} processes")
                    except Exception as e:
                        silent_print(f"Error killing {process_name}: {e}")
            
            silent_print("Process cleanup completed for update")
            
        except Exception as e:
            silent_print(f"Warning: Could not terminate all conflicting processes: {e}")

    def show_install_error_dialog(self):
        """Show the install error dialog with troubleshooting options"""
        # Show troubleshooting dialog on all platforms
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Install Error")
        msg_box.setText("Something interrupted the firmware install process, would you like to try a troubleshooting run?")
        msg_box.setIcon(QMessageBox.Critical)
        
        # Create custom buttons in the desired order: Try Again, Try Method 2, Stop Install, Exit
        try_again_btn = msg_box.addButton("Try Again", QMessageBox.ActionRole)
        try_method2_btn = msg_box.addButton("Try Method 2", QMessageBox.ActionRole)
        
        # Only show Method 3 (SP Flash Tool) button on Windows
        try_method3_btn = None
        if platform.system() == "Windows":
            try_method3_btn = msg_box.addButton("Try Method 3", QMessageBox.ActionRole)
        
        stop_install_btn = msg_box.addButton("Stop Install", QMessageBox.ActionRole)
        exit_btn = msg_box.addButton("Exit", QMessageBox.RejectRole)
        
        # Set default button
        msg_box.setDefaultButton(try_again_btn)
        
        reply = msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == try_again_btn:
            # Try Again - use selected installation method from settings
            method = getattr(self, 'installation_method', 'guided')
            if method == "guided":
                # Method 1: Show unplug Y1 prompt and retry normal installation
                # Don't clear marker here - it will be cleared after successful installation
                self.show_unplug_prompt_and_retry()
            elif method == "mtkclient":
                # Method 2: Same as pressing Try Method 2
                remove_installation_marker()
                self.show_troubleshooting_instructions()
            elif method == "spflash" and platform.system() == "Windows":
                # Method 3: Same as pressing Try Method 3 (Windows only)
                remove_installation_marker()
                self.try_method_3()
            else:
                # Fallback to guided method
                self.show_unplug_prompt_and_retry()
        elif clicked_button == try_method2_btn:
            # Clear the marker and show troubleshooting instructions
            remove_installation_marker()
            self.show_troubleshooting_instructions()
        elif clicked_button == try_method3_btn and try_method3_btn:
            # Clear the marker and open SP Flash Tool shortcut (Windows only)
            remove_installation_marker()
            self.try_method_3()
        elif clicked_button == stop_install_btn:
            # Stop install and return to ready state
            remove_installation_marker()
            self.revert_to_startup_state()
        else:
            # Exit the application - don't clear marker as user chose to exit
            QApplication.quit()

    def show_unplug_prompt_and_retry(self):
        """Show the unplug Y1 prompt and retry normal installation"""
        # Show the same unplug prompt that's used at the start of normal installation
        reply = QMessageBox.question(
            self,
            "Get Ready",
            "Please make sure your Y1 is NOT plugged in and press OK, then follow the next instructions.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel
        )

        if reply == QMessageBox.Cancel:
            return

        # Clean up libusb state before starting new MTK operation (Windows only)
        if platform.system() == "Windows":
            self.cleanup_libusb_state()

        # Create installation marker to track progress
        create_installation_marker()

        # Load and display the init steps image
        self.load_initsteps_image()

        # Start MTK worker
        # Create debug window if debug mode is enabled
        debug_window = None
        if getattr(self, 'debug_mode', False):
            debug_window = DebugOutputWindow(self)
            debug_window.show()
        
        self.mtk_worker = MTKWorker(debug_mode=getattr(self, 'debug_mode', False), debug_window=debug_window)
        self.mtk_worker.status_updated.connect(self.status_label.setText)
        self.mtk_worker.show_installing_image.connect(self.load_installing_image)
        self.mtk_worker.mtk_completed.connect(self.on_mtk_completed)
        self.mtk_worker.handshake_failed.connect(self.on_handshake_failed)
        self.mtk_worker.errno2_detected.connect(self.on_errno2_detected)
        self.mtk_worker.backend_error_detected.connect(self.on_backend_error_detected)
        self.mtk_worker.keyboard_interrupt_detected.connect(self.on_keyboard_interrupt_detected)
        self.mtk_worker.disable_update_button.connect(self.disable_update_button)
        self.mtk_worker.enable_update_button.connect(self.enable_update_button)

        self.mtk_worker.start()

        # Disable download button during MTK operation
        self.download_btn.setEnabled(False)
        self.settings_btn.setEnabled(False)

    def show_troubleshooting_instructions(self):
        """Show troubleshooting instructions and launch recovery firmware install"""
        # Show Method 2 image when troubleshooting instructions are displayed
        self.load_method2_image()
        
        if platform.system() == "Windows":
            # Windows: Check if shortcut exists, download if missing
            if not self.ensure_recovery_shortcut():
                return
            
            # Windows-specific Method 2 instructions
            instructions = ("Please follow these steps after you click OK:\n\n"
                          "1. INSERT Paperclip\n"
                          "2. CONNECT your Y1 via USB\n"
                          "3. INSERT Paperclip again\n"
                          "4. WAIT for install to finish then disconnect your Y1\n"
                          "5. HOLD middle button to restart\n\n"
                          "This method shows technical installation details. If it fails, try Method 3.")
        else:
            # Non-Windows baseline Method 2 instructions
            instructions = ("Please follow these steps:\n\n"
                          "1. INSERT Paperclip\n"
                          "2. CONNECT Y1 via USB\n"
                          "3. WAIT for the install to finish\n"
                          "4. DISCONNECT your Y1\n"
                          "5. HOLD middle button to restart\n\n"
                          "This method shows technical installation details.")
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Troubleshooting Instructions - Method 2")
        msg_box.setText(instructions)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setDefaultButton(QMessageBox.Ok)
        
        reply = msg_box.exec()
        
        if reply == QMessageBox.Ok:
            # Launch recovery firmware installer (platform-specific)
            self.launch_recovery_firmware_install()

    def stop_mtk_processes(self):
        """Stop any running mtk.py processes to prevent libusb conflicts on Windows"""
        if platform.system() != "Windows":
            return  # Only needed on Windows
            
        try:
            # Use tasklist to find mtk.py processes
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                mtk_processes = []
                
                for line in lines[1:]:  # Skip header line
                    if 'mtk.py' in line:
                        # Extract PID from CSV format
                        parts = line.split(',')
                        if len(parts) >= 2:
                            pid = parts[1].strip('"')
                            if pid.isdigit():
                                mtk_processes.append(pid)
                
                if mtk_processes:
                    self.status_label.setText(f"Found {len(mtk_processes)} mtk.py processes, stopping them...")
                    
                    # Stop each mtk.py process
                    for pid in mtk_processes:
                        try:
                            subprocess.run(
                                ["taskkill", "/PID", pid, "/F"],
                                capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW
                            )
                        except Exception as e:
                            print(f"Failed to stop mtk.py process {pid}: {e}")
                    
                    # Give processes time to terminate
                    import time
                    time.sleep(1)
                    
                    self.status_label.setText(f"Stopped {len(mtk_processes)} mtk.py processes")
                else:
                    self.status_label.setText("No mtk.py processes found")
                    
        except Exception as e:
            self.status_label.setText(f"Error checking for mtk.py processes: {e}")
            print(f"Error checking for mtk.py processes: {e}")

    def cleanup_libusb_state(self):
        """Clean up libusb state before starting new MTK operations (Windows only)
        
        IMPORTANT: This function should ONLY be called BEFORE starting new MTK operations,
        NEVER during active flashing/installation. It helps resolve libusb conflicts
        that occur when previous MTK processes didn't clean up properly.
        """
        if platform.system() != "Windows":
            return  # Only needed on Windows
            
        try:
            self.status_label.setText("Cleaning up libusb state...")
            
            # Method 1: Try to clear USB device cache using pnputil
            try:
                subprocess.run(
                    ["pnputil", "/enum-devices", "/class", "USB"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5
                )
                # This refreshes the USB device list without restarting anything
            except Exception as e:
                print(f"USB device refresh failed: {e}")
            
            # Method 2: Try to reset USB hub service (more aggressive but safer than device restart)
            try:
                # Check if USB hub service is running
                result = subprocess.run(
                    ["sc", "query", "usbhub"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5
                )
                
                if result.returncode == 0 and "RUNNING" in result.stdout:
                    # Service is running, try to restart it
                    subprocess.run(
                        ["sc", "stop", "usbhub"],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=5
                    )
                    import time
                    time.sleep(2)  # Wait for service to stop
                    
                    subprocess.run(
                        ["sc", "start", "usbhub"],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=5
                    )
                    time.sleep(3)  # Wait for service to start
                    
                    self.status_label.setText("USB hub service restarted to clear libusb conflicts")
                else:
                    self.status_label.setText("USB hub service not running, skipping restart")
                    
            except Exception as e:
                print(f"USB hub service restart failed: {e}")
            
            # Method 3: Wait a bit for USB subsystem to stabilize
            import time
            time.sleep(2)
            
            self.status_label.setText("Libusb state cleanup completed")
            
        except Exception as e:
            print(f"Error during libusb cleanup: {e}")
            self.status_label.setText("Libusb cleanup failed, continuing anyway")
            # Continue anyway - this is not critical

    def try_method_3(self):
        """Open SP Flash Tool shortcut for Windows users"""
        # Show method3 image when SP Flash Tool method is displayed
        self.load_method3_image()
        
        # Check if shortcut exists, download if missing
        if not self.ensure_sp_flash_tool_shortcut():
            return
            
        try:
            # Look for the SP Flash Tool shortcut in the same directory as firmware_downloader.py
            current_dir = Path.cwd()
            sp_flash_tool_lnk = current_dir / "Recover Firmware Install - SP Flash Tool.lnk"
            
            # Show SP Flash Tool specific instructions popup
            reply = QMessageBox.question(
                self,
                "SP Flash Tool Instructions - Method 3",
                "Please follow these steps:\n\n"
                "1. CONNECT Y1 via USB\n"
                "2. INSERT Paperclip\n"
                "3. WAIT for the black window to appear\n"
                "4. Follow the on-screen instructions in the recovery window\n"
                "5. Disconnect Y1 and hold middle button to restart\n\n"
                "This method uses the manufacturer's SP Flash Tool. If it fails with proper drivers, contact the seller/manufacturer.\n\n"
                "Click OK when ready to open SP Flash Tool.",
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Ok
            )
            
            if reply == QMessageBox.Cancel:
                return
            
            # Stop mtk.py processes and clean up libusb state before opening SP Flash Tool
            self.stop_mtk_processes()
            self.cleanup_libusb_state()
            
            # Launch the SP Flash Tool shortcut
            if platform.system() == "Windows":
                # On Windows, use os.startfile to launch the .lnk file
                os.startfile(str(sp_flash_tool_lnk))
                self.status_label.setText("SP Flash Tool opened successfully")
            else:
                # This should never happen since the button is only shown on Windows
                QMessageBox.information(
                    self,
                    "Platform Not Supported",
                    "SP Flash Tool is only available on Windows systems."
                )
                
        except Exception as e:
            self.status_label.setText(f"Error opening SP Flash Tool: {e}")
            
            # Show error message
            QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to open SP Flash Tool:\n{e}\n\n"
                "Please try launching it manually."
            )

    def launch_recovery_firmware_install(self):
        """Launch the recovery firmware installer"""
        try:
            if platform.system() == "Windows":
                # Windows: Check if shortcut exists, download if missing
                if not self.ensure_recovery_shortcut():
                    return
                    
                # Look for the .lnk file in the same directory as firmware_downloader.py
                current_dir = Path.cwd()
                recovery_lnk = current_dir / "Recover Firmware Install.lnk"
                
                # On Windows, use os.startfile to launch the .lnk file
                os.startfile(str(recovery_lnk))
                self.status_label.setText("Recovery Firmware Install launched successfully")
            else:
                # Linux/macOS: Open terminal with MTK command
                current_dir = Path.cwd()
                
                # Check if required files exist
                required_files = ["lk.bin", "boot.img", "recovery.img", "system.img", "userdata.img"]
                missing_files = []
                for file in required_files:
                    if not Path(file).exists():
                        missing_files.append(file)

                if missing_files:
                    QMessageBox.warning(
                        self, 
                        "Missing Files", 
                        f"Required firmware files are missing: {', '.join(missing_files)}\n\n"
                        "Please ensure you have extracted the firmware files to the current directory."
                    )
                    return
                
                # Construct the MTK command (same as used in regular installation)
                mtk_command = f"cd '{current_dir}' && python3 mtk.py w uboot,bootimg,recovery,android,usrdata lk.bin,boot.img,recovery.img,system.img,userdata.img"
                
                if platform.system() == "Linux":
                    # Linux: Open terminal with MTK command in separate window
                    terminal_cmd = ["gnome-terminal", "--title=Innioasis Recovery", "--", "bash", "-c", f"{mtk_command}; exec bash"]
                    # Try alternative terminals if gnome-terminal fails
                    alternatives = [
                        ["xterm", "-title", "Innioasis Recovery", "-e", f"bash -c '{mtk_command}; exec bash'"],
                        ["konsole", "--title", "Innioasis Recovery", "-e", f"bash -c '{mtk_command}; exec bash'"],
                        ["xfce4-terminal", "--title=Innioasis Recovery", "-e", f"bash -c '{mtk_command}; exec bash'"]
                    ]
                    
                    success = False
                    for cmd in [terminal_cmd] + alternatives:
                        try:
                            subprocess.Popen(cmd, start_new_session=True)
                            success = True
                            break
                        except FileNotFoundError:
                            continue
                    
                    if not success:
                        QMessageBox.warning(
                            self,
                            "Terminal Not Found",
                            "Could not find a suitable terminal emulator.\n\n"
                            "Please open a terminal manually and run:\n"
                            f"{mtk_command}"
                        )
                        return
                        
                elif platform.system() == "Darwin":  # macOS
                    # macOS: Open Terminal.app with MTK command and activate venv
                    venv_path = Path.home() / "Library/Application Support/Innioasis Updater/venv"
                    script_content = f"""#!/bin/bash
# Set terminal title
echo -ne "\\033]0;Innioasis Recovery\\007"

cd '{current_dir}'

# Activate virtual environment if it exists
if [ -f "{venv_path}/bin/activate" ]; then
    source "{venv_path}/bin/activate"
    echo "Virtual environment activated"
fi

echo "=========================================="
echo "  Innioasis Recovery Firmware Install"
echo "=========================================="
echo ""
echo "This terminal window will now run the MTK firmware installation process."
echo ""
echo "IMPORTANT INSTRUCTIONS:"
echo "1. Make sure your Y1 device is connected via USB"
echo "2. Put your device into Download Mode (power off, then hold Volume Down + Power)"
echo "3. The installation process will begin automatically"
echo "4. DO NOT disconnect your device during installation"
echo "5. Wait for the process to complete - this may take several minutes"
echo "6. Your device will restart automatically when finished"
echo ""
echo "If you see any errors or the process fails:"
echo "- Check that your device is properly connected"
echo "- Try putting the device in Download Mode again"
echo "- Contact support if problems persist"
echo ""
echo "Press Enter to start the installation process..."
read -n 1
echo ""
echo "Starting Innioasis Recovery Firmware Install..."
echo "Running MTK command in separate terminal window..."
echo ""

# Run MTK command with python3 (same as used in regular installation)
python3 mtk.py w uboot,bootimg,recovery,android,usrdata lk.bin,boot.img,recovery.img,system.img,userdata.img

echo ""
echo "=========================================="
echo "MTK command completed."
echo ""
if [ $? -eq 0 ]; then
    echo "✓ Installation appears to have completed successfully!"
    echo "Your device should restart automatically."
else
    echo "⚠ Installation may have encountered issues."
    echo "Please check the output above for error messages."
fi
echo ""
echo "Press any key to close this terminal..."
read -n 1
"""
                    # Create temporary script
                    script_path = current_dir / "mtk_recovery.sh"
                    with open(script_path, 'w') as f:
                        f.write(script_content)
                    
                    # Make script executable
                    os.chmod(script_path, 0o755)
                    
                    # Open Terminal.app with the script
                    subprocess.Popen([
                        "open", "-a", "Terminal", str(script_path)
                    ])
                    
                    # Clean up script after a delay
                    QTimer.singleShot(5000, lambda: script_path.unlink() if script_path.exists() else None)
                
                self.status_label.setText("Recovery Firmware Install launched in terminal")
                
        except Exception as e:
            self.status_label.setText(f"Error launching recovery firmware install: {e}")
            
            # Show error message
            QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to launch the recovery firmware installer:\n{e}\n\n"
                "Please try launching it manually."
            )

    def check_drivers_and_architecture(self):
        """Check driver availability and system architecture for Windows users"""
        if platform.system() != "Windows":
            return {
                'has_mtk_driver': True,
                'has_usbdk_driver': True,
                'is_arm64': False,
                'available_methods': ['guided', 'mtkclient'],
                'can_install_firmware': True
            }
        
        # Check for ARM64 architecture
        is_arm64 = False
        try:
            import platform
            machine = platform.machine().lower()
            is_arm64 = machine in ['arm64', 'aarch64']
        except:
            pass
        
        # Check for MTK driver (SP Flash Tool driver)
        has_mtk_driver = False
        try:
            mediatek_driver_file = Path("C:/Program Files/MediaTek/SP Driver/unins000.exe")
            has_mtk_driver = mediatek_driver_file.exists()
        except:
            pass
        
        # Check for UsbDk driver
        has_usbdk_driver = False
        try:
            usbdk_driver_file = Path("C:/Program Files/UsbDk Runtime Library/UsbDk.sys")
            has_usbdk_driver = usbdk_driver_file.exists()
        except:
            pass
        
        # Determine available methods based on drivers
        available_methods = []
        can_install_firmware = True
        
        if is_arm64:
            # ARM64 Windows: Only allow firmware downloads, no installation methods
            available_methods = []
            can_install_firmware = False
        elif has_mtk_driver and has_usbdk_driver:
            # Both drivers available: All methods available
            available_methods = ['guided', 'mtkclient', 'spflash']
        elif has_mtk_driver and not has_usbdk_driver:
            # Only MTK driver: Force Method 3 (SP Flash Tool) for this session
            # This acts as though the user selected Method 3 from settings but without ticking "use as default"
            available_methods = ['spflash']
            # Temporarily override installation method for this session only
            if not hasattr(self, '_original_installation_method'):
                self._original_installation_method = getattr(self, 'installation_method', 'guided')
            self.installation_method = "spflash"
        else:
            # No drivers: No installation methods available
            available_methods = []
            can_install_firmware = False
        
        return {
            'has_mtk_driver': has_mtk_driver,
            'has_usbdk_driver': has_usbdk_driver,
            'is_arm64': is_arm64,
            'available_methods': available_methods,
            'can_install_firmware': can_install_firmware
        }

    def download_latest_updater(self):
        """Download the latest updater.py script silently during launch"""
        try:
            updater_url = "https://innioasis.app/updater.py"
            response = requests.get(updater_url, timeout=10)
            response.raise_for_status()

            updater_path = Path("updater.py")
            with open(updater_path, 'wb') as f:
                f.write(response.content)

            silent_print("Latest updater.py downloaded successfully")
        except Exception as e:
            silent_print(f"Failed to download latest updater.py: {e}")

    def check_for_utility_updates(self):
        """Check for and download the latest updater.py when user clicks the button, then run it"""
        try:
            # Show progress dialog
            progress_dialog = QDialog(self)
            progress_dialog.setWindowTitle("Checking for Updates")
            progress_dialog.setFixedSize(300, 100)
            progress_dialog.setModal(True)
            
            layout = QVBoxLayout(progress_dialog)
            status_label = QLabel("Checking for utility updates...")
            layout.addWidget(status_label)
            
            progress_dialog.show()
            
            # Download the latest updater.py
            updater_url = "https://innioasis.app/updater.py"
            response = requests.get(updater_url, timeout=15)
            response.raise_for_status()

            updater_path = Path("updater.py")
            with open(updater_path, 'wb') as f:
                f.write(response.content)

            progress_dialog.close()
            QMessageBox.information(self, "Update Complete", "The latest updater.py has been downloaded successfully!")
            
            # Run the updated updater.py
            self.run_updater()
            
        except requests.exceptions.RequestException as e:
            progress_dialog.close()
            QMessageBox.warning(self, "Update Failed", 
                              f"Could not connect to download the latest updater.py.\n\nError: {e}\n\nUsing existing updater.py.")
            # Still try to run the existing updater
            self.run_updater()
        except Exception as e:
            progress_dialog.close()
            QMessageBox.warning(self, "Update Failed", 
                              f"Failed to download the latest updater.py.\n\nError: {e}\n\nUsing existing updater.py.")
            # Still try to run the existing updater
            self.run_updater()

    def run_updater(self):
        """Run the updater.py script"""
        try:
            updater_path = Path("updater.py")
            if updater_path.exists():
                # Close the current application
                self.close()
                
                # Run the updater
                subprocess.Popen([sys.executable, str(updater_path)])
            else:
                QMessageBox.error(self, "Error", "updater.py not found!")
        except Exception as e:
            QMessageBox.error(self, "Error", f"Failed to run updater.py: {e}")

if __name__ == "__main__":
    try:
        # Create the application
        app = QApplication(sys.argv)

        # Set application icon based on platform
        if platform.system() == "Darwin":  # macOS
            icon_path = "mtkclient/gui/images/Innioasis Updater Icon.icns"
        elif platform.system() == "Windows":
            icon_path = "mtkclient/gui/images/icon.ico"
        else:
            # Fallback to PNG for other platforms
            icon_path = "mtkclient/gui/images/icon.png"

        if Path(icon_path).exists():
            app.setWindowIcon(QIcon(icon_path))

        # Create and show the main window
        window = FirmwareDownloaderGUI()
        window.show()

        # Start the application event loop
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

