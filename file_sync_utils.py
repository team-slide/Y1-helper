#!/usr/bin/env python3
"""
Robust File Sync Utilities for Y1 Helper
Provides intelligent file detection and synchronization across platforms
"""

import os
import re
import json
import hashlib
import platform
import requests
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
import mimetypes
# Conditional import for magic (not available on Windows by default)
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False

class FileSyncConfig:
    """Configuration manager for file synchronization"""
    
    def __init__(self, config_file="file_sync_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self.platform = platform.system().lower()
        
    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._get_default_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Get default configuration if file not found"""
        return {
            "github": {
                "repo_owner": "team-slide",
                "repo_name": "Y1-helper",
                "api_base": "https://api.github.com",
                "raw_base": "https://raw.githubusercontent.com",
                "branch": "master"
            },
            "sync": {
                "sync_strategy": "smart_include",
                "smart_rules": {
                    "always_sync": ["y1_helper.py", "requirements.txt", "version.txt"],
                    "exclude_patterns": ["\\.git/.*", "\\.github/.*", "\\.log$", "\\.tmp$"]
                }
            }
        }
    
    def get_platform_config(self) -> Dict:
        """Get platform-specific configuration"""
        return self.config.get("platforms", {}).get(self.platform, {})
    
    def get_exclude_patterns(self) -> List[str]:
        """Get combined exclude patterns for current platform"""
        base_excludes = self.config.get("sync", {}).get("smart_rules", {}).get("exclude_patterns", [])
        platform_excludes = self.config.get("sync", {}).get("smart_rules", {}).get("platform_specific_excludes", {}).get(self.platform, [])
        return base_excludes + platform_excludes

class IntelligentFileDetector:
    """Intelligent file type detection and classification"""
    
    def __init__(self):
        self.text_extensions = {
            '.py', '.txt', '.ini', '.xml', '.json', '.md', '.cfg', '.conf',
            '.yml', '.yaml', '.toml', '.csv', '.tsv', '.sh', '.bat', '.ps1',
            '.vbs', '.js', '.html', '.css', '.sql', '.r', '.m', '.java',
            '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.swift',
            '.kt', '.scala', '.clj', '.hs', '.ml', '.fs', '.lua', '.pl',
            '.perl', '.tcl', '.awk', '.sed', '.makefile', '.dockerfile'
        }
        
        self.binary_extensions = {
            '.exe', '.dll', '.so', '.dylib', '.bin', '.img', '.iso',
            '.apk', '.deb', '.rpm', '.pkg', '.msi', '.dmg', '.jar',
            '.war', '.ear', '.class', '.o', '.obj', '.a', '.lib'
        }
        
        self.archive_extensions = {
            '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
            '.lzma', '.lz4', '.zst', '.lzh', '.arj'
        }
        
        self.media_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico',
            '.svg', '.webp', '.mp3', '.wav', '.flac', '.mp4', '.avi',
            '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4a', '.aac'
        }
        
        # Initialize magic for file type detection
        if MAGIC_AVAILABLE and platform.system() != "Windows":
            try:
                self.magic = magic.Magic(mime=True)
            except Exception:
                self.magic = None
        else:
            self.magic = None
    
    def is_text_file(self, file_path: str, content: Optional[bytes] = None) -> bool:
        """Determine if a file is text-based"""
        # Check extension first
        ext = Path(file_path).suffix.lower()
        if ext in self.text_extensions:
            return True
        
        # Check content if available
        if content:
            try:
                # Try to decode as text
                content.decode('utf-8')
                return True
            except UnicodeDecodeError:
                pass
            
            # Use magic if available (Linux/macOS)
            if self.magic:
                mime_type = self.magic.from_buffer(content)
                return mime_type.startswith('text/')
            
            # Windows alternative: check for null bytes (binary indicator)
            if platform.system() == "Windows":
                if b'\x00' in content[:1024]:  # Check first 1KB for null bytes
                    return False
                # If no null bytes and we can decode as UTF-8, likely text
                try:
                    content.decode('utf-8')
                    return True
                except UnicodeDecodeError:
                    return False
        
        return False
    
    def is_binary_file(self, file_path: str, content: Optional[bytes] = None) -> bool:
        """Determine if a file is binary"""
        ext = Path(file_path).suffix.lower()
        if ext in self.binary_extensions:
            return True
        
        if content and self.magic:
            mime_type = self.magic.from_buffer(content)
            return not mime_type.startswith('text/')
        
        return False
    
    def should_sync_file(self, file_path: str, config: FileSyncConfig, content: Optional[bytes] = None) -> bool:
        """Determine if a file should be synchronized"""
        file_path = str(file_path)
        
        # Check always sync files
        always_sync = config.config.get("sync", {}).get("smart_rules", {}).get("always_sync", [])
        if any(file_path.endswith(pattern) for pattern in always_sync):
            return True
        
        # Check exclude patterns
        exclude_patterns = config.get_exclude_patterns()
        for pattern in exclude_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return False
        
        # Intelligent detection based on content
        if self.is_text_file(file_path, content):
            return True
        
        # Check if it's a data file that might be needed
        ext = Path(file_path).suffix.lower()
        if ext in {'.bin', '.img', '.apk', '.zip', '.tar', '.gz'}:
            return True
        
        return False

class RobustFileSync:
    """Robust file synchronization with intelligent detection"""
    
    def __init__(self, config_file="file_sync_config.json"):
        self.config = FileSyncConfig(config_file)
        self.detector = IntelligentFileDetector()
        self.github_token = self.config.config.get("github", {}).get("token")
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Y1-Helper-Sync/1.0'
        }
        if self.github_token:
            self.headers['Authorization'] = f'token {self.github_token}'
        
        self.sync_log = []
        self.stats = {
            'files_checked': 0,
            'files_updated': 0,
            'files_skipped': 0,
            'errors': 0,
            'bytes_downloaded': 0
        }
    
    def log_message(self, level: str, message: str):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.sync_log.append(log_entry)
        print(log_entry)
    
    def get_github_file_info(self, file_path: str) -> Optional[Dict]:
        """Get file information from GitHub API"""
        try:
            repo_owner = self.config.config["github"]["repo_owner"]
            repo_name = self.config.config["github"]["repo_name"]
            api_base = self.config.config["github"]["api_base"]
            branch = self.config.config["github"]["branch"]
            
            url = f"{api_base}/repos/{repo_owner}/{repo_name}/contents/{file_path}"
            params = {'ref': branch}
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            self.log_message("ERROR", f"Failed to get file info for {file_path}: {e}")
            return None
    
    def get_github_file_content(self, file_path: str) -> Optional[bytes]:
        """Download file content from GitHub"""
        try:
            raw_base = self.config.config["github"]["raw_base"]
            repo_owner = self.config.config["github"]["repo_owner"]
            repo_name = self.config.config["github"]["repo_name"]
            branch = self.config.config["github"]["branch"]
            
            url = f"{raw_base}/{repo_owner}/{repo_name}/{branch}/{file_path}"
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            return response.content
        except Exception as e:
            self.log_message("ERROR", f"Failed to download {file_path}: {e}")
            return None
    
    def should_update_file(self, local_path: str, remote_info: Dict) -> Tuple[bool, str]:
        """Determine if a file should be updated"""
        try:
            if not os.path.exists(local_path):
                return True, "File does not exist locally"
            
            # Check file size first (most reliable)
            local_size = os.path.getsize(local_path)
            if local_size != remote_info['size']:
                return True, f"File size mismatch (remote: {remote_info['size']}, local: {local_size})"
            
            # For text files, compare content with normalized line endings
            if self.detector.is_text_file(local_path):
                try:
                    # Download remote content for comparison
                    remote_content = self.get_github_file_content(remote_info['path'])
                    if remote_content is None:
                        self.log_message("WARNING", f"Could not download remote content for comparison")
                        return False, "Could not verify remote content, assuming up to date"
                    
                    # Read local content
                    with open(local_path, 'rb') as f:
                        local_content = f.read()
                    
                    # Normalize line endings for comparison
                    local_normalized = self.normalize_line_endings(local_content)
                    remote_normalized = self.normalize_line_endings(remote_content)
                    
                    if local_normalized != remote_normalized:
                        return True, f"Content differs after line ending normalization"
                    
                    return False, "Content matches after line ending normalization"
                    
                except Exception as e:
                    self.log_message("WARNING", f"Could not compare content: {e}")
            
            # For binary files, use size comparison only
            else:
                # If sizes match, assume up to date for binary files
                return False, "Binary file sizes match, assuming up to date"
            
            # Fallback - should never reach here
            return False, "File is up to date"
            
        except Exception as e:
            self.log_message("ERROR", f"Error checking if file should update {local_path}: {e}")
            # On error, be conservative - don't update unless we're sure
            return False, f"Error during comparison, assuming up to date: {e}"
    
    def normalize_line_endings(self, content: bytes) -> bytes:
        """Normalize line endings to Unix style (LF) for comparison"""
        # Convert Windows line endings (CRLF) to Unix (LF)
        content_str = content.decode('utf-8', errors='ignore')
        normalized = content_str.replace('\r\n', '\n')
        return normalized.encode('utf-8')
    
    def download_and_verify_file(self, file_path: str, local_path: str, remote_info: Dict) -> bool:
        """Download file with verification"""
        try:
            # Download to temporary file first
            temp_path = f"{local_path}.tmp"
            content = self.get_github_file_content(file_path)
            
            if content is None:
                return False
            
            # Verify content matches expected size
            if len(content) != remote_info['size']:
                self.log_message("ERROR", f"Downloaded content size mismatch for {file_path}")
                return False
            
            # Check if we should sync this file type
            if not self.detector.should_sync_file(file_path, self.config, content):
                self.log_message("INFO", f"Skipping {file_path} - not a syncable file type")
                return False
            
            # Create backup if file exists
            if os.path.exists(local_path) and self.config.config.get("sync", {}).get("backup_enabled", True):
                backup_path = f"{local_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(local_path, backup_path)
                self.log_message("INFO", f"Created backup: {backup_path}")
            
            # Write to temporary file
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            with open(temp_path, 'wb') as f:
                f.write(content)
            
            # Verify the temporary file
            if os.path.getsize(temp_path) != len(content):
                self.log_message("ERROR", f"Temporary file size mismatch for {file_path}")
                os.remove(temp_path)
                return False
            
            # Replace original file
            if os.path.exists(local_path):
                os.remove(local_path)
            os.rename(temp_path, local_path)
            
            # Update stats
            self.stats['files_updated'] += 1
            self.stats['bytes_downloaded'] += len(content)
            
            self.log_message("INFO", f"Successfully updated {file_path}")
            return True
            
        except Exception as e:
            self.log_message("ERROR", f"Failed to download and verify {file_path}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
    
    def scan_and_sync_files(self, target_dir: str = ".") -> Dict:
        """Scan repository and sync files intelligently"""
        self.log_message("INFO", "Starting intelligent file synchronization...")
        
        try:
            # Get repository contents
            repo_owner = self.config.config["github"]["repo_owner"]
            repo_name = self.config.config["github"]["repo_name"]
            api_base = self.config.config["github"]["api_base"]
            branch = self.config.config["github"]["branch"]
            
            url = f"{api_base}/repos/{repo_owner}/{repo_name}/contents"
            params = {'ref': branch}
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            files = response.json()
            self.log_message("INFO", f"Found {len(files)} items in repository")
            
            # Process files
            for item in files:
                try:
                    if item['type'] == 'file':
                        self.stats['files_checked'] += 1
                        file_path = item['path']
                        
                        # Check if file should be synced
                        if not self.detector.should_sync_file(file_path, self.config):
                            self.stats['files_skipped'] += 1
                            continue
                        
                        local_path = os.path.join(target_dir, file_path)
                        should_update, reason = self.should_update_file(local_path, item)
                        
                        if should_update:
                            self.log_message("INFO", f"Updating {file_path}: {reason}")
                            if not self.download_and_verify_file(file_path, local_path, item):
                                self.stats['errors'] += 1
                        else:
                            self.stats['files_skipped'] += 1
                            self.log_message("DEBUG", f"Skipping {file_path}: {reason}")
                            
                except Exception as e:
                    self.log_message("ERROR", f"Error processing {item.get('path', 'unknown')}: {e}")
                    self.stats['errors'] += 1
                    continue
                
            # Handle directories separately
            for item in files:
                if item['type'] == 'dir':
                    try:
                        # Recursively scan subdirectories
                        sub_result = self.scan_and_sync_files(os.path.join(target_dir, item['path']))
                        # Merge stats
                        for key in self.stats:
                            self.stats[key] += sub_result.get(key, 0)
                    except Exception as e:
                        self.log_message("ERROR", f"Error processing directory {item.get('path', 'unknown')}: {e}")
                        self.stats['errors'] += 1
                        continue
            
            return self.stats
            
        except Exception as e:
            self.log_message("ERROR", f"Failed to scan repository: {e}")
            self.stats['errors'] += 1
            return self.stats
    
    def get_sync_summary(self) -> str:
        """Get a summary of the sync operation"""
        return (f"Sync completed: {self.stats['files_updated']} updated, "
                f"{self.stats['files_skipped']} skipped, {self.stats['errors']} errors, "
                f"{self.stats['bytes_downloaded'] / 1024 / 1024:.1f} MB downloaded")

def main():
    """Main function for standalone testing"""
    syncer = RobustFileSync()
    stats = syncer.scan_and_sync_files()
    print(syncer.get_sync_summary())

if __name__ == "__main__":
    main() 