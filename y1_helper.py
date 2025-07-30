import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Menu, simpledialog
import subprocess
import threading
import time
import os
import struct
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import numpy as np
import platform
import ctypes
from ctypes import wintypes
import tempfile
import shutil
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import hashlib
import io
import requests
from tkinter.scrolledtext import ScrolledText
import inspect
import builtins
import datetime
import webbrowser
import psutil
import traceback

# Y1 Helper, created by Ryan Specter, Gemini, Claude, GPT, Grok and Cursor IDE for Project Gallagher, Innioasis Y1 Custom Firmware Project


# Add this near the top, after imports
base_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(base_dir, 'assets')

# Hardcoded backup API keys (stripped of github_pat_ prefix)
BACKUP_API_KEYS = [
    "11BUHMFQQ0S0BJlidk1hVe_j081TB15LMr84UOTp5cCSGoPMD7reL8naZAnsywrX8NZ56RY55IqPqeaqUf",
    "1BUHMFQQ0kI3jUezJIefF_c0sYzNSc98CFYiWytkpCZdLRGwDU49k87i6d1UZ6sMHMMLEYYYQmqhCxWOR",
    "11BUHMFQQ0Jd3WX8SZ7QAg_3eekBXeJC6ZmHZUTjDtGUx6KEuV9SaJdLlCTNnD58jpW2K6SZ2ANQRCnBHE",
    "11BUHMFQQ07ICpSRb0UXv4_SYOAPW11eNx9uu2FhuwWp4urbXJcS3LHmNOtEKjsu1X3YJM2UWTuDuCldBs",
    "11BUHMFQQ0Klynt0Ddzg30_1zvtZUvI6Tbw3ApczAAHhXTxeYDzoDc7ffLehm6Tzu4ACZPZG64Tt9YWKlf",
    "11BUHMFQQ07NN2czv5nxhh_a16N4Y99uDi9Znr4tnewdjL1aPjC3eK27iDoTHrubrZCNOTDHQ3mKI9QpEJ"
]

# This comment proves the patcher worked for Ryan

def check_and_update_launcher():
    """Check for new_launcher.py and update launcher.py if found"""
    try:
        new_launcher_path = os.path.join(base_dir, 'new_launcher.py')
        launcher_path = os.path.join(base_dir, 'launcher.py')
        
        if os.path.exists(new_launcher_path):
            debug_print("Found new_launcher.py, updating launcher.py")
            
            # Copy new_launcher.py to launcher.py
            shutil.copy2(new_launcher_path, launcher_path)
            debug_print("Successfully copied new_launcher.py to launcher.py")
            
            # Delete new_launcher.py
            os.remove(new_launcher_path)
            debug_print("Successfully deleted new_launcher.py")
            
            return True
        else:
            debug_print("No new_launcher.py found")
            return False
            
    except Exception as e:
        debug_print(f"Error updating launcher: {e}")
        return False

# Global debug flag - set to True when Ctrl+D is pressed
DEBUG_MODE = False

def debug_print(message):
    """Print debug messages with timestamp only if debug mode is enabled, except for flash_tool.exe output"""
    # Always show flash_tool.exe output regardless of debug mode
    if "flash_tool.exe" in message or "Flash tool" in message:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[DEBUG {timestamp}] {message}")
    elif DEBUG_MODE:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[DEBUG {timestamp}] {message}")

def toggle_debug_mode():
    """Toggle debug mode on/off"""
    global DEBUG_MODE
    DEBUG_MODE = not DEBUG_MODE
    if DEBUG_MODE:
        print("[DEBUG] Debug mode enabled - all debug output will be shown")
    else:
        print("[DEBUG] Debug mode disabled - debug output suppressed")

class Y1HelperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        debug_print("Initializing Y1HelperApp")
        
        # Base directory (for config file access)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Initialize cache system
        self.cache_dir = os.path.join(self.base_dir, ".cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_index_file = os.path.join(self.cache_dir, "index.xml")
        self.cache_manifest_file = os.path.join(self.cache_dir, "slidia_manifest.xml")
        self.cache_last_update_file = os.path.join(self.cache_dir, "last_update.txt")
        
        # Clean up old cache files to prevent over-reliance on cached data
        self.cleanup_cache_directory()
        
        # Pre-populate ROM directory with all required files from assets (except system.img)
        self.pre_populate_rom_directory()
        
        # Cache settings - reduced to prevent over-reliance on cached data
        self.cache_expiry_hours = 6  # Cache expires after 6 hours (reduced from 24)
        self.manifest_url = "https://raw.githubusercontent.com/team-slide/slidia/refs/heads/main/slidia_manifest.xml"
        
        # Initialize API rate limiting
        self.api_rate_limits = {
            'unauthenticated': {'calls': 0, 'reset_time': datetime.datetime.now() + datetime.timedelta(hours=1)},
            'authenticated': {}  # Will store per-token limits
        }
        self.max_unauthenticated_calls = 40
        self.max_authenticated_calls = 100
        self.rate_limit_exceeded = False
        
        # API call optimization and startup tracking
        self.last_api_check_time = None
        self.startup_timestamp = datetime.datetime.now()
        self.api_check_cooldown_minutes = 2  # Prevent API calls if app restarted within 2 minutes (reduced from 5)
        self.cache_refresh_interval_minutes = 15  # Cache refresh interval when app is running (reduced from 30)
        self.last_cache_refresh_time = None
        self.user_triggered_cache_refresh = False
        
        # Apps menu interaction tracking
        self.apps_menu_active = False
        self.apps_menu_last_interaction = None  # Track if user manually triggered cache refresh
        
        # Initialize cache at startup
        self.initialize_cache()
        
        # Load rate limit state from file if it exists
        self.load_rate_limit_state()
        
        # Load startup tracking from file
        self.load_startup_tracking()
        
        # Check for and apply launcher updates
        launcher_updated = check_and_update_launcher()
        if launcher_updated:
            debug_print("Launcher was updated during startup")
        
        # Refresh config.ini from config.zip
        debug_print("Refreshing config.ini...")
        self.download_and_unpack_config()
        
        # Version information
        self.version = "0.8.0"
        
        # Backup current y1_helper.py to .old directory at launch
        self.backup_current_version()
        
        # Write version.txt file
        self.write_version_file()
        
        # Clean up any existing system.img from previous sessions
        system_img_path = os.path.join(assets_dir, "system.img")
        if os.path.exists(system_img_path):
            try:
                os.remove(system_img_path)
                debug_print("Cleaned up existing system.img from previous session")
            except Exception as e:
                debug_print(f"Failed to clean up system.img: {e}")
        
        # At launch: copy new.xml to assets/install_rom.xml if it exists, then delete new.xml
        new_xml_path = os.path.join(self.base_dir, 'new.xml')
        install_rom_path = os.path.join(assets_dir, 'install_rom.xml')
        if os.path.exists(new_xml_path):
            try:
                shutil.copy2(new_xml_path, install_rom_path)
                debug_print('Copied new.xml to assets/install_rom.xml')
                os.remove(new_xml_path)
                debug_print('Deleted new.xml from project directory')
            except Exception as e:
                debug_print(f'Failed to copy/delete new.xml: {e}')
        
        self.title(f"Y1 Helper v{self.version} - created by Ryan Specter - u/respectyarn")
        self.geometry("520x800")  # Increased height for update status visibility
        self.resizable(False, False)
        
        # Ensure window gets focus and appears in front
        self.lift()  # Bring window to front
        self.attributes('-topmost', True)  # Temporarily make topmost
        self.after(100, lambda: self.attributes('-topmost', False))  # Remove topmost after 100ms
        self.focus_force()  # Force focus to this window
        
        # Center window on screen
        self.update_idletasks()  # Update window info
        x = (self.winfo_screenwidth() // 2) - (520 // 2)
        y = (self.winfo_screenheight() // 2) - (800 // 2)
        self.geometry(f"520x800+{x}+{y}")
        
        # Detect Windows 11 theme
        self.setup_windows_11_theme()
        self.apply_theme_colors()
        
        # Device configuration
        self.device_width = 480
        self.device_height = 360
        self.framebuffer_size = self.device_width * self.device_height * 4  # RGBA8888
        
        # Display scaling (75% of original size)
        self.display_scale = 0.75
        self.display_width = int(self.device_width * self.display_scale)  # 360
        self.display_height = int(self.device_height * self.display_scale)  # 270
        
        # State variables
        self.is_capturing = True  # Always capturing
        self.capture_thread = None
        self.current_app = None
        self.control_launcher = False
        self.last_screen_image = None
        self.device_connected = False

        self.firmware_installation_in_progress = False  # Track if firmware installation is in progress
        self.firmware_manifest_url = "https://raw.githubusercontent.com/team-slide/slidia/refs/heads/main/slidia_manifest.xml"
        self.prepare_prompt_refused = False  # Track if user refused the initial prepare prompt
        self.prepare_prompt_shown = False  # Track if prepare prompt has been shown for current connection
        
        # Essential UI variables
        self.status_var = tk.StringVar(value="Ready")
        self.scroll_wheel_mode_var = tk.BooleanVar()  # Renamed from launcher_var
        self.disable_dpad_swap_var = tk.BooleanVar()  # Variable for D-pad swap control (now "Invert Scroll Direction")
        self.y1_launcher_detected = False  # Track if com.innioasis.y1 is detected
        self.rgb_profile_var = tk.StringVar(value="BGRA8888")
        
        # Update system variables
        self.update_check_interval = 1800000  # 30 minutes in milliseconds (increased for efficiency)
        self.last_update_check = 0
        self.update_available = False
        self.update_info = None
        self.update_button = None
        self.patches_applied = os.environ.get('Y1_HELPER_PATCHES_APPLIED', '0') == '1'
        
        # Add input pacing: minimum delay between input events (in seconds)
        self.input_pacing_interval = 0.1  # 100ms
        self.last_input_time = 0
        
        # Scroll cursor variables
        self.scroll_cursor_active = False
        self.scroll_cursor_timer = None
        self.scroll_cursor_duration = 25  # Very brief cursor display (25ms) - reduced for better responsiveness
        
        # Performance optimization variables
        self.framebuffer_refresh_interval = 1.0  # Refresh every 1 second for better responsiveness
        self.last_framebuffer_refresh = 0
        self.unified_check_interval = 5  # Check device and refresh apps every 5 seconds (more frequent)
        self.last_unified_check = 0
        self.app_detection_interval = 10  # Check app every 10 seconds (increased from 5)
        self.last_app_detection = 0
        self.force_refresh_requested = False  # Flag for manual refresh requests
        
        # Activity detection variables
        self.last_user_activity = time.time()
        self.inactivity_threshold = 10.0  # 10 seconds of inactivity
        self.slow_refresh_interval = 20.0  # 20 seconds during inactivity
        self.last_app_change = time.time()
        self.current_app_package = None
        
        # Device state tracking
        self.device_stay_awake_set = False
        self.last_blank_screen_detection = 0
        self.blank_screen_threshold = 0.01  # 10ms of blank screen before showing placeholder
        
        # Enhanced device connection tracking
        self.device_connection_lock = threading.Lock()  # Thread-safe device state management
        self.last_device_check_time = 0
        self.device_check_failures = 0
        self.max_device_check_failures = 2  # Reduced failures before marking as disconnected (more responsive)
        self.device_validation_interval = 3.0  # Validate device responsiveness every 3 seconds (more frequent)
        self.last_device_validation = 0
        self.consecutive_framebuffer_failures = 0  # Track consecutive framebuffer pull failures
        self.max_framebuffer_failures = 3  # Max framebuffer failures before showing ready placeholder
        self.input_command_in_progress = False  # Flag to track input commands
        
        # Input mode persistence
        self.manual_mode_override = False  # Track if user manually changed mode
        self.last_manual_mode_change = time.time()
        
        # Add a flag to the class
        self.is_flashing_firmware = False
        
        # Update system variables
        self.update_prompt_shown = False
        
        debug_print("Setting up UI components")
        # Initialize UI
        self.setup_ui()
        self.setup_menu()
        self.setup_bindings()
        
        debug_print("Checking ADB connection")
        # Check ADB connection
        self.unified_device_check()
        
        # Show placeholder if no device connected
        if not hasattr(self, 'device_connected') or not self.device_connected:
            debug_print("No device connected, showing ready placeholder")
            self.show_ready_placeholder()
        else:
            # Device is connected, enable input bindings
            self.enable_input_bindings()
        
        # Set device to stay awake while charging
        self.set_device_stay_awake()
        
        # Detect current app and set launcher control (and start periodic check) only if device is connected
        if self.device_connected:
            self.detect_current_app()
        
        # Start screen capture immediately
        self.start_screen_capture()
        
        # Initialize config download and background updates
        self.download_and_unpack_config()
        self.update_config_background()
        
        # Check for updates in background after a short delay
        self.after(5000, self.show_update_pill_if_needed)  # Check for updates after 5 seconds
        
        # Check for team-slide updates and show patch status
        self.after(3000, self.check_and_show_team_slide_update)  # Check for team-slide updates after 3 seconds
        self.after(1000, self.show_patch_status_message)  # Show patch status after 1 second
        
        # Check for updates at startup and show dialog if newer version available
        self.after(2000, self.startup_update_check)  # Check for updates after 2 seconds
        
        debug_print("Y1HelperApp initialization complete")
    
    def write_version_file(self):
        """Write version information to version.txt file"""
        try:
            version_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")
            with open(version_file_path, 'w', encoding='utf-8') as f:
                f.write(f"{self.version}\n")
            debug_print(f"Version file written: {version_file_path}")
        except Exception as e:
            debug_print(f"Failed to write version file: {e}")
    
    def backup_current_version(self):
        """Backup current y1_helper.py to .old directory with version subfolder"""
        try:
            # Create .old directory if it doesn't exist
            old_dir = os.path.join(self.base_dir, ".old")
            os.makedirs(old_dir, exist_ok=True)
            
            # Create version subfolder
            version_folder = f"v{self.version}"
            version_dir = os.path.join(old_dir, version_folder)
            os.makedirs(version_dir, exist_ok=True)
            
            # Source file (current y1_helper.py)
            source_file = os.path.join(self.base_dir, "y1_helper.py")
            
            # Destination file
            dest_file = os.path.join(version_dir, "y1_helper.py")
            
            # Check if destination file exists and compare modification times
            if os.path.exists(dest_file):
                source_mtime = os.path.getmtime(source_file)
                dest_mtime = os.path.getmtime(dest_file)
                
                # Only overwrite if source is newer
                if source_mtime > dest_mtime:
                    shutil.copy2(source_file, dest_file)
                    debug_print(f"Updated backup of y1_helper.py to {version_dir} (source was newer)")
                else:
                    debug_print(f"Backup already exists and is up to date: {version_dir}")
            else:
                # File doesn't exist, create backup
                shutil.copy2(source_file, dest_file)
                debug_print(f"Created backup of y1_helper.py to {version_dir}")
                
        except Exception as e:
            debug_print(f"Failed to backup current version: {e}")
    
    def initialize_cache(self):
        """Initialize the cache system and clean up .old directory"""
        try:
            debug_print("Initializing cache system...")
            
            # Clean up .old directory (keep only y1_helper.py files)
            self.cleanup_old_directory()
            
            # Create cache directory if it doesn't exist
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Initialize cache if it doesn't exist or is expired
            if not self.is_cache_valid():
                self.update_cache()
            else:
                debug_print("Cache is valid, using existing cache")
                
        except Exception as e:
            debug_print(f"Cache initialization failed: {e}")
    
    def cleanup_old_directory(self):
        """Clean up .old directory to keep only y1_helper.py files"""
        
    def pre_populate_rom_directory(self):
        """Replace ROM directory files with originals from assets and delete system.img at app startup"""
        try:
            debug_print("Replacing ROM directory files with originals from assets at startup...")
            
            # Ensure ROM directory exists
            rom_dir = os.path.join(self.base_dir, "assets", "rom")
            assets_dir = os.path.join(self.base_dir, "assets")
            
            os.makedirs(rom_dir, exist_ok=True)
            
            # Delete system.img if it exists (must come from downloaded ROM)
            system_img_path = os.path.join(rom_dir, "system.img")
            if os.path.exists(system_img_path):
                os.remove(system_img_path)
                debug_print("Deleted existing system.img from ROM directory")
            
            # Replace files with originals from assets (only if they exist in assets)
            replaced_count = 0
            
            # List of files that should be in rom directory (based on current ideal structure)
            rom_files = [
                "boot.img", "cache.img", "DA_PL.bin", "DA_PL_CRYPTO20.bin",
                "DA_SWSEC.bin", "DA_SWSEC_CRYPTO20.bin", "EBR1", "EBR2",
                "kernel", "kernel_g368_nyx.bin", "lk.bin", "logo.bin",
                "MBR", "MT6572_Android_scatter.txt", "MTK_AllInOne_DA.bin",
                "preloader_g368_nyx.bin", "recovery.img", "secro.img", "userdata.img"
            ]
            
            for file_name in rom_files:
                src_path = os.path.join(assets_dir, file_name)
                dest_path = os.path.join(rom_dir, file_name)
                
                if os.path.exists(src_path):
                    # Always copy from assets to replace any existing file
                    try:
                        shutil.copy2(src_path, dest_path)
                        replaced_count += 1
                        debug_print(f"Replaced {file_name} with original from assets")
                    except Exception as e:
                        debug_print(f"Failed to replace {file_name}: {e}")
                else:
                    debug_print(f"File {file_name} not found in assets directory")
            
            debug_print(f"ROM directory startup cleanup completed: {replaced_count} files replaced with originals")
            
        except Exception as e:
            debug_print(f"Error during ROM directory startup cleanup: {e}")
    
    def clear_rom_directory_for_firmware(self):
        """Replace ROM directory files with originals from assets and delete system.img before firmware download"""
        try:
            rom_dir = os.path.join(self.base_dir, "assets", "rom")
            assets_dir = os.path.join(self.base_dir, "assets")
            
            # Ensure ROM directory exists
            os.makedirs(rom_dir, exist_ok=True)
            
            debug_print(f"Replacing ROM directory files with originals from assets: {rom_dir}")
            
            # Delete system.img if it exists (must come from downloaded ROM)
            system_img_path = os.path.join(rom_dir, "system.img")
            if os.path.exists(system_img_path):
                os.remove(system_img_path)
                debug_print("Deleted existing system.img from ROM directory")
            
            # Replace files with originals from assets (only if they exist in assets)
            replaced_count = 0
            
            # List of files that should be in rom directory (based on current ideal structure)
            rom_files = [
                "boot.img", "cache.img", "DA_PL.bin", "DA_PL_CRYPTO20.bin",
                "DA_SWSEC.bin", "DA_SWSEC_CRYPTO20.bin", "EBR1", "EBR2",
                "kernel", "kernel_g368_nyx.bin", "lk.bin", "logo.bin",
                "MBR", "MT6572_Android_scatter.txt", "MTK_AllInOne_DA.bin",
                "preloader_g368_nyx.bin", "recovery.img", "secro.img", "userdata.img"
            ]
            
            for file_name in rom_files:
                src_path = os.path.join(assets_dir, file_name)
                dest_path = os.path.join(rom_dir, file_name)
                
                if os.path.exists(src_path):
                    # Always copy from assets to replace any existing file
                    try:
                        shutil.copy2(src_path, dest_path)
                        replaced_count += 1
                        debug_print(f"Replaced {file_name} with original from assets")
                    except Exception as e:
                        debug_print(f"Failed to replace {file_name}: {e}")
                else:
                    debug_print(f"File {file_name} not found in assets directory")
            
            debug_print(f"ROM directory cleanup completed: {replaced_count} files replaced with originals")
                
        except Exception as e:
            debug_print(f"Error replacing ROM directory files: {e}")
    
    def _get_required_rom_files(self):
        """Get list of required ROM files based on install_rom.xml reference"""
        # This list is based on what install_rom.xml contains - the app doesn't parse the XML
        return [
            "preloader_g368_nyx.bin",
            "MBR",
            "EBR1", 
            "EBR2",
            "lk.bin",
            "boot.img",
            "recovery.img",
            "secro.img",
            "logo.bin",
            "system.img",
            "cache.img",
            "userdata.img",
            "MTK_AllInOne_DA.bin",
            "MT6572_Android_scatter.txt",
            "DA_PL.bin",
            "DA_PL_CRYPTO20.bin",
            "DA_SWSEC.bin",
            "DA_SWSEC_CRYPTO20.bin",
            "kernel",
            "kernel_g368_nyx.bin"
        ]
    
    def cleanup_cache_directory(self):
        """Clean up old cache files to prevent accumulation and over-reliance on cached data"""
        try:
            debug_print("Cleaning up cache directory...")
            
            # Clean up old working tokens (older than 2 hours)
            working_tokens_file = os.path.join(self.cache_dir, "working_tokens.json")
            if os.path.exists(working_tokens_file):
                try:
                    with open(working_tokens_file, 'r') as f:
                        data = json.load(f)
                        cache_time = datetime.datetime.fromisoformat(data.get('cache_time', '1970-01-01T00:00:00'))
                        if datetime.datetime.now() - cache_time > datetime.timedelta(hours=2):
                            os.remove(working_tokens_file)
                            debug_print("Removed old working tokens cache (older than 2 hours)")
                except Exception as e:
                    debug_print(f"Error cleaning up working tokens: {e}")
            
            # Clean up old rate limit state (older than 1 hour)
            rate_limit_file = os.path.join(self.cache_dir, "rate_limits.json")
            if os.path.exists(rate_limit_file):
                try:
                    file_time = datetime.datetime.fromtimestamp(os.path.getmtime(rate_limit_file))
                    if datetime.datetime.now() - file_time > datetime.timedelta(hours=1):
                        os.remove(rate_limit_file)
                        debug_print("Removed old rate limit cache (older than 1 hour)")
                except Exception as e:
                    debug_print(f"Error cleaning up rate limit cache: {e}")
            
            # Clean up old startup tracking (older than 1 day)
            startup_tracking_file = os.path.join(self.cache_dir, "startup_tracking.json")
            if os.path.exists(startup_tracking_file):
                try:
                    file_time = datetime.datetime.fromtimestamp(os.path.getmtime(startup_tracking_file))
                    if datetime.datetime.now() - file_time > datetime.timedelta(days=1):
                        os.remove(startup_tracking_file)
                        debug_print("Removed old startup tracking cache (older than 1 day)")
                except Exception as e:
                    debug_print(f"Error cleaning up startup tracking cache: {e}")
            
            debug_print("Cache cleanup completed")
            
        except Exception as e:
            debug_print(f"Error during cache cleanup: {e}")
        try:
            old_dir = os.path.join(self.base_dir, ".old")
            if not os.path.exists(old_dir):
                return
                
            debug_print("Cleaning up .old directory...")
            removed_count = 0
            
            for root, dirs, files in os.walk(old_dir):
                for file in files:
                    if file != "y1_helper.py":
                        file_path = os.path.join(root, file)
                        try:
                            os.remove(file_path)
                            removed_count += 1
                            debug_print(f"Removed non-y1_helper.py file: {file_path}")
                        except Exception as e:
                            debug_print(f"Failed to remove {file_path}: {e}")
                            
            if removed_count > 0:
                debug_print(f"Cleaned up {removed_count} non-y1_helper.py files from .old directory")
                
        except Exception as e:
            debug_print(f"Error cleaning up .old directory: {e}")
    
    def is_cache_valid(self):
        """Check if cache is still valid (not expired)"""
        try:
            if not os.path.exists(self.cache_last_update_file):
                return False
                
            with open(self.cache_last_update_file, 'r') as f:
                last_update_str = f.read().strip()
                
            if not last_update_str:
                return False
                
            last_update = datetime.fromisoformat(last_update_str)
            expiry_time = last_update + timedelta(hours=self.cache_expiry_hours)
            
            return datetime.datetime.now() < expiry_time
            
        except Exception as e:
            debug_print(f"Error checking cache validity: {e}")
            return False
    
    def update_cache(self):
        """Update the cache with latest manifest and release data"""
        try:
            debug_print("Updating cache...")
            
            # Download latest manifest
            manifest_content = self.download_manifest_with_fallback()
            if manifest_content:
                # Save manifest to cache
                with open(self.cache_manifest_file, 'w', encoding='utf-8') as f:
                    f.write(manifest_content)
                
                # Parse manifest and build comprehensive index with release URLs
                self.build_cache_index_with_releases(manifest_content)
                
                # Update last update timestamp
                with open(self.cache_last_update_file, 'w') as f:
                    f.write(datetime.datetime.now().isoformat())
                    
                debug_print("Cache updated successfully")
            else:
                debug_print("Failed to download manifest for cache update")
                
        except Exception as e:
            debug_print(f"Error updating cache: {e}")
    
    def check_rate_limits(self, token=None):
        """Check if we can make an API call based on rate limits"""
        try:
            now = datetime.datetime.now()
            
            # Check unauthenticated limits
            if not token:
                unauthenticated = self.api_rate_limits['unauthenticated']
                if now > unauthenticated['reset_time']:
                    # Reset counter
                    unauthenticated['calls'] = 0
                    unauthenticated['reset_time'] = now + datetime.timedelta(hours=1)
                
                if unauthenticated['calls'] >= self.max_unauthenticated_calls:
                    self.rate_limit_exceeded = True
                    self.update_title_for_rate_limit()
                    debug_print("Unauthenticated API rate limit exceeded")
                    return False
                
                unauthenticated['calls'] += 1
                return True
            
            # Check authenticated limits
            if token not in self.api_rate_limits['authenticated']:
                self.api_rate_limits['authenticated'][token] = {
                    'calls': 0, 
                    'reset_time': now + datetime.timedelta(hours=1)
                }
            
            token_limits = self.api_rate_limits['authenticated'][token]
            if now > token_limits['reset_time']:
                # Reset counter
                token_limits['calls'] = 0
                token_limits['reset_time'] = now + datetime.timedelta(hours=1)
            
            if token_limits['calls'] >= self.max_authenticated_calls:
                debug_print(f"Authenticated API rate limit exceeded for token: {token[:10]}...")
                return False
            
            token_limits['calls'] += 1
            return True
            
        except Exception as e:
            debug_print(f"Error checking rate limits: {e}")
            return True  # Allow call if rate limit check fails
    
    def update_title_for_rate_limit(self):
        """Update title bar to show rate limit status"""
        try:
            if self.rate_limit_exceeded:
                self.title(f"Y1 Helper v{self.version} - Installer Features Temporarily Unavailable")
            else:
                self.title(f"Y1 Helper v{self.version} - created by Ryan Specter - u/respectyarn")
        except Exception as e:
            debug_print(f"Error updating title: {e}")
    
    def save_rate_limit_state(self):
        """Save rate limit state to file for persistence between sessions"""
        try:
            rate_limit_file = os.path.join(self.cache_dir, "rate_limits.json")
            state = {
                'unauthenticated': self.api_rate_limits['unauthenticated'],
                'authenticated': self.api_rate_limits['authenticated'],
                'rate_limit_exceeded': self.rate_limit_exceeded
            }
            
            # Convert datetime objects to strings for JSON serialization
            for key in state['unauthenticated']:
                if isinstance(state['unauthenticated'][key], datetime.datetime):
                    state['unauthenticated'][key] = state['unauthenticated'][key].isoformat()
            
            for token in state['authenticated']:
                for key in state['authenticated'][token]:
                    if isinstance(state['authenticated'][token][key], datetime.datetime):
                        state['authenticated'][token][key] = state['authenticated'][token][key].isoformat()
            
            with open(rate_limit_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            debug_print(f"Error saving rate limit state: {e}")
    
    def load_rate_limit_state(self):
        """Load rate limit state from file"""
        try:
            rate_limit_file = os.path.join(self.cache_dir, "rate_limits.json")
            if os.path.exists(rate_limit_file):
                with open(rate_limit_file, 'r') as f:
                    state = json.load(f)
                
                # Convert string timestamps back to datetime objects
                for key in state['unauthenticated']:
                    if key == 'reset_time':
                        state['unauthenticated'][key] = datetime.datetime.fromisoformat(state['unauthenticated'][key])
                
                for token in state['authenticated']:
                    for key in state['authenticated'][token]:
                        if key == 'reset_time':
                            state['authenticated'][token][key] = datetime.datetime.fromisoformat(state['authenticated'][token][key])
                
                self.api_rate_limits = state
                self.rate_limit_exceeded = state.get('rate_limit_exceeded', False)
                self.update_title_for_rate_limit()
                debug_print("Rate limit state loaded from file")
                
        except Exception as e:
            debug_print(f"Error loading rate limit state: {e}")
    
    def save_startup_tracking(self):
        """Save startup tracking information to file"""
        try:
            tracking_file = os.path.join(self.cache_dir, "startup_tracking.json")
            tracking_data = {
                'last_startup_time': self.startup_timestamp.isoformat(),
                'last_api_check_time': self.last_api_check_time.isoformat() if self.last_api_check_time else None,
                'last_cache_refresh_time': self.last_cache_refresh_time.isoformat() if self.last_cache_refresh_time else None
            }
            
            with open(tracking_file, 'w') as f:
                json.dump(tracking_data, f, indent=2)
            
            debug_print("Startup tracking saved")
        except Exception as e:
            debug_print(f"Error saving startup tracking: {e}")
    
    def load_startup_tracking(self):
        """Load startup tracking information from file"""
        try:
            tracking_file = os.path.join(self.cache_dir, "startup_tracking.json")
            if os.path.exists(tracking_file):
                with open(tracking_file, 'r') as f:
                    tracking_data = json.load(f)
                
                # Load last startup time
                if tracking_data.get('last_startup_time'):
                    try:
                        last_startup = datetime.datetime.fromisoformat(tracking_data['last_startup_time'])
                        time_since_last_startup = datetime.datetime.now() - last_startup
                        debug_print(f"Time since last startup: {time_since_last_startup.total_seconds() / 60:.1f} minutes")
                    except Exception as e:
                        debug_print(f"Error parsing last startup time: {e}")
                
                # Load last API check time
                if tracking_data.get('last_api_check_time'):
                    try:
                        self.last_api_check_time = datetime.datetime.fromisoformat(tracking_data['last_api_check_time'])
                    except Exception as e:
                        debug_print(f"Error parsing last API check time: {e}")
                
                # Load last cache refresh time
                if tracking_data.get('last_cache_refresh_time'):
                    try:
                        self.last_cache_refresh_time = datetime.datetime.fromisoformat(tracking_data['last_cache_refresh_time'])
                    except Exception as e:
                        debug_print(f"Error parsing last cache refresh time: {e}")
                
                debug_print("Startup tracking loaded")
        except Exception as e:
            debug_print(f"Error loading startup tracking: {e}")
    
    def should_skip_api_checks(self):
        """Check if API checks should be skipped due to recent startup"""
        try:
            if not self.last_api_check_time:
                return False
            
            time_since_last_check = datetime.datetime.now() - self.last_api_check_time
            minutes_since_check = time_since_last_check.total_seconds() / 60
            
            if minutes_since_check < self.api_check_cooldown_minutes:
                debug_print(f"Skipping API checks - only {minutes_since_check:.1f} minutes since last check")
                return True
            
            return False
        except Exception as e:
            debug_print(f"Error checking API check cooldown: {e}")
            return False
    
    def should_refresh_cache(self):
        """Check if cache should be refreshed based on time interval or user action"""
        try:
            # Always refresh if user triggered it
            if self.user_triggered_cache_refresh:
                self.user_triggered_cache_refresh = False
                return True
            
            # Check if cache is expired
            if not self.is_cache_valid():
                debug_print("Cache expired, refresh needed")
                return True
            
            # Check if enough time has passed since last refresh
            if self.last_cache_refresh_time:
                time_since_refresh = datetime.datetime.now() - self.last_cache_refresh_time
                minutes_since_refresh = time_since_refresh.total_seconds() / 60
                
                if minutes_since_refresh >= self.cache_refresh_interval_minutes:
                    debug_print(f"Cache refresh interval reached ({minutes_since_refresh:.1f} minutes)")
                    return True
            
            return False
        except Exception as e:
            debug_print(f"Error checking cache refresh: {e}")
            return False
    
    def fetch_config_from_github(self):
        """Fetch config.ini from GitHub master branch to ensure fresh API keys"""
        try:
            # Check rate limits before making any API calls
            if not self.check_rate_limits():
                debug_print("Rate limit exceeded, skipping config fetch")
                return False
            
            debug_print("Fetching config.ini from GitHub master branch...")
            
            # Try to get config.ini directly from master branch
            config_urls = [
                "https://raw.githubusercontent.com/team-slide/y1-helper/master/config.ini",
                "https://raw.githubusercontent.com/team-slide/y1-helper/main/config.ini"
            ]
            
            for config_url in config_urls:
                try:
                    # Use unauthenticated request to avoid consuming token quota
                    response = requests.get(config_url, timeout=30)
                    if response.status_code == 200:
                        # Save the fetched config
                        config_path = self.get_config_path()
                        with open(config_path, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        debug_print(f"Successfully fetched config.ini from {config_url}")
                        return True
                except Exception as e:
                    debug_print(f"Failed to fetch config from {config_url}: {e}")
                    continue
            
            # Try config.zip as fallback
            config_zip_urls = [
                "https://raw.githubusercontent.com/team-slide/y1-helper/master/config.zip",
                "https://raw.githubusercontent.com/team-slide/y1-helper/main/config.zip"
            ]
            
            for zip_url in config_zip_urls:
                try:
                    response = requests.get(zip_url, timeout=30)
                    if response.status_code == 200:
                        # Save zip file temporarily
                        temp_zip = os.path.join(self.cache_dir, "temp_config.zip")
                        with open(temp_zip, 'wb') as f:
                            f.write(response.content)
                        
                        # Extract config.ini
                        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                            zip_ref.extractall(self.cache_dir)
                        
                        # Move config.ini to proper location
                        extracted_config = os.path.join(self.cache_dir, "config.ini")
                        config_path = self.get_config_path()
                        if os.path.exists(extracted_config):
                            shutil.move(extracted_config, config_path)
                        
                        # Clean up
                        os.remove(temp_zip)
                        debug_print(f"Successfully extracted config.ini from {zip_url}")
                        return True
                        
                except Exception as e:
                    debug_print(f"Failed to fetch config.zip from {zip_url}: {e}")
                    continue
            
            debug_print("Failed to fetch config.ini from GitHub")
            return False
            
        except Exception as e:
            debug_print(f"Error fetching config from GitHub: {e}")
            return False
    
    def download_manifest_with_fallback(self):
        """Download manifest with multiple fallback methods"""
        try:
            # Method 1: Try authenticated GitHub API
            debug_print("Attempting authenticated manifest download...")
            response = self._make_github_request_with_retries(self.manifest_url)
            if response and response.status_code == 200:
                debug_print("Manifest downloaded via authenticated API")
                return response.text
            
            # Method 2: Try unauthenticated request
            debug_print("Attempting unauthenticated manifest download...")
            response = requests.get(self.manifest_url, timeout=30)
            if response.status_code == 200:
                debug_print("Manifest downloaded via unauthenticated request")
                return response.text
            
            # Method 3: Try alternative URLs
            debug_print("Attempting alternative manifest URLs...")
            alternative_urls = [
                "https://raw.githubusercontent.com/team-slide/slidia/main/slidia_manifest.xml",
                "https://github.com/team-slide/slidia/raw/main/slidia_manifest.xml"
            ]
            
            for url in alternative_urls:
                try:
                    response = requests.get(url, timeout=30)
                    if response.status_code == 200:
                        debug_print(f"Manifest downloaded via alternative URL: {url}")
                        return response.text
                except Exception as e:
                    debug_print(f"Alternative URL {url} failed: {e}")
                    continue
            
            debug_print("All manifest download methods failed")
            return None
            
        except Exception as e:
            debug_print(f"Error downloading manifest: {e}")
            return None
    
    def build_cache_index_with_releases(self, manifest_content):
        """Build comprehensive cache index with individual file URLs from GitHub releases"""
        try:
            root = ET.fromstring(manifest_content)
            
            # Create index structure
            index = ET.Element("cache_index")
            index.set("last_updated", datetime.datetime.now().isoformat())
            
            # Process firmware packages
            firmware_section = ET.SubElement(index, "firmware")
            for package in root.findall('.//package[@handler="Firmware"]'):
                firmware_entry = ET.SubElement(firmware_section, "entry")
                firmware_entry.set("name", package.get('name', ''))
                firmware_entry.set("repo", package.get('repo', ''))
                firmware_entry.set("url", package.get('url', ''))
                firmware_entry.set("handler", package.get('handler', ''))
                
                # Fetch complete release data with all file URLs
                release_data = self._get_complete_release_data(package.get('repo', ''), 'firmware')
                if release_data:
                    firmware_entry.set("release_url", release_data.get('release_url', ''))
                    firmware_entry.set("release_tag", release_data.get('tag_name', ''))
                    
                    # Add individual file URLs
                    files_section = ET.SubElement(firmware_entry, "files")
                    for file_info in release_data.get('files', []):
                        file_entry = ET.SubElement(files_section, "file")
                        file_entry.set("name", file_info.get('name', ''))
                        file_entry.set("url", file_info.get('url', ''))
                        file_entry.set("size", str(file_info.get('size', 0)))
                        file_entry.set("type", file_info.get('type', ''))
                        file_entry.set("download_count", str(file_info.get('download_count', 0)))
                    
                    debug_print(f"Added {len(release_data.get('files', []))} files for firmware {package.get('name', '')}")
                else:
                    debug_print(f"No release data found for firmware {package.get('name', '')}")
            
            # Process app packages
            app_section = ET.SubElement(index, "apps")
            for package in root.findall('.//package[@handler="App"]'):
                app_entry = ET.SubElement(app_section, "entry")
                app_entry.set("name", package.get('name', ''))
                app_entry.set("repo", package.get('repo', ''))
                app_entry.set("url", package.get('url', ''))
                app_entry.set("handler", package.get('handler', ''))
                
                # Fetch complete release data with all file URLs
                release_data = self._get_complete_release_data(package.get('repo', ''), 'app')
                if release_data:
                    app_entry.set("release_url", release_data.get('release_url', ''))
                    app_entry.set("release_tag", release_data.get('tag_name', ''))
                    
                    # Add individual file URLs
                    files_section = ET.SubElement(app_entry, "files")
                    for file_info in release_data.get('files', []):
                        file_entry = ET.SubElement(files_section, "file")
                        file_entry.set("name", file_info.get('name', ''))
                        file_entry.set("url", file_info.get('url', ''))
                        file_entry.set("size", str(file_info.get('size', 0)))
                        file_entry.set("type", file_info.get('type', ''))
                        file_entry.set("download_count", str(file_info.get('download_count', 0)))
                    
                    debug_print(f"Added {len(release_data.get('files', []))} files for app {package.get('name', '')}")
                else:
                    debug_print(f"No release data found for app {package.get('name', '')}")
            
            # Save index
            tree = ET.ElementTree(index)
            tree.write(self.cache_index_file, encoding='utf-8', xml_declaration=True)
            debug_print("Comprehensive cache index with file URLs built successfully")
            
        except Exception as e:
            debug_print(f"Error building cache index: {e}")
    
    def _get_complete_release_data(self, repo_name, item_type):
        """Get complete release data including all file URLs with minimal API calls"""
        try:
            if not repo_name:
                return None
            
            # Try to get release data via API (single call for all data)
            release_data = self._get_release_data_via_api(repo_name)
            if release_data:
                # Process files based on item type
                processed_files = self._process_release_files(release_data.get('assets', []), item_type)
                if processed_files:
                    return {
                        'release_url': f"https://github.com/{repo_name}/releases/latest",
                        'tag_name': release_data.get('tag_name', ''),
                        'files': processed_files
                    }
            
            # Fallback to page scraping if API fails
            release_data = self._get_release_data_via_page(repo_name, item_type)
            if release_data:
                return release_data
            
            debug_print(f"Could not get release data for {repo_name}")
            return None
            
        except Exception as e:
            debug_print(f"Error getting release data for {repo_name}: {e}")
            return None
    
    def _get_release_data_via_api(self, repo_name):
        """Get release data via GitHub API with minimal calls"""
        try:
            # Single API call to get latest release with all assets
            api_url = f"https://api.github.com/repos/{repo_name}/releases/latest"
            response = self._make_github_request_with_retries(api_url)
            
            if response and response.status_code == 200:
                return response.json()
            
            # Try unauthenticated API
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            debug_print(f"API method failed for {repo_name}: {e}")
            return None
    
    def _process_release_files(self, assets, item_type):
        """Process ALL release assets indiscriminately - let download logic decide what to use"""
        try:
            processed_files = []
            
            for asset in assets:
                file_name = asset.get('name', '')
                file_url = asset.get('browser_download_url', '')
                file_size = asset.get('size', 0)
                download_count = asset.get('download_count', 0)
                
                # Determine file type
                file_type = self._determine_file_type(file_name.lower())
                
                # Store ALL files indiscriminately - let the download logic decide what to use
                processed_files.append({
                    'name': file_name,
                    'url': file_url,
                    'size': file_size,
                    'type': file_type,
                    'download_count': download_count
                })
            
            # Sort files by download count (most popular first) and then by name
            processed_files.sort(key=lambda x: (x.get('download_count', 0), x.get('name', '')), reverse=True)
            
            debug_print(f"Cached {len(processed_files)} files for {item_type} release")
            return processed_files
            
        except Exception as e:
            debug_print(f"Error processing release files: {e}")
            return []
    
    def _determine_file_type(self, file_name):
        """Determine file type based on filename"""
        file_name = file_name.lower()
        if file_name.endswith('.apk'):
            return 'apk'
        elif file_name.endswith('.img'):
            return 'img'
        elif file_name.endswith('.zip'):
            return 'zip'
        elif file_name.endswith('.bin'):
            return 'bin'
        elif file_name.endswith('.tar.gz'):
            return 'tar.gz'
        else:
            return 'other'
    
    def _get_release_data_via_page(self, repo_name, item_type):
        """Get release data by scraping the releases page as fallback"""
        try:
            releases_url = f"https://github.com/{repo_name}/releases"
            response = requests.get(releases_url, timeout=30)
            
            if response.status_code == 200:
                import re
                
                # Look for download links in the page
                if item_type == 'app':
                    # For apps, look for APK files
                    download_pattern = r'href="([^"]*\.apk)"'
                else:
                    # For firmware, look for img, zip, bin, tar.gz files
                    download_pattern = r'href="([^"]*\.(img|zip|bin|tar\.gz))"'
                
                matches = re.findall(download_pattern, response.text)
                
                if matches:
                    files = []
                    for match in matches:
                        download_path = match[0] if isinstance(match, tuple) else match
                        if download_path.startswith('/'):
                            file_url = f"https://github.com{download_path}"
                        elif download_path.startswith('http'):
                            file_url = download_path
                        else:
                            continue
                        
                        # Extract filename from URL
                        file_name = download_path.split('/')[-1]
                        file_type = self._determine_file_type(file_name)
                        
                        files.append({
                            'name': file_name,
                            'url': file_url,
                            'size': 0,  # Size not available from page scraping
                            'type': file_type
                        })
                    
                    if files:
                        return {
                            'release_url': releases_url,
                            'tag_name': 'latest',
                            'files': files
                        }
            
            return None
            
        except Exception as e:
            debug_print(f"Page scraping method failed for {repo_name}: {e}")
            return None
    
    def _get_latest_release_url(self, repo_name):
        """Get the latest release URL for a GitHub repository"""
        try:
            if not repo_name:
                return None
                
            # Try multiple methods to get the latest release
            release_url = self._get_latest_release_via_api(repo_name)
            if release_url:
                return release_url
                
            # Fallback to releases page scraping
            release_url = self._get_latest_release_via_page(repo_name)
            if release_url:
                return release_url
                
            debug_print(f"Could not get release URL for {repo_name}")
            return None
            
        except Exception as e:
            debug_print(f"Error getting release URL for {repo_name}: {e}")
            return None
    
    def _get_latest_release_via_api(self, repo_name):
        """Get latest release URL via GitHub API"""
        try:
            # Try authenticated API first
            api_url = f"https://api.github.com/repos/{repo_name}/releases/latest"
            response = self._make_github_request_with_retries(api_url)
            
            if response and response.status_code == 200:
                release_data = response.json()
                if 'assets' in release_data and release_data['assets']:
                    # Get the first asset (usually the main file)
                    asset = release_data['assets'][0]
                    return asset.get('browser_download_url')
                    
            # Try unauthenticated API
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                release_data = response.json()
                if 'assets' in release_data and release_data['assets']:
                    asset = release_data['assets'][0]
                    return asset.get('browser_download_url')
                    
            return None
            
        except Exception as e:
            debug_print(f"API method failed for {repo_name}: {e}")
            return None
    
    def _get_latest_release_via_page(self, repo_name):
        """Get latest release URL by scraping the releases page"""
        try:
            releases_url = f"https://github.com/{repo_name}/releases"
            response = requests.get(releases_url, timeout=30)
            
            if response.status_code == 200:
                # Look for download links in the page
                import re
                # Pattern to match download links for releases
                download_pattern = r'href="([^"]*\.(apk|zip|tar\.gz|exe|dmg|deb|rpm))"'
                matches = re.findall(download_pattern, response.text)
                
                if matches:
                    # Get the first match and convert to full URL
                    download_path = matches[0][0]
                    if download_path.startswith('/'):
                        return f"https://github.com{download_path}"
                    elif download_path.startswith('http'):
                        return download_path
                        
            return None
            
        except Exception as e:
            debug_print(f"Page scraping method failed for {repo_name}: {e}")
            return None
    
    def _get_cached_release_url(self, repo_name, item_type):
        """Get cached release URL for a repository"""
        try:
            cached_index = self.get_cached_index()
            if cached_index is None:
                return None
                
            # Look for the entry in the appropriate section
            section = 'apps' if item_type == 'app' else 'firmware'
            for entry in cached_index.findall(f'.//{section}/entry'):
                if entry.get('repo') == repo_name:
                    return entry.get('release_url')
                    
            return None
            
        except Exception as e:
            debug_print(f"Error getting cached release URL for {repo_name}: {e}")
            return None
    
    def _get_cached_file_urls(self, repo_name, item_type):
        """Get cached file URLs for a repository"""
        try:
            cached_index = self.get_cached_index()
            if cached_index is None:
                return []
                
            # Look for the entry in the appropriate section
            section = 'apps' if item_type == 'app' else 'firmware'
            for entry in cached_index.findall(f'.//{section}/entry'):
                if entry.get('repo') == repo_name:
                    files = []
                    for file_entry in entry.findall('.//files/file'):
                        files.append({
                            'name': file_entry.get('name', ''),
                            'url': file_entry.get('url', ''),
                            'size': int(file_entry.get('size', 0)),
                            'type': file_entry.get('type', '')
                        })
                    return files
                    
            return []
            
        except Exception as e:
            debug_print(f"Error getting cached file URLs for {repo_name}: {e}")
            return []
    
    def _get_cached_file_url_by_type(self, repo_name, item_type, file_type):
        """Get cached file URL for a specific file type"""
        try:
            cached_files = self._get_cached_file_urls(repo_name, item_type)
            for file_info in cached_files:
                if file_info.get('type') == file_type:
                    return file_info.get('url')
            return None
            
        except Exception as e:
            debug_print(f"Error getting cached file URL for {repo_name} type {file_type}: {e}")
            return None
    
    def get_cached_manifest(self):
        """Get manifest content from cache"""
        try:
            if os.path.exists(self.cache_manifest_file):
                with open(self.cache_manifest_file, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            debug_print(f"Error reading cached manifest: {e}")
            return None
    
    def get_cached_index(self):
        """Get cache index"""
        try:
            if os.path.exists(self.cache_index_file):
                tree = ET.parse(self.cache_index_file)
                return tree.getroot()
            return None
        except Exception as e:
            debug_print(f"Error reading cache index: {e}")
            return None
    
    def refresh_cache_if_needed(self):
        """Refresh cache if it's expired or doesn't exist"""
        if not self.is_cache_valid():
            debug_print("Cache expired or invalid, refreshing...")
            self.update_cache()
    
    def setup_windows_11_theme(self):
        """Setup Windows 11 compatible theme with light/dark mode detection"""
        debug_print("Setting up Windows 11 theme")
        try:
            if platform.system() == "Windows":
                # Detect system theme
                self.is_dark_mode = self.detect_system_theme()
                debug_print(f"System theme detected: {'Dark' if self.is_dark_mode else 'Light'}")
                
                # Apply theme colors
                self.apply_theme_colors()
                
                # Set up theme change detection
                self.setup_theme_change_detection()
                
                debug_print("Windows 11 theme setup complete")
            else:
                debug_print("Not on Windows, using default theme")
                self.is_dark_mode = False
                self.apply_theme_colors()
        except Exception as e:
            debug_print(f"Theme setup failed: {e}")
            self.is_dark_mode = False
            self.apply_theme_colors()
    
    def detect_system_theme(self):
        """Detect if system is in dark mode"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            # AppsUseLightTheme: 0 = dark mode, 1 = light mode
            return value == 0
        except Exception as e:
            debug_print(f"Could not detect system theme: {e}")
            return False
    
    def apply_theme_colors(self):
        """Apply theme colors based on current mode"""
        debug_print(f"Applying {'dark' if self.is_dark_mode else 'light'} theme colors")
        
        if self.is_dark_mode:
            # Dark theme colors - Windows 11 style
            self.bg_color = "#202020"
            self.fg_color = "#ffffff"
            self.accent_color = "#0078d4"
            self.secondary_bg = "#2b2b2b"
            self.border_color = "#404040"
            self.menu_bg = "#202020"
            self.menu_fg = "#ffffff"
            self.menu_select_bg = "#0078d4"
            self.menu_select_fg = "#ffffff"
            self.button_bg = "#2b2b2b"
            self.button_fg = "#ffffff"
            self.button_active_bg = "#0078d4"
            self.button_active_fg = "#ffffff"
        else:
            # Light theme colors - Windows 11 style
            self.bg_color = "#ffffff"
            self.fg_color = "#000000"
            self.accent_color = "#0078d4"
            self.secondary_bg = "#f3f3f3"
            self.border_color = "#e0e0e0"
            self.menu_bg = "#ffffff"
            self.menu_fg = "#000000"
            self.menu_select_bg = "#0078d4"
            self.menu_select_fg = "#ffffff"
            self.button_bg = "#f3f3f3"
            self.button_fg = "#000000"
            self.button_active_bg = "#0078d4"
            self.button_active_fg = "#ffffff"
        
        # Apply colors to the window
        self.configure(bg=self.bg_color)
        
        # Apply Windows 11 title bar theming with proper window handle
        if platform.system() == "Windows":
            try:
                # Get the actual window handle
                hwnd = self.winfo_id()
                if hwnd:
                    # Set title bar theme using Windows API
                    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                        ctypes.byref(ctypes.c_bool(self.is_dark_mode)), ctypes.sizeof(ctypes.c_bool)
                    )
                    debug_print(f"Applied Windows 11 {'dark' if self.is_dark_mode else 'light'} title bar to hwnd: {hwnd}")
                else:
                    debug_print("Could not get window handle for title bar theming")
            except Exception as e:
                debug_print(f"Could not apply Windows 11 title bar theme: {e}")
        
        # Apply modern ttk style
        style = ttk.Style()
        
        # Configure the theme
        try:
            style.theme_use('clam')  # Use clam theme as base for better modern look
        except:
            pass  # Fall back to default if clam not available
        
        # Configure base style
        style.configure(".", 
                       background=self.bg_color,
                       foreground=self.fg_color,
                       fieldbackground=self.secondary_bg,
                       troughcolor=self.secondary_bg,
                       selectbackground=self.accent_color,
                       selectforeground=self.fg_color,
                       bordercolor=self.border_color,
                       lightcolor=self.border_color,
                       darkcolor=self.border_color,
                       focuscolor=self.accent_color)
        
        # Configure specific widgets with modern styling
        style.configure("TFrame", background=self.bg_color, relief="flat", borderwidth=0)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 9))
        style.configure("TButton", 
                       background=self.button_bg, 
                       foreground=self.button_fg,
                       bordercolor=self.border_color,
                       focuscolor=self.accent_color,
                       font=("Segoe UI", 9))
        style.map("TButton",
                 background=[("active", self.button_active_bg), ("pressed", self.button_active_bg)],
                 foreground=[("active", self.button_active_fg), ("pressed", self.button_active_fg)])
        
        style.configure("TCheckbutton", 
                       background=self.bg_color, 
                       foreground=self.fg_color,
                       font=("Segoe UI", 9))
        style.map("TCheckbutton",
                 background=[("active", self.bg_color)],
                 foreground=[("active", self.fg_color)])
        
        style.configure("TLabelframe", 
                       background=self.bg_color, 
                       foreground=self.fg_color,
                       bordercolor=self.border_color,
                       font=("Segoe UI", 9))
        style.configure("TLabelframe.Label", 
                       background=self.bg_color, 
                       foreground=self.fg_color,
                       font=("Segoe UI", 9, "bold"))
        
        style.configure("TMenubar", background=self.menu_bg, foreground=self.menu_fg)
        style.configure("TMenu", background=self.menu_bg, foreground=self.menu_fg)
        
        # Apply menu colors
        self.apply_menu_colors()
        
        # Update all existing widgets
        self.update_widget_colors()
        
        debug_print("Theme colors applied with modern styling")
        
        # Apply menu colors after theme is set
        if hasattr(self, 'apply_menu_colors'):
            self.apply_menu_colors()
        
        # Update pill colors if it exists
        if hasattr(self, 'update_pill'):
            if self.is_dark_mode:
                self.update_pill.configure(bg="#0078D4", fg="white")  # Windows blue, white text
            else:
                self.update_pill.configure(bg="#0078D4", fg="white")  # Windows blue, white text
    
    def apply_dialog_theme(self, dialog):
        """Apply theme colors to a dialog window"""
        try:
            # Apply background color to dialog
            dialog.configure(bg=self.bg_color)
            
            # Apply Windows 11 title bar theming if on Windows
            if platform.system() == "Windows":
                try:
                    hwnd = dialog.winfo_id()
                    if hwnd:
                        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                        ctypes.windll.dwmapi.DwmSetWindowAttribute(
                            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                            ctypes.byref(ctypes.c_bool(self.is_dark_mode)), ctypes.sizeof(ctypes.c_bool)
                        )
                except Exception as e:
                    debug_print(f"Could not apply Windows 11 title bar theme to dialog: {e}")
            
            debug_print(f"Applied {'dark' if self.is_dark_mode else 'light'} theme to dialog")
        except Exception as e:
            debug_print(f"Failed to apply dialog theme: {e}")
    
    def update_widget_colors(self):
        """Update colors of all existing widgets"""
        debug_print("Updating widget colors")
        try:
            # Update main window
            self.configure(bg=self.bg_color)
            
            # Update all child widgets recursively
            self._update_widget_tree(self)
            
            debug_print("Widget colors updated")
        except Exception as e:
            debug_print(f"Failed to update widget colors: {e}")
    
    def parse_app_manifest(self, manifest_content):
        """Parse the manifest XML to find app options with fallback to cache"""
        try:
            # Try to parse the provided manifest content first
            if manifest_content:
                root = ET.fromstring(manifest_content)
                app_options = []
                
                # Look for package elements with handler type "App"
                for package in root.findall('.//package'):
                    name = package.get('name', '')
                    repo = package.get('repo', '')
                    url = package.get('url', '')
                    handler = package.get('handler', '')
                    
                    # Check if this is an app package
                    if handler == 'App':
                        app_info = {
                            'name': name,
                            'repo': repo,
                            'url': url,
                            'handler': handler
                        }
                        
                        # Try to get cached file URLs for this app
                        cached_files = self._get_cached_file_urls(repo, 'app')
                        if cached_files:
                            app_info['cached_files'] = cached_files
                            debug_print(f"Using cached file URLs for {name}: {len(cached_files)} files")
                        
                        app_options.append(app_info)
                
                if app_options:
                    debug_print(f"Found {len(app_options)} app options from manifest")
                    return app_options
            
            # Fallback to cache if no apps found in manifest
            debug_print("No apps found in manifest, trying cache...")
            cached_index = self.get_cached_index()
            if cached_index:
                app_options = []
                for entry in cached_index.findall('.//apps/entry'):
                    app_options.append({
                        'name': entry.get('name', ''),
                        'repo': entry.get('repo', ''),
                        'url': entry.get('url', ''),
                        'handler': entry.get('handler', ''),
                        'release_url': entry.get('release_url', ''),
                        'cached_files': self._get_cached_file_urls(entry.get('repo', ''), 'app')
                    })
                
                if app_options:
                    debug_print(f"Found {len(app_options)} app options from cache")
                    return app_options
            
            debug_print("No apps found in manifest or cache")
            return []
            
        except Exception as e:
            debug_print(f"Error parsing app manifest: {e}")
            return []
    
    def show_app_selection_dialog(self, app_options):
        """Show dialog for app selection"""
        dialog = tk.Toplevel(self)
        dialog.title("Select App")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Apply theme colors to dialog
        self.apply_dialog_theme(dialog)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)
        dialog.geometry(f"400x300+{x}+{y}")
        
        # Create frame
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(frame, text="Select an app to install:", font=("Segoe UI", 12, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Create listbox with scrollbar
        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        listbox = tk.Listbox(listbox_frame, font=("Segoe UI", 10))
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # Apply theme colors to listbox (only if theme colors are available)
        try:
            if hasattr(self, 'bg_color') and hasattr(self, 'fg_color') and hasattr(self, 'accent_color'):
                listbox.configure(bg=self.bg_color, fg=self.fg_color, selectbackground=self.accent_color, selectforeground=self.fg_color)
        except Exception as e:
            debug_print(f"Could not apply theme to listbox: {e}")
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Function to strip markdown formatting
        def strip_markdown(text):
            """Remove markdown formatting from text"""
            import re
            # Remove **bold**, *italic*, `code`, and other markdown
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold**
            text = re.sub(r'\*(.*?)\*', r'\1', text)      # *italic*
            text = re.sub(r'`(.*?)`', r'\1', text)        # `code`
            text = re.sub(r'#+\s*', '', text)             # Headers
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Links
            return text.strip()
        
        # Populate listbox
        selected_app = None
        for i, app in enumerate(app_options):
            # Strip markdown and clean the name
            clean_name = strip_markdown(app['name'])
            # Make the first item (latest) bold using font weight instead of asterisks
            if i == 0:
                listbox.insert(tk.END, f"? {clean_name} (Latest)")
            else:
                listbox.insert(tk.END, clean_name)
        
        # Select first item by default
        if app_options:
            listbox.selection_set(0)
            selected_app = app_options[0]
        
        # Double-click to select
        def on_double_click(event):
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected_app = app_options[index]
                dialog.destroy()
        
        listbox.bind("<Double-Button-1>", on_double_click)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                nonlocal selected_app
                selected_app = app_options[index]
            dialog.destroy()
        
        def on_cancel():
            nonlocal selected_app
            selected_app = None
            dialog.destroy()
        
        ttk.Button(button_frame, text="Install", command=on_select).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT)
        
        dialog.wait_window()
        return selected_app



    def show_app_selection_dialog_with_error(self, error_message):
        """Show app selection dialog with error message inline"""
        dialog = tk.Toplevel(self)
        dialog.title("Select App")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Apply theme colors to dialog
        self.apply_dialog_theme(dialog)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)
        dialog.geometry(f"400x300+{x}+{y}")
        
        # Create frame
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(frame, text="Select an app to install:", font=("Segoe UI", 12, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Create listbox with scrollbar
        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        listbox = tk.Listbox(listbox_frame, font=("Segoe UI", 10))
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # Apply theme colors to listbox (only if theme colors are available)
        try:
            if hasattr(self, 'bg_color') and hasattr(self, 'fg_color') and hasattr(self, 'accent_color'):
                listbox.configure(bg=self.bg_color, fg=self.fg_color, selectbackground=self.accent_color, selectforeground=self.fg_color)
        except Exception as e:
            debug_print(f"Could not apply theme to listbox: {e}")
        
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Show error message in listbox
        listbox.insert(tk.END, error_message)
        listbox.itemconfig(0, fg='red')  # Make error message red
        
        # Disable selection for error message
        def on_select(event):
            if listbox.curselection() and listbox.curselection()[0] == 0:
                listbox.selection_clear(0, tk.END)
        
        listbox.bind('<<ListboxSelect>>', on_select)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Disable install button when error is shown
        install_btn = ttk.Button(button_frame, text="Install", command=lambda: None, state='disabled')
        install_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT)
        
        dialog.wait_window()
        return None
    
    def get_config_path(self):
        """Get config.ini path - try root first, then assets as fallback"""
        # Try root directory first
        root_config = os.path.join(self.base_dir, "config.ini")
        if os.path.exists(root_config):
            return root_config
        
        # Fallback to assets directory
        assets_config = os.path.join(assets_dir, "config.ini")
        if os.path.exists(assets_config):
            return assets_config
        
        # Return root path as default (will be created if needed)
        return root_config
    
    def download_and_unpack_config(self):
        """Download config.ini from GitHub master branch to root directory"""
        try:
            config_url = "https://raw.githubusercontent.com/team-slide/Y1-helper/master/config.ini"
            config_ini_path = os.path.join(self.base_dir, "config.ini")
            
            debug_print("Downloading config.ini from master branch...")
            
            # Download config.zip using robust retry mechanism
            response = self._make_github_request_with_retries(config_url)
            
            if response.status_code == 200:
                # Save the content to file
                with open(config_ini_path, 'w', encoding='utf-8') as f: f.write(response.text)
                
                # Config.ini downloaded directly
                
                debug_print("Config.ini downloaded successfully from master branch")
            else:
                debug_print(f"Failed to download config.ini: HTTP {response.status_code}")
                
        except Exception as e:
            debug_print(f"Failed to download config.ini: {e}")
            # Continue without config.ini if download fails
    
    def get_random_api_key(self):
        """Get a random API key from config.ini or hardcoded backup keys for rate limit prevention"""
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                debug_print(f"Config file not found at: {config_path}")
                return None

            
            api_keys = []
            
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Get all API keys from the config
            api_keys = []
            if 'api_keys' in config:
                try:
                    # Check for key_1, key_2, etc. format
                    for key, value in config['api_keys'].items():
                        if isinstance(value, str) and key.startswith('key_') and value.strip():
                            api_keys.append(value.strip())
                    
                    # Check for api_key0 - api_key1000 format
                    for i in range(1001):  # 0 to 1000
                        key_name = f'api_key{i}'
                        if key_name in config['api_keys']:
                            token = config['api_keys'][key_name].strip()
                            if token and token not in api_keys:
                                api_keys.append(token)
                except Exception as e:
                    debug_print(f"Error processing api_keys section: {e}")
            
            # If no API keys found, try legacy github.token
            if not api_keys and 'github' in config and 'token' in config['github']:
                try:
                    token = config['github']['token'].strip()
                    if token:
                        api_keys.append(token)
                except Exception as e:
                    debug_print(f"Error processing legacy token: {e}")
            
            if api_keys:
                # Return a random key
                import random
                selected_key = random.choice(api_keys)
                debug_print(f"Selected API key: {selected_key[:10]}... (length: {len(selected_key)})")
                return selected_key
            
            return None
        except Exception as e:
            debug_print(f"Error getting random API key: {e}")
            return None
    

    
    def has_api_keys_available(self):
        """Check if any API keys are available"""
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                return False
            
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            
            api_keys = []
            if 'api_keys' in config:
                try:
                    # Check for key_1, key_2, etc. format
                    for key, value in config['api_keys'].items():
                        if isinstance(value, str) and key.startswith('key_') and value.strip():
                            token = value.strip()
                            if token.startswith('github_pat_'):
                                token = token[11:]  # Remove 'github_pat_' prefix
                            api_keys.append(token)
                    
                    # Check for api_key0 - api_key1000 format
                    for i in range(1001):  # 0 to 1000
                        key_name = f'api_key{i}'
                        if key_name in config['api_keys']:
                            token = config['api_keys'][key_name].strip()
                            if token and token not in api_keys:
                                if token.startswith('github_pat_'):
                                    token = token[11:]  # Remove 'github_pat_' prefix
                                api_keys.append(token)
                except Exception as e:
                    debug_print(f"Error checking api_keys section: {e}")
            
            # If no API keys found, try legacy github.token
            if not api_keys and 'github' in config and 'token' in config['github']:
                try:
                    token = config['github']['token'].strip()
                    if token:
                        if token.startswith('github_pat_'):
                            token = token[11:]  # Remove 'github_pat_' prefix
                        api_keys.append(token)
                except Exception as e:
                    debug_print(f"Error checking legacy token: {e}")
            
            return len(api_keys) > 0
            
        except Exception as e:
            debug_print(f"Error getting random API key: {e}")
            return None
            debug_print(f"Error checking API keys availability: {e}")
            return False
    
    def create_github_request(self, url):
        """Create a urllib request with GitHub API headers and token"""
        token = self.get_random_api_key()
        headers = {
            'User-Agent': 'Y1-Helper/0.7.0'
        }
        
        if token:
            headers['Authorization'] = f'token {token}'
            debug_print(f"Using authenticated request with token")
        else:
            debug_print(f"Using unauthenticated request (60 requests/hour limit)")
        
        return urllib.request.Request(url, headers=headers)
    
    def handle_rate_limit_error(self, response, url):
        """Handle rate limit errors and provide fallback options"""
        if response.status == 403:  # Rate limit exceeded
            debug_print(f"Rate limit exceeded for {url}")
            
            # Check if we have API keys available
            if self.has_api_keys_available():
                debug_print("Retrying with a different API key...")
                # Try again with a different API key
                return self.create_github_request(url)
            else:
                debug_print("No API keys available, using unauthenticated request as fallback")
                # Use unauthenticated request as last resort
                headers = {
                    'User-Agent': 'Y1-Helper/0.7.0'
                }
                return urllib.request.Request(url, headers=headers)
        
        return None  # Not a rate limit error
    
    def has_api_keys_available(self):
        """Check if any API keys are available"""
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                return False
            
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            
            api_keys = []
            if 'api_keys' in config:
                try:
                    # Check for key_1, key_2, etc. format
                    for key, value in config['api_keys'].items():
                        if isinstance(value, str) and key.startswith('key_') and value.strip():
                            token = value.strip()
                            if token.startswith('github_pat_'):
                                token = token[11:]  # Remove 'github_pat_' prefix
                            api_keys.append(token)
                    
                    # Check for api_key0 - api_key1000 format
                    for i in range(1001):  # 0 to 1000
                        key_name = f'api_key{i}'
                        if key_name in config['api_keys']:
                            token = config['api_keys'][key_name].strip()
                            if token and token not in api_keys:
                                if token.startswith('github_pat_'):
                                    token = token[11:]  # Remove 'github_pat_' prefix
                                api_keys.append(token)
                except Exception as e:
                    debug_print(f"Error checking api_keys section: {e}")
            
            # If no API keys found, try legacy github.token
            if not api_keys and 'github' in config and 'token' in config['github']:
                try:
                    token = config['github']['token'].strip()
                    if token:
                        if token.startswith('github_pat_'):
                            token = token[11:]  # Remove 'github_pat_' prefix
                        api_keys.append(token)
                except Exception as e:
                    debug_print(f"Error checking legacy token: {e}")
            
            return len(api_keys) > 0
            
        except Exception as e:
            debug_print(f"Error checking API keys availability: {e}")
            return False
    
    def create_github_request(self, url):
        """Create a urllib request with GitHub API headers and token"""
        token = self.get_random_api_key()
        headers = {
            'User-Agent': 'Y1-Helper/0.7.0'
        }
        
        if token:
            headers['Authorization'] = f'token {token}'
            debug_print(f"Using authenticated request with token: {token[:10]}...")
        else:
            debug_print(f"Using unauthenticated request (60 requests/hour limit)")
        
        debug_print(f"Creating request for URL: {url}")
        return urllib.request.Request(url, headers=headers)
    
    def handle_rate_limit_error(self, response, url):
        """Handle rate limit and authorization errors and provide fallback options"""
        if response.status in [401, 403]:  # Unauthorized or rate limit exceeded
            debug_print(f"Authentication/rate limit error ({response.status}) for {url}")
            
            # Check if we have API keys available
            if self.has_api_keys_available():
                debug_print("Retrying with a different API key...")
                # Try again with a different API key
                return self.create_github_request(url)
            else:
                debug_print("No API keys available, using unauthenticated request as fallback")
                # Use unauthenticated request as last resort
                headers = {
                    'User-Agent': 'Y1-Helper/0.7.0'
                }
                return urllib.request.Request(url, headers=headers)
        
        return None  # Not an authentication/rate limit error
    
    def add_api_key_to_config(self, new_key):
        """Add a new API key to config.ini using the api_key format for thousands of keys"""
        try:
            config_path = self.get_config_path()
            
            import configparser
            config = configparser.ConfigParser()
            
            # Read existing config if it exists
            if os.path.exists(config_path):
                config.read(config_path)
            
            # Ensure api_keys section exists
            if 'api_keys' not in config:
                config['api_keys'] = {}
            
            # Find next available api_key number (supports 0-9999)
            key_number = 0
            while f'api_key{key_number}' in config['api_keys']:
                key_number += 1
                if key_number > 9999:  # Safety limit
                    debug_print("Maximum number of API keys reached (9999)")
                    return
            
            # Add the new key using api_key format
            config['api_keys'][f'api_key{key_number}'] = new_key
            
            # Write back to file
            with open(config_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            debug_print(f"Added new API key (api_key{key_number}) to config.ini")
            
            # Clear cached working tokens since we added a new one
            self._clear_cached_working_tokens()
            
        except Exception as e:
            debug_print(f"Error adding API key to config: {e}")
    
    def _clear_cached_working_tokens(self):
        """Clear cached working tokens when new tokens are added"""
        try:
            cache_file = os.path.join(self.cache_dir, "working_tokens.json")
            if os.path.exists(cache_file):
                os.remove(cache_file)
                debug_print("Cleared cached working tokens")
        except Exception as e:
            debug_print(f"Error clearing cached working tokens: {e}")
    
    def get_all_api_keys(self):
        """Get all available API keys with optimized handling for thousands of keys"""
        try:
            api_keys = []
            
            # First, try to get keys from config.ini
            config_path = self.get_config_path()
            debug_print(f"Looking for config at: {config_path}")
            if os.path.exists(config_path):
                import configparser
                config = configparser.ConfigParser()
                config.read(config_path)
                
                if 'api_keys' in config:
                    debug_print(f"Found api_keys section with {len(config['api_keys'])} entries")
                    try:
                        # Check for key_1, key_2, etc. format (legacy)
                        for key, value in config['api_keys'].items():
                            if isinstance(value, str) and key.startswith('key_') and value.strip():
                                token = value.strip()
                                if token.startswith('github_pat_'):
                                    token = token[11:]  # Remove 'github_pat_' prefix
                                if token not in api_keys:
                                    api_keys.append(token)
                        
                        # Check for api_key0 - api_key9999 format (supports thousands of keys)
                        # Use a more efficient approach for large numbers of keys
                        api_key_entries = []
                        for key, value in config['api_keys'].items():
                            if key.startswith('api_key') and isinstance(value, str) and value.strip():
                                try:
                                    # Extract number from api_key123 format
                                    key_num = int(key[8:])  # Remove 'api_key' prefix
                                    token = value.strip()
                                    if token.startswith('github_pat_'):
                                        token = token[11:]  # Remove 'github_pat_' prefix
                                    api_key_entries.append((key_num, token))
                                except ValueError:
                                    # Skip non-numeric keys
                                    continue
                        
                        # Sort by key number and add to api_keys
                        api_key_entries.sort(key=lambda x: x[0])
                        for key_num, token in api_key_entries:
                            if token not in api_keys:
                                api_keys.append(token)
                        
                        debug_print(f"Found {len(api_key_entries)} api_key entries")
                        
                    except Exception as e:
                        debug_print(f"Error processing api_keys section: {e}")
                
                # If no API keys found, try legacy github.token
                if not api_keys and 'github' in config and 'token' in config['github']:
                    try:
                        token = config['github']['token'].strip()
                        if token:
                            if token.startswith('github_pat_'):
                                token = token[11:]  # Remove 'github_pat_' prefix
                            api_keys.append(token)
                    except Exception as e:
                        debug_print(f"Error processing legacy token: {e}")
            else:
                debug_print(f"Config file not found at: {config_path}")
            
            debug_print(f"Total API keys found from config: {len(api_keys)}")
            
            # Add hardcoded backup keys
            for backup_key in BACKUP_API_KEYS:
                if backup_key not in api_keys:
                    api_keys.append(backup_key)
            
            debug_print(f"Total API keys available (config + backup): {len(api_keys)}")
            
            # Randomize the order to distribute load across tokens
            import random
            random.shuffle(api_keys)
            debug_print("API keys randomized for load distribution")
            
            return api_keys
            
        except Exception as e:
            debug_print(f"Error getting all API keys: {e}")
            # Return backup keys as fallback
            return BACKUP_API_KEYS.copy()
    
    def _test_token_efficiency(self, url, max_tokens_to_test=3):
        """
        Test a minimal subset of tokens to find working ones quickly.
        Returns a list of working tokens in order of preference.
        """
        try:
            # First check for cached working tokens
            cached_tokens = self._get_cached_working_tokens()
            if cached_tokens:
                debug_print("Using cached working tokens")
                return cached_tokens
            
            all_keys = self.get_all_api_keys()
            if not all_keys:
                debug_print("No API keys available")
                return []
            
            # Test only the last few tokens (most likely to work)
            tokens_to_test = all_keys[-max_tokens_to_test:] if len(all_keys) > max_tokens_to_test else all_keys
            working_tokens = []
            
            debug_print(f"Testing {len(tokens_to_test)} tokens for efficiency")
            
            for i, token in enumerate(tokens_to_test):
                if not self.check_rate_limits(token):
                    debug_print(f"Rate limit exceeded for token {token[:10]}..., skipping")
                    continue
                
                headers = {
                    'User-Agent': 'Y1-Helper/0.7.0',
                    'Authorization': f'token {token}'
                }
                
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        debug_print(f"Token {token[:10]}... is working (test {i+1})")
                        working_tokens.append(token)
                        # Stop after finding 2 working tokens (more efficient)
                        if len(working_tokens) >= 2:
                            break
                    else:
                        debug_print(f"Token {token[:10]}... failed with status {response.status_code}")
                except Exception as e:
                    debug_print(f"Token {token[:10]}... failed with error: {e}")
                    continue
            
            debug_print(f"Found {len(working_tokens)} working tokens")
            
            # Cache the working tokens for future use
            if working_tokens:
                self._cache_working_tokens(working_tokens)
            
            return working_tokens
            
        except Exception as e:
            debug_print(f"Error testing token efficiency: {e}")
            return []
    
    def _get_cached_working_tokens(self):
        """Get cached working tokens to avoid repeated testing"""
        try:
            cache_file = os.path.join(self.cache_dir, "working_tokens.json")
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    cache_time = datetime.datetime.fromisoformat(data.get('cache_time', '1970-01-01T00:00:00'))
                    # Cache is valid for 1 hour
                    if datetime.datetime.now() - cache_time < datetime.timedelta(hours=1):
                        tokens = data.get('tokens', [])
                        debug_print(f"Using {len(tokens)} cached working tokens")
                        return tokens
                    else:
                        debug_print("Cached working tokens expired")
            return []
        except Exception as e:
            debug_print(f"Error loading cached working tokens: {e}")
            return []
    
    def _cache_working_tokens(self, tokens):
        """Cache working tokens for future use"""
        try:
            cache_file = os.path.join(self.cache_dir, "working_tokens.json")
            
            # Read existing tokens to merge with new ones
            existing_tokens = []
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                        cache_time = datetime.datetime.fromisoformat(data.get('cache_time', '1970-01-01T00:00:00'))
                        # Only use existing tokens if cache is still valid (1 hour)
                        if datetime.datetime.now() - cache_time < datetime.timedelta(hours=1):
                            existing_tokens = data.get('tokens', [])
                except Exception:
                    pass
            
            # Merge tokens, avoiding duplicates
            all_tokens = existing_tokens.copy()
            for token in tokens:
                if token not in all_tokens:
                    all_tokens.append(token)
            
            # Keep only the most recent 5 tokens to avoid cache bloat
            if len(all_tokens) > 5:
                all_tokens = all_tokens[-5:]
            
            data = {
                'cache_time': datetime.datetime.now().isoformat(),
                'tokens': all_tokens
            }
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            debug_print(f"Cached {len(all_tokens)} working tokens (added {len(tokens)} new)")
        except Exception as e:
            debug_print(f"Error caching working tokens: {e}")
    
    def _add_working_token(self, token):
        """Add a single working token to the cache immediately"""
        try:
            self._cache_working_tokens([token])
        except Exception as e:
            debug_print(f"Error adding working token: {e}")
    
    def _generate_github_fallback_urls(self, original_url):
        """Generate multiple fallback URLs for GitHub content access"""
        fallback_urls = [original_url]  # Start with original URL
        
        # If it's a raw.githubusercontent.com URL, generate fallbacks
        if 'raw.githubusercontent.com' in original_url:
            # Parse the URL to extract components
            try:
                # Example: https://raw.githubusercontent.com/team-slide/slidia/refs/heads/main/slidia_manifest.xml
                parts = original_url.replace('https://raw.githubusercontent.com/', '').split('/')
                if len(parts) >= 4:
                    owner = parts[0]
                    repo = parts[1]
                    branch = parts[2]
                    file_path = '/'.join(parts[3:])
                    
                    # Generate different branch variations
                    branch_variations = [
                        branch,
                        branch.replace('refs/heads/', ''),
                        'main',
                        'master',
                        'develop'
                    ]
                    
                    # Generate different URL patterns
                    for branch_var in branch_variations:
                        # Standard raw.githubusercontent.com
                        fallback_urls.append(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch_var}/{file_path}")
                        
                        # Alternative: GitHub API content endpoint
                        fallback_urls.append(f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={branch_var}")
                        
                        # Alternative: Direct GitHub web interface (for text files)
                        if file_path.endswith(('.xml', '.txt', '.md', '.json', '.ini', '.cfg')):
                            fallback_urls.append(f"https://github.com/{owner}/{repo}/blob/{branch_var}/{file_path}?raw=true")
                    
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_urls = []
                    for url in fallback_urls:
                        if url not in seen:
                            seen.add(url)
                            unique_urls.append(url)
                    
                    return unique_urls
                    
            except Exception as e:
                debug_print(f"Error generating fallback URLs: {e}")
        
        # If it's a GitHub API URL, generate fallbacks
        elif 'api.github.com' in original_url:
            # For API URLs, try different authentication methods but keep the same URL
            return [original_url]
        
        # For other URLs, return as is
        return fallback_urls

    def _make_github_request_with_retries(self, url, method='GET', stream=False, **kwargs):
        """
        Make a GitHub request with highly optimized token selection prioritizing working tokens.
        
        Strategy:
        1. Use cached working tokens first (most efficient)
        2. Only test new tokens if no working tokens available
        3. Cache successful tokens immediately for future use
        4. Skip expensive fallback to all tokens
        5. Early termination on success
        
        Returns: requests.Response object
        Raises: requests.RequestException if all attempts fail
        """
        # Check rate limits before making any API calls
        if not self.check_rate_limits():
            debug_print("Rate limit exceeded, trying unauthenticated request only")
            # Try unauthenticated request as last resort
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers={'User-Agent': 'Y1-Helper/0.7.0'},
                    stream=stream,
                    timeout=30,
                    **kwargs
                )
                
                if response.status_code == 200:
                    debug_print(f"Unauthenticated request successful for {url} (status: {response.status_code})")
                    return response
                else:
                    debug_print(f"Unauthenticated request failed with status {response.status_code} for URL: {url}")
                    raise Exception("Rate limit exceeded and unauthenticated request failed")
                    
            except Exception as e:
                debug_print(f"Unauthenticated request failed for URL {url}: {e}")
                raise Exception("Rate limit exceeded and all request methods failed")
        
        # Generate fallback URLs
        fallback_urls = self._generate_github_fallback_urls(url)
        
        # Get working tokens (cached or tested)
        working_tokens = self._get_cached_working_tokens()
        if not working_tokens and fallback_urls:
            debug_print("No cached working tokens, testing token efficiency")
            working_tokens = self._test_token_efficiency(fallback_urls[0])
        
        debug_print(f"Making GitHub request with {len(fallback_urls)} URL variations")
        debug_print(f"Working tokens available: {len(working_tokens)}")
        
        # Try each URL with working tokens first
        for fallback_url in fallback_urls:
            debug_print(f"Trying URL: {fallback_url}")
            
            # Try working tokens first (most efficient)
            if working_tokens:
                for i, token in enumerate(working_tokens):
                    if not self.check_rate_limits(token):
                        continue
                    
                    debug_print(f"Trying working token: {token[:10]}... (attempt {i+1}/{len(working_tokens)})")
                    
                    headers = {
                        'User-Agent': 'Y1-Helper/0.7.0',
                        'Authorization': f'token {token}'
                    }
                    
                    try:
                        response = requests.request(
                            method=method,
                            url=fallback_url,
                            headers=headers,
                            stream=stream,
                            timeout=30,
                            **kwargs
                        )
                        
                        # Check for authentication/authorization errors
                        if response.status_code in [401, 403]:
                            debug_print(f"Working token failed with status {response.status_code}: {token[:10]}...")
                            continue
                        
                        # Success! Stop trying more tokens
                        debug_print(f"Request successful with working token: {token[:10]}... (status: {response.status_code})")
                        # Ensure this token stays in cache (move to front)
                        self._add_working_token(token)
                        return response
                        
                    except requests.RequestException as e:
                        debug_print(f"Request failed with working token {token[:10]}...: {e}")
                        continue
            
            # If no working tokens available, test a small subset of tokens
            if not working_tokens:
                debug_print("No working tokens available, testing new tokens")
                all_keys = self.get_all_api_keys()
                if all_keys:
                    # Test only the last few tokens (most likely to work)
                    tokens_to_test = all_keys[-3:] if len(all_keys) > 3 else all_keys
                    
                    for i, token in enumerate(tokens_to_test):
                        if not self.check_rate_limits(token):
                            continue
                        
                        debug_print(f"Testing new token: {token[:10]}... (attempt {i+1}/{len(tokens_to_test)})")
                        
                        headers = {
                            'User-Agent': 'Y1-Helper/0.7.0',
                            'Authorization': f'token {token}'
                        }
                        
                        try:
                            response = requests.request(
                                method=method,
                                url=fallback_url,
                                headers=headers,
                                stream=stream,
                                timeout=30,
                                **kwargs
                            )
                            
                            # Check for authentication/authorization errors
                            if response.status_code in [401, 403]:
                                debug_print(f"New token failed with status {response.status_code}: {token[:10]}...")
                                continue
                            
                            # Success! Cache this token immediately and return
                            debug_print(f"New token successful: {token[:10]}... (status: {response.status_code})")
                            self._add_working_token(token)
                            return response
                            
                        except requests.RequestException as e:
                            debug_print(f"New token failed with error: {token[:10]}...: {e}")
                            continue
            
            # If all authenticated requests failed for this URL, try unauthenticated
            debug_print(f"All authenticated requests failed for {fallback_url}, trying unauthenticated")
            if self.check_rate_limits():  # Check unauthenticated rate limit
                headers = {
                    'User-Agent': 'Y1-Helper/0.7.0'
                }
                
                try:
                    response = requests.request(
                        method=method,
                        url=fallback_url,
                        headers=headers,
                        stream=stream,
                        timeout=30,
                        **kwargs
                    )
                    debug_print(f"Unauthenticated request successful for {fallback_url} (status: {response.status_code})")
                    return response
                    
                except requests.RequestException as e:
                    debug_print(f"Unauthenticated request also failed for {fallback_url}: {e}")
                    continue
        
        # All attempts failed
        debug_print("All GitHub request attempts failed")
        raise Exception("Failed to make GitHub request after all retries")
    
    def update_config_background(self):
        """Update config.ini in background every 5 minutes"""
        try:
            # Download and unpack config
            self.download_and_unpack_config()
            
            # Schedule next update in 5 minutes
            self.after(300000, self.update_config_background)  # 300000ms = 5 minutes
            
        except Exception as e:
            debug_print(f"Background config update failed: {e}")
            # Schedule retry in 1 minute on failure
            self.after(60000, self.update_config_background)  # 60000ms = 1 minute
    
    def check_for_updates(self):
        """Check for newer version and return update info if available"""
        try:
            debug_print("Checking for updates...")
            
            # Get random API key for rate limit prevention
            api_key = self.get_random_api_key()
            
            # GitHub API URL for latest release
            api_url = "https://api.github.com/repos/itsry/Y1-helper/releases/latest"
            
            # Try authenticated request first
            request = self.create_github_request(api_url)
            release_data = None
            
            try:
                with urllib.request.urlopen(request) as response:
                    release_data = json.loads(response.read().decode('utf-8'))
                    debug_print(f"Latest release: {release_data.get('tag_name', 'unknown')}")
            except urllib.error.HTTPError as e:
                if e.code == 403:  # Rate limit or authentication error
                    debug_print("Authenticated request failed, trying fallback...")
                    # Try with different API key or unauthenticated
                    request = self.handle_rate_limit_error(e, api_url)
                    if request:
                        with urllib.request.urlopen(request) as response:
                            release_data = json.loads(response.read().decode('utf-8'))
                            debug_print(f"Fallback successful, latest release: {release_data.get('tag_name', 'unknown')}")
                else:
                    debug_print(f"HTTP error checking for updates: {e.code}")
                    return None
            except Exception as e:
                debug_print(f"Error checking for updates: {e}")
                return None
            
            if not release_data:
                debug_print("No release data received")
                return None
            
            # Extract version from tag name (remove 'v' prefix if present)
            latest_version = release_data.get('tag_name', '')
            if latest_version.startswith('v'):
                latest_version = latest_version[1:]
            
            debug_print(f"Current version: {self.version}, Latest version: {latest_version}")
            
            # Compare versions
            if self.compare_versions(latest_version, self.version) > 0:
                # Newer version available
                update_info = {
                    'version': latest_version,
                    'assets': release_data.get('assets', []),
                    'body': release_data.get('body', ''),
                    'html_url': release_data.get('html_url', '')
                }
                debug_print(f"Update available: {latest_version}")
                return update_info
            else:
                debug_print("No update available")
                return None
                
        except Exception as e:
            debug_print(f"Error in check_for_updates: {e}")
            return None
    
    def compare_versions(self, version1, version2):
        """Compare two version strings, return 1 if version1 > version2, -1 if version1 < version2, 0 if equal"""
        try:
            # Split versions into components
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad with zeros to make lengths equal
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            # Compare each component
            for i in range(max_len):
                if v1_parts[i] > v2_parts[i]:
                    return 1
                elif v1_parts[i] < v2_parts[i]:
                    return -1
            
            return 0  # Versions are equal
        except Exception as e:
            debug_print(f"Error comparing versions: {e}")
            return 0
    
    def download_update(self, update_info):
        """Download update executable (patch.exe or installer.exe)"""
        try:
            debug_print("Starting update download...")
            
            # Look for patch.exe first, then installer.exe
            target_asset = None
            for asset in update_info['assets']:
                asset_name = asset.get('name', '').lower()
                if asset_name == 'patch.exe':
                    target_asset = asset
                    break
                elif asset_name == 'installer.exe' and target_asset is None:
                    target_asset = asset
            
            if not target_asset:
                debug_print("No suitable update executable found")
                return None, "No update executable (patch.exe or installer.exe) found in release"
            
            debug_print(f"Downloading {target_asset['name']}...")
            
            # Create progress dialog
            progress_dialog = self.create_progress_dialog("Downloading Update")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label'):
                        progress_dialog.status_label.config(text=message)
                        progress_dialog.update()
                    debug_print(f"Update Download Progress: {message}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress(f"Downloading {target_asset['name']}...")
            
            # Download the file
            download_url = target_asset['browser_download_url']
            temp_file = os.path.join(tempfile.gettempdir(), target_asset['name'])
            
            # Get random API key for rate limit prevention
            api_key = self.get_random_api_key()
            
            # Try authenticated download first
            request = self.create_github_request(download_url)
            
            try:
                with urllib.request.urlopen(request) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(temp_file, 'wb') as f:
                        while True:
                            chunk = response.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                update_progress(f"Downloading {target_asset['name']}... {progress:.1f}%")
                            else:
                                update_progress(f"Downloading {target_asset['name']}... {downloaded_size} bytes")
                
                debug_print(f"Update downloaded successfully: {temp_file}")
                return temp_file, None
                
            except urllib.error.HTTPError as e:
                if e.code == 403:  # Rate limit or authentication error
                    debug_print("Authenticated download failed, trying fallback...")
                    # Try with different API key or unauthenticated
                    request = self.handle_rate_limit_error(e, download_url)
                    if request:
                        with urllib.request.urlopen(request) as response:
                            total_size = int(response.headers.get('content-length', 0))
                            downloaded_size = 0
                            
                            with open(temp_file, 'wb') as f:
                                while True:
                                    chunk = response.read(8192)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    
                                    if total_size > 0:
                                        progress = (downloaded_size / total_size) * 100
                                        update_progress(f"Downloading {target_asset['name']}... {progress:.1f}%")
                                    else:
                                        update_progress(f"Downloading {target_asset['name']}... {downloaded_size} bytes")
                        
                        debug_print(f"Update downloaded successfully via fallback: {temp_file}")
                        return temp_file, None
                    else:
                        return None, f"Download failed: HTTP {e.code}"
                else:
                    return None, f"Download failed: HTTP {e.code}"
            except Exception as e:
                debug_print(f"Error downloading update: {e}")
                return None, f"Download failed: {str(e)}"
            finally:
                if progress_dialog:
                    progress_dialog.destroy()
                    
        except Exception as e:
            debug_print(f"Error in download_update: {e}")
            return None, f"Download failed: {str(e)}"
    
    def run_update(self, update_file):
        """Run the downloaded update executable and close y1_helper"""
        try:
            debug_print(f"Running update: {update_file}")
            
            # Launch the update executable
            subprocess.Popen([update_file], shell=True)
            
            # Close y1_helper after a short delay
            self.after(1000, self.quit)
            
        except Exception as e:
            debug_print(f"Error running update: {e}")
            messagebox.showerror("Update Error", f"Failed to run update: {str(e)}")
    
    def show_update_available(self, update_info):
        """Show update available dialog"""
        try:
            result = messagebox.askyesno(
                "Update Available",
                f"A newer version ({update_info['version']}) is available!\n\n"
                f"Current version: {self.version}\n"
                f"Latest version: {update_info['version']}\n\n"
                f"Would you like to download and install the update now?",
                icon='info'
            )
            
            if result:
                self.perform_update(update_info)
                
        except Exception as e:
            debug_print(f"Error showing update dialog: {e}")
    
    def perform_update(self, update_info):
        """Perform the update process"""
        try:
            debug_print("Starting update process...")
            
            # Download the update
            update_file, error = self.download_update(update_info)
            
            if error:
                messagebox.showerror("Update Error", f"Failed to download update: {error}")
                return
            
            if update_file and os.path.exists(update_file):
                # Run the update
                self.run_update(update_file)
            else:
                messagebox.showerror("Update Error", "Update file not found after download")
                
        except Exception as e:
            debug_print(f"Error in perform_update: {e}")
            messagebox.showerror("Update Error", f"Update failed: {str(e)}")
    
    def check_and_show_update(self):
        """Show update dialog if update is available"""
        try:
            debug_print("Manual update check triggered")
            
            if self.update_available and self.update_info:
                self.show_team_slide_update_prompt(self.update_info)
            else:
                # Do a fresh check if no stored update info
                update_info = self.check_for_team_slide_updates()
                if update_info:
                    self.update_available = True
                    self.update_info = update_info
                    self.show_team_slide_update_prompt(update_info)
                else:
                    messagebox.showinfo("Update Check", "You are running the latest version!")
                
        except Exception as e:
            debug_print(f"Error in check_and_show_update: {e}")
            messagebox.showerror("Update Error", f"Failed to check for updates: {str(e)}")
    
    def show_update_pill_if_needed(self):
        """Show update button if update is available and update menu labels"""
        try:
            if self.update_available and self.update_info:
                debug_print("Update available, showing update button")
                # Show the update button
                self.update_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
                
                # Update button text with version info
                if self.update_info.get('patch_asset'):
                    self.update_btn.config(text=f"?? Update to v{self.update_info['version']} (Patch)")
                elif self.update_info.get('installer_asset'):
                    self.update_btn.config(text=f"?? Update to v{self.update_info['version']} (Full)")
                else:
                    self.update_btn.config(text=f"?? Update to v{self.update_info['version']}")
                
                # Update Help menu title to show update available
                if hasattr(self, 'help_menu') and hasattr(self, 'help_menu_index'):
                    self.menubar.entryconfig(self.help_menu_index, label="Help - Update Available")
                    debug_print("Updated Help menu title to show Update Available")
                
                # Update menu item labels for update actions
                if hasattr(self, 'update_app_index') and hasattr(self, 'reinstall_app_index'):
                    self.help_menu.entryconfig(self.update_app_index, label="Quick Update")
                    self.help_menu.entryconfig(self.reinstall_app_index, label="Full Install")
                    debug_print("Updated menu labels for update actions")
            else:
                debug_print("No update available")
                # Reset to normal labels if no update available
                if hasattr(self, 'help_menu') and hasattr(self, 'help_menu_index'):
                    self.menubar.entryconfig(self.help_menu_index, label="Help")
                    if hasattr(self, 'update_app_index') and hasattr(self, 'reinstall_app_index'):
                        self.help_menu.entryconfig(self.update_app_index, label="Update App")
                        self.help_menu.entryconfig(self.reinstall_app_index, label="Repair App")
                    debug_print("Reset Help menu title to normal")
                
        except Exception as e:
            debug_print(f"Error in show_update_pill_if_needed: {e}")
    
    def check_for_team_slide_updates(self):
        """Check for updates from team-slide/y1-helper repository with caching"""
        try:
            debug_print("Checking for team-slide updates...")
            
            # First check cached update info
            cached_update = self._get_cached_update_info()
            if cached_update:
                debug_print(f"Found cached update info: {cached_update['version']}")
                if self._is_cached_update_newer(cached_update):
                    debug_print("Cached update is newer than current version")
                    return cached_update
                else:
                    debug_print("Cached update is not newer than current version")
            
            # Method 1: GitHub API (primary method)
            update_info = self._check_updates_via_api()
            if update_info:
                # Cache the update info
                self._cache_update_info(update_info)
                # Check if version matches latest (no update needed)
                if update_info.get('version') == self.version:
                    self._cleanup_old_installer_files()
                return update_info
            
            # Method 2: Fallback to releases page scraping
            debug_print("API method failed, trying releases page fallback...")
            update_info = self._check_updates_via_releases_page()
            if update_info:
                # Cache the update info
                self._cache_update_info(update_info)
                # Check if version matches latest (no update needed)
                if update_info.get('version') == self.version:
                    self._cleanup_old_installer_files()
                return update_info
            
            # Method 3: Fallback to master branch checking
            debug_print("Releases page failed, trying master branch fallback...")
            update_info = self._check_updates_via_master_branch()
            if update_info:
                # Cache the update info
                self._cache_update_info(update_info)
                # Check if version matches latest (no update needed)
                if update_info.get('version') == self.version:
                    self._cleanup_old_installer_files()
                return update_info
            
            debug_print("All update check methods failed")
            return None
            
        except Exception as e:
            debug_print(f"Error checking for team-slide updates: {e}")
            return None
    
    def _get_cached_update_info(self):
        """Get cached update information"""
        try:
            update_cache_file = os.path.join(self.cache_dir, "update_cache.json")
            if os.path.exists(update_cache_file):
                with open(update_cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                # Check if cache is still valid (24 hours)
                cache_time = datetime.datetime.fromisoformat(cached_data.get('cache_time', ''))
                if datetime.datetime.now() - cache_time < datetime.timedelta(hours=24):
                    debug_print("Using cached update information")
                    return cached_data.get('update_info')
                else:
                    debug_print("Cached update information expired")
            return None
        except Exception as e:
            debug_print(f"Error reading cached update info: {e}")
            return None
    
    def _cache_update_info(self, update_info):
        """Enhanced cache update information with URLs, release versions, and tags"""
        try:
            update_cache_file = os.path.join(self.cache_dir, "update_cache.json")
            
            # Enhanced cache data structure
            cache_data = {
                'cache_time': datetime.datetime.now().isoformat(),
                'update_info': update_info,
                'cached_urls': {},
                'release_version': update_info.get('version'),
                'release_tag': update_info.get('tag_name', f"v{update_info.get('version', '')}"),
                'installer_url': None,
                'patch_url': None
            }
            
            # Extract installer.exe and patch.exe URLs
            if 'assets' in update_info:
                for asset in update_info['assets']:
                    asset_name = asset.get('name', '').lower()
                    if asset_name == 'installer.exe':
                        cache_data['installer_url'] = asset.get('browser_download_url')
                        cache_data['cached_urls']['installer.exe'] = asset.get('browser_download_url')
                    elif asset_name == 'patch.exe':
                        cache_data['patch_url'] = asset.get('browser_download_url')
                        cache_data['cached_urls']['patch.exe'] = asset.get('browser_download_url')
            
            # Add hardcoded fallback URLs for team-slide/y1-helper
            if not cache_data['installer_url']:
                cache_data['installer_url'] = f"https://github.com/team-slide/y1-helper/releases/latest/download/installer.exe"
                cache_data['cached_urls']['installer.exe'] = cache_data['installer_url']
            if not cache_data['patch_url']:
                cache_data['patch_url'] = f"https://github.com/team-slide/y1-helper/releases/latest/download/patch.exe"
                cache_data['cached_urls']['patch.exe'] = cache_data['patch_url']
            
            with open(update_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            debug_print("Enhanced update information cached")
        except Exception as e:
            debug_print(f"Error caching enhanced update info: {e}")
    
    def _is_cached_update_newer(self, cached_update):
        """Check if cached update is newer than current version"""
        try:
            current_version = self.version
            cached_version = cached_update.get('version')
            
            if not current_version or not cached_version:
                return False
            
            # Compare versions
            comparison = self.compare_versions(current_version, cached_version)
            return comparison < 0  # Cached version is newer
        except Exception as e:
            debug_print(f"Error comparing cached update: {e}")
            return False
    
    def _get_cached_update_urls(self):
        """Get cached installer and patch URLs"""
        try:
            update_cache_file = os.path.join(self.cache_dir, "update_cache.json")
            if os.path.exists(update_cache_file):
                with open(update_cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                return {
                    'installer_url': cached_data.get('installer_url'),
                    'patch_url': cached_data.get('patch_url'),
                    'cached_urls': cached_data.get('cached_urls', {})
                }
            return None
        except Exception as e:
            debug_print(f"Error reading cached update URLs: {e}")
            return None
    
    def _cleanup_old_update_files(self):
        """Delete old installer.exe and patch.exe files from the project directory (not subdirectories)."""
        try:
            debug_print("Cleaning up old update files...")
            files_to_remove = ['installer.exe', 'patch.exe']
            removed_count = 0
            
            for filename in files_to_remove:
                file_path = os.path.join(self.base_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        debug_print(f"Removed old update file: {filename}")
                        removed_count += 1
                    except Exception as e:
                        debug_print(f"Failed to remove {filename}: {e}")
            
            if removed_count > 0:
                debug_print(f"Cleaned up {removed_count} old update file(s)")
            else:
                debug_print("No old update files found to clean up")
                
        except Exception as e:
            debug_print(f"Error during cleanup: {e}")
    
    def _cleanup_old_installer_files(self):
        """Clean up installer/patch.exe files when version matches latest release"""
        try:
            current_version = self.version
            if not current_version:
                return
            
            # Use cached update info to avoid infinite recursion
            cached_update = self._get_cached_update_info()
            if not cached_update:
                return
            
            latest_version = cached_update.get('version')
            if not latest_version:
                return
            
            # If versions match, clean up installer files
            if self.compare_versions(current_version, latest_version) == 0:
                debug_print(f"Version {current_version} matches latest {latest_version}, cleaning up installer files")
                for file in os.listdir(self.base_dir):
                    if file.endswith('.exe') and file in ['patch.exe', 'installer.exe']:
                        file_path = os.path.join(self.base_dir, file)
                        try:
                            os.remove(file_path)
                            debug_print(f"Removed installer file (up to date): {file}")
                        except Exception as e:
                            debug_print(f"Failed to remove {file}: {e}")
        except Exception as e:
            debug_print(f"Error cleaning up installer files: {e}")
    
    def _check_updates_via_api(self):
        """Check for updates using GitHub API"""
        try:
            debug_print("Checking updates via GitHub API...")
            
            # GitHub API URL for latest release
            api_url = "https://api.github.com/repos/team-slide/y1-helper/releases/latest"
            
            # Use our comprehensive retry mechanism with rate limiting
            response = self._make_github_request_with_retries(api_url)
            
            if response.status_code != 200:
                debug_print(f"GitHub API returned status {response.status_code}")
                return None
            
            release_data = json.loads(response.text)
            
            if not release_data:
                debug_print("No release data received from API")
                return None
            
            # Extract version from tag name (remove 'v' prefix if present)
            latest_version = release_data.get('tag_name', '')
            if latest_version.startswith('v'):
                latest_version = latest_version[1:]
            
            debug_print(f"Current version: {self.version}, Latest version: {latest_version}")
            
            # Always return the latest release info, regardless of version comparison
            debug_print(f"Latest version found: {latest_version}")
            
            # Check for patch.exe or installer.exe
            assets = release_data.get('assets', [])
            patch_asset = None
            installer_asset = None
            
            for asset in assets:
                asset_name = asset.get('name', '').lower()
                if asset_name == 'patch.exe':
                    patch_asset = asset
                    debug_print("Found patch.exe in release")
                elif asset_name == 'installer.exe':
                    installer_asset = asset
                    debug_print("Found installer.exe in release")
            
            return {
                'version': latest_version,
                'tag_name': release_data.get('tag_name', ''),
                'body': release_data.get('body', ''),
                'assets': assets,
                'patch_asset': patch_asset,
                'installer_asset': installer_asset,
                'html_url': release_data.get('html_url', ''),
                'method': 'api'
            }
            
        except Exception as e:
            debug_print(f"Error checking updates via API: {e}")
            return None
    
    def _check_updates_via_releases_page(self):
        """Check for updates by scraping the releases page"""
        try:
            debug_print("Checking updates via releases page...")
            
            # Scrape the releases page
            releases_url = "https://github.com/team-slide/y1-helper/releases"
            response = self._make_github_request_with_retries(releases_url)
            
            if response.status_code != 200:
                debug_print(f"Releases page returned status {response.status_code}")
                return None
            
            # Parse the HTML to find the latest release
            import re
            content = response.text
            
            # Look for release tags in the page
            tag_pattern = r'releases/tag/v?([0-9]+\.[0-9]+\.[0-9]+)'
            tags = re.findall(tag_pattern, content)
            
            if not tags:
                debug_print("No version tags found in releases page")
                return None
            
            # Get the latest version
            latest_version = max(tags, key=lambda v: self.compare_versions(v, "0.0.0"))
            debug_print(f"Found latest version in releases page: {latest_version}")
            
            # Always return the latest release info, regardless of version comparison
            debug_print(f"Latest version found: {latest_version}")
            
            # Check for patch.exe or installer.exe in the page
            patch_found = 'patch.exe' in content.lower()
            installer_found = 'installer.exe' in content.lower()
            
            debug_print(f"Found in releases page - patch.exe: {patch_found}, installer.exe: {installer_found}")
            
            return {
                'version': latest_version,
                'tag_name': f"v{latest_version}",
                'body': f"Update to version {latest_version}",
                'assets': [],
                'patch_asset': {'name': 'patch.exe'} if patch_found else None,
                'installer_asset': {'name': 'installer.exe'} if installer_found else None,
                'html_url': f"https://github.com/team-slide/y1-helper/releases/tag/v{latest_version}",
                'method': 'releases_page'
            }
            
            return None
            
        except Exception as e:
            debug_print(f"Error checking updates via releases page: {e}")
            return None
    
    def _check_updates_via_master_branch(self):
        """Check for updates by checking master branch version"""
        try:
            debug_print("Checking updates via master branch...")
            
            # Check version.txt in master branch
            version_url = "https://raw.githubusercontent.com/team-slide/y1-helper/master/version.txt"
            response = self._make_github_request_with_retries(version_url)
            
            if response.status_code != 200:
                debug_print(f"Master version.txt returned status {response.status_code}")
                return None
            
            latest_version = response.text.strip()
            debug_print(f"Master branch version: {latest_version}")
            
            # Always return the latest release info, regardless of version comparison
            debug_print(f"Latest version found in master: {latest_version}")
            
            # Check for patch.zip or installer.exe in master
            patch_url = "https://raw.githubusercontent.com/team-slide/y1-helper/master/patch.zip"
            installer_url = "https://raw.githubusercontent.com/team-slide/y1-helper/master/installer.exe"
            
            patch_response = self._make_github_request_with_retries(patch_url, method='HEAD')
            installer_response = self._make_github_request_with_retries(installer_url, method='HEAD')
            
            patch_available = patch_response.status_code == 200
            installer_available = installer_response.status_code == 200
            
            debug_print(f"Master branch - patch.zip: {patch_available}, installer.exe: {installer_available}")
            
            return {
                'version': latest_version,
                'tag_name': f"v{latest_version}",
                'body': f"Update to version {latest_version} from master branch",
                'assets': [],
                'patch_asset': {'name': 'patch.zip', 'browser_download_url': patch_url} if patch_available else None,
                'installer_asset': {'name': 'installer.exe', 'browser_download_url': installer_url} if installer_available else None,
                'html_url': "https://github.com/team-slide/y1-helper",
                'method': 'master_branch'
            }
            
        except Exception as e:
            debug_print(f"Error checking updates via master branch: {e}")
            return None
    
    def download_patch_from_team_slide(self):
        """Download patch files from team-slide/y1-helper repository"""
        try:
            debug_print("Downloading patch from team-slide repository...")
            
            # GitHub API URL for the patch directory
            api_url = "https://api.github.com/repos/team-slide/y1-helper/contents/patch"
            
            # Use our comprehensive retry mechanism
            response = self._make_github_request_with_retries(api_url)
            contents_data = json.loads(response.text)
            
            if not isinstance(contents_data, list):
                debug_print("No patch directory found or not a directory")
                return False
            
            # Create patch directory
            patch_dir = os.path.join(self.base_dir, 'patch')
            os.makedirs(patch_dir, exist_ok=True)
            
            downloaded_files = 0
            
            for item in contents_data:
                if item.get('type') == 'file':
                    file_name = item.get('name')
                    download_url = item.get('download_url')
                    
                    if file_name and download_url:
                        file_path = os.path.join(patch_dir, file_name)
                        debug_print(f"Downloading patch file: {file_name}")
                        
                        # Download the file
                        file_response = self._make_github_request_with_retries(download_url)
                        with open(file_path, 'wb') as f:
                            f.write(file_response.content)
                        
                        downloaded_files += 1
                        debug_print(f"Downloaded: {file_name}")
            
            debug_print(f"Downloaded {downloaded_files} patch files")
            return downloaded_files > 0
            
        except Exception as e:
            debug_print(f"Error downloading patch: {e}")
            return False
    
    def show_team_slide_update_prompt(self, update_info):
        """Show update prompt for team-slide updates"""
        try:
            title = "Update Available"
            message = f"A new version of Y1 Helper is available!\n\n"
            message += f"Current version: {self.version}\n"
            message += f"New version: {update_info['version']}\n\n"
            
            if update_info.get('body'):
                # Strip markdown and limit length
                body = update_info['body']
                if len(body) > 200:
                    body = body[:200] + "..."
                message += f"Changes:\n{body}\n\n"
            
            if update_info.get('patch_asset'):
                message += "A patch update is available for quick installation."
            elif update_info.get('installer_asset'):
                message += "A full installer is available for complete update."
            else:
                message += "Update files are available for download."
            
            message += "\n\nWould you like to download and install the update now?"
            
            result = messagebox.askyesno(title, message)
            
            if result:
                self.perform_team_slide_update(update_info)
                
        except Exception as e:
            debug_print(f"Error showing update prompt: {e}")
    
    def perform_team_slide_update(self, update_info):
        """Perform the team-slide update, prioritizing patch.exe over installer.exe, and robustly handle UAC/installer launching."""
        try:
            debug_print("Performing team-slide update...")
            # Prioritize patch.exe if both are available
            if update_info.get('patch_asset'):
                debug_print("Using patch.exe for update")
                self.download_and_run_patch(update_info['patch_asset'])
            elif update_info.get('installer_asset'):
                debug_print("Using installer.exe for update")
                self.download_and_run_installer(update_info['installer_asset'])
            else:
                debug_print("No update assets found, trying manual patch download")
                if self.download_patch_from_team_slide():
                    messagebox.showinfo("Patch Downloaded", 
                        "Patch files have been downloaded and will be applied on the next restart of Y1 Helper.")
                else:
                    messagebox.showerror("Download Failed", 
                        "Failed to download patch files. Please try again later.")
        except Exception as e:
            debug_print(f"Error performing update: {e}")
            messagebox.showerror("Update Failed", f"Update failed: {e}")

    def _run_update_exe_and_wait(self, exe_path, friendly_name):
        """Launch the update exe and close Y1 Helper immediately."""
        try:
            debug_print(f"Launching {friendly_name}: {exe_path}")
            # Start the process and close Y1 Helper immediately
            try:
                subprocess.Popen([exe_path], shell=True)
                debug_print(f"{friendly_name} launched successfully. Closing Y1 Helper immediately.")
                self.quit()
            except Exception as e:
                debug_print(f"Failed to launch {friendly_name}: {e}")
                messagebox.showerror(f"{friendly_name} Launch Failed", f"Failed to launch {friendly_name}: {e}")
                return
        except Exception as e:
            debug_print(f"Error launching {friendly_name}: {e}")
            messagebox.showerror(f"{friendly_name} Error", f"Error while launching {friendly_name}: {e}")
            self.quit()

    def download_and_run_patch(self, patch_asset):
        """Download and run patch with fallback methods and robust process handling."""
        try:
            progress_dialog = self.create_progress_dialog("Downloading Patch")
            start_time = time.time()
            
            def update_progress(status, detail="", progress=None, speed_info=""):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label'):
                        progress_dialog.status_label.config(text=status)
                        if detail:
                            progress_dialog.detail_label.config(text=detail)
                        if progress is not None:
                            progress_dialog.progress_bar.config(value=progress)
                        if speed_info:
                            progress_dialog.speed_label.config(text=speed_info)
                        progress_dialog.update()
                    debug_print(f"Patch Download Progress: {status} - {detail}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress("Preparing to download patch...", "Connecting to server...")
            
            if patch_asset.get('browser_download_url'):
                download_url = patch_asset['browser_download_url']
                file_name = patch_asset.get('name', 'patch.exe')
            else:
                file_name = patch_asset.get('name', 'patch.exe')
                if file_name == 'patch.zip':
                    download_url = "https://raw.githubusercontent.com/team-slide/y1-helper/master/patch.zip"
                else:
                    download_url = f"https://github.com/team-slide/y1-helper/releases/latest/download/{file_name}"
            
            debug_print(f"Downloading from: {download_url}")
            temp_file = os.path.join(tempfile.gettempdir(), file_name)
            
            update_progress("Connecting to download server...", f"URL: {download_url}")
            
            response = self._make_github_request_with_retries(download_url, stream=True)
            if response.status_code != 200:
                debug_print(f"Failed to download patch: HTTP {response.status_code}")
                progress_dialog.destroy()
                messagebox.showerror("Download Failed", f"Failed to download patch: HTTP {response.status_code}")
                return
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            last_update_time = time.time()
            last_downloaded_size = 0
            
            update_progress("Downloading patch file...", f"File: {file_name}", 0)
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        current_time = time.time()
                        
                        # Update progress every 100ms or when significant progress made
                        if current_time - last_update_time >= 0.1 or downloaded_size - last_downloaded_size >= 1024*1024:  # 1MB
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                downloaded_mb = downloaded_size / (1024*1024)
                                total_mb = total_size / (1024*1024)
                                
                                # Calculate speed
                                elapsed = current_time - start_time
                                if elapsed > 0:
                                    speed_mbps = (downloaded_size / (1024*1024)) / elapsed
                                    eta_seconds = (total_size - downloaded_size) / (downloaded_size / elapsed) if downloaded_size > 0 else 0
                                    
                                    if eta_seconds > 60:
                                        eta_text = f"{eta_seconds/60:.1f} minutes remaining"
                                    elif eta_seconds > 0:
                                        eta_text = f"{eta_seconds:.1f} seconds remaining"
                                    else:
                                        eta_text = "Calculating..."
                                    
                                    speed_info = f"Speed: {speed_mbps:.1f} MB/s • {eta_text}"
                                else:
                                    speed_info = "Calculating speed..."
                                
                                update_progress(
                                    f"Downloading {file_name}...",
                                    f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB ({progress:.1f}%)",
                                    progress,
                                    speed_info
                                )
                            else:
                                downloaded_mb = downloaded_size / (1024*1024)
                                update_progress(
                                    f"Downloading {file_name}...",
                                    f"{downloaded_mb:.1f} MB downloaded",
                                    None,
                                    "Size unknown"
                                )
                            
                            last_update_time = current_time
                            last_downloaded_size = downloaded_size
            
            progress_dialog.destroy()
            debug_print(f"Patch downloaded successfully: {temp_file}")
            
            if file_name.endswith('.zip'):
                update_progress("Extracting patch files...", "Unpacking downloaded archive...")
                patch_dir = os.path.join(self.base_dir, 'patch')
                os.makedirs(patch_dir, exist_ok=True)
                with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                    zip_ref.extractall(patch_dir)
                os.remove(temp_file)
                messagebox.showinfo("Patch Applied", "Patch files have been downloaded and will be applied on next restart.")
            else:
                self._run_update_exe_and_wait(temp_file, "Patch Installer")
                
        except Exception as e:
            debug_print(f"Error downloading/running patch: {e}")
            if 'progress_dialog' in locals():
                progress_dialog.destroy()
            messagebox.showerror("Patch Error", f"Failed to download or run patch: {e}")

    def download_and_run_installer(self, installer_asset):
        """Download and run installer.exe with robust process handling."""
        try:
            progress_dialog = self.create_progress_dialog("Downloading Installer")
            start_time = time.time()
            
            def update_progress(status, detail="", progress=None, speed_info=""):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label'):
                        progress_dialog.status_label.config(text=status)
                        if detail:
                            progress_dialog.detail_label.config(text=detail)
                        if progress is not None:
                            progress_dialog.progress_bar.config(value=progress)
                        if speed_info:
                            progress_dialog.speed_label.config(text=speed_info)
                        progress_dialog.update()
                    debug_print(f"Installer Download Progress: {status} - {detail}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress("Preparing to download installer...", "Connecting to server...")
            
            if installer_asset.get('browser_download_url'):
                download_url = installer_asset['browser_download_url']
                file_name = installer_asset.get('name', 'installer.exe')
            else:
                file_name = installer_asset.get('name', 'installer.exe')
                download_url = f"https://github.com/team-slide/y1-helper/releases/latest/download/{file_name}"
            
            debug_print(f"Downloading from: {download_url}")
            temp_file = os.path.join(tempfile.gettempdir(), file_name)
            
            update_progress("Connecting to download server...", f"URL: {download_url}")
            
            response = self._make_github_request_with_retries(download_url, stream=True)
            if response.status_code != 200:
                debug_print(f"Failed to download installer: HTTP {response.status_code}")
                progress_dialog.destroy()
                messagebox.showerror("Download Failed", f"Failed to download installer: HTTP {response.status_code}")
                return
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            last_update_time = time.time()
            last_downloaded_size = 0
            
            update_progress("Downloading installer file...", f"File: {file_name}", 0)
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        current_time = time.time()
                        
                        # Update progress every 100ms or when significant progress made
                        if current_time - last_update_time >= 0.1 or downloaded_size - last_downloaded_size >= 1024*1024:  # 1MB
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                downloaded_mb = downloaded_size / (1024*1024)
                                total_mb = total_size / (1024*1024)
                                
                                # Calculate speed
                                elapsed = current_time - start_time
                                if elapsed > 0:
                                    speed_mbps = (downloaded_size / (1024*1024)) / elapsed
                                    eta_seconds = (total_size - downloaded_size) / (downloaded_size / elapsed) if downloaded_size > 0 else 0
                                    
                                    if eta_seconds > 60:
                                        eta_text = f"{eta_seconds/60:.1f} minutes remaining"
                                    elif eta_seconds > 0:
                                        eta_text = f"{eta_seconds:.1f} seconds remaining"
                                    else:
                                        eta_text = "Calculating..."
                                    
                                    speed_info = f"Speed: {speed_mbps:.1f} MB/s • {eta_text}"
                                else:
                                    speed_info = "Calculating speed..."
                                
                                update_progress(
                                    f"Downloading {file_name}...",
                                    f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB ({progress:.1f}%)",
                                    progress,
                                    speed_info
                                )
                            else:
                                downloaded_mb = downloaded_size / (1024*1024)
                                update_progress(
                                    f"Downloading {file_name}...",
                                    f"{downloaded_mb:.1f} MB downloaded",
                                    None,
                                    "Size unknown"
                                )
                            
                            last_update_time = current_time
                            last_downloaded_size = downloaded_size
            
            progress_dialog.destroy()
            debug_print(f"Installer downloaded successfully: {temp_file}")
            self._run_update_exe_and_wait(temp_file, "Installer")
            
        except Exception as e:
            debug_print(f"Error downloading and running installer: {e}")
            if 'progress_dialog' in locals():
                progress_dialog.destroy()
            messagebox.showerror("Installer Failed", f"Failed to download or run installer: {e}")
    
    def check_and_show_team_slide_update(self):
        """Check for team-slide updates and show prompt if available"""
        try:
            update_info = self.check_for_team_slide_updates()
            if update_info:
                self.show_team_slide_update_prompt(update_info)
        except Exception as e:
            debug_print(f"Error checking for team-slide updates: {e}")
    
    def show_patch_status_message(self):
        """Show status message if patches were applied"""
        try:
            patch_dir = os.path.join(self.base_dir, 'patch')
            if not os.path.exists(patch_dir):
                return
            
            # Check if patch directory has contents
            patch_files = []
            for item in os.listdir(patch_dir):
                item_path = os.path.join(patch_dir, item)
                if os.path.isfile(item_path):
                    patch_files.append(item)
                elif os.path.isdir(item_path):
                    for root, dirs, files in os.walk(item_path):
                        for file in files:
                            rel_path = os.path.relpath(os.path.join(root, file), patch_dir)
                            patch_files.append(rel_path)
            
            if patch_files:
                # Show status message
                status_message = f"Patches applied automatically ({len(patch_files)} files). Changes will take effect on next restart."
                self.status_var.set(status_message)
                
                # Also show in a temporary message box
                messagebox.showinfo("Patches Applied", 
                    f"Patches have been applied automatically ({len(patch_files)} files).\n\n"
                    "The changes will take effect when you restart Y1 Helper.")
                
        except Exception as e:
            debug_print(f"Error showing patch status: {e}")
    
    def download_app(self, app_info):
        """Download app from GitHub releases with progress"""
        progress_dialog = None
        try:
            # Create progress dialog
            progress_dialog = self.create_progress_dialog("Downloading App")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label') and progress_dialog.winfo_exists():
                        progress_dialog.status_label.config(text=message)
                        progress_dialog.update()
                    debug_print(f"App Download Progress: {message}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress("Connecting to GitHub...")
            
            # Check if we have cached file URLs for this app
            cached_files = app_info.get('cached_files', [])
            debug_print(f"App {app_info['name']} cached files: {len(cached_files)} files")
            if cached_files:
                debug_print(f"Cached files for {app_info['name']}: {cached_files}")
                # Find APK file in cached files
                apk_file = None
                for file_info in cached_files:
                    if file_info.get('type') == 'apk':
                        apk_file = file_info
                        break
                
                if apk_file:
                    debug_print(f"Using cached APK URL for {app_info['name']}: {apk_file['url']}")
                    update_progress("Using cached APK information...")
                else:
                    debug_print(f"No APK file found in cached files for {app_info['name']}, falling back to API")
                    update_progress("No cached APK found, fetching from GitHub...")
            else:
                debug_print(f"No cached files for {app_info['name']}, using API fallback")
                update_progress("No cached information, fetching from GitHub...")
            
                # Download directly from cached URL
                download_path = os.path.join(tempfile.gettempdir(), f"{app_info['name'].replace(' ', '_')}.apk")
                
                update_progress(f"Downloading {app_info['name']} from cached URL...")
                debug_print(f"Downloading {app_info['name']} from cached URL: {apk_file['url']}")
                
                # Download the file
                debug_print(f"Downloading from URL: {apk_file['url']}")
                response = requests.get(apk_file['url'], stream=True, timeout=60)
                response.raise_for_status()
                debug_print(f"Download response status: {response.status_code}")
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                update_progress(f"Downloading {app_info['name']}... {progress}%")
                
                update_progress(f"Download complete!")
                
                # Return the download path for installation
                return download_path
            
            # Fallback to original method if no cached URL or no APK in cached files
            # Get random API key from config for rate limit prevention
            api_key = self.get_random_api_key()
            
            # Parse the GitHub URL to get repo and latest release
            repo_url = app_info['url']
            release_data = None
            repo_path = None
            headers = {}
            if api_key:
                headers['Authorization'] = f'token {api_key}'

            if 'github.com' in repo_url:
                if '/releases/latest' in repo_url:
                    repo_path = repo_url.replace('https://github.com/', '').replace('/releases/latest', '')
                    debug_print(f"Parsed repo path: {repo_path}")
                    update_progress(f"Fetching latest release from {repo_path}...")
                    api_url = f"https://api.github.com/repos/{repo_path}/releases/latest"
                    try:
                        # Use comprehensive GitHub API authentication with retries
                        debug_print(f"Fetching latest release from API: {api_url}")
                        response = self._make_github_request_with_retries(api_url)
                        debug_print(f"API response status: {response.status_code}")
                        release_data = json.loads(response.text)
                        debug_print(f"Latest release data: {release_data.get('tag_name', 'unknown')} - {len(release_data.get('assets', []))} assets")
                    except Exception as e:
                        if hasattr(e, 'code') and e.code == 404:
                            debug_print(f"Latest endpoint failed (404), trying first release...")
                            api_url = f"https://api.github.com/repos/{repo_path}/releases"
                            try:
                                # Use comprehensive GitHub API authentication with retries
                                response = self._make_github_request_with_retries(api_url)
                                releases = json.loads(response.text)
                                if releases:
                                    release_data = releases[0]
                                    debug_print(f"First release data: {release_data.get('tag_name', 'unknown')} - {len(release_data.get('assets', []))} assets")
                                else:
                                    raise Exception(f"No releases found for {repo_path}")
                            except Exception as fallback_error:
                                raise Exception(f"GitHub API error: {fallback_error}")
                        else:
                            raise Exception(f"GitHub API error: {e}")
                elif '/releases/' in repo_url or repo_url.rstrip('/').endswith('/releases'):
                    # Handle /releases/ or /releases
                    repo_path = repo_url.replace('https://github.com/', '').split('/releases')[0]
                    debug_print(f"Parsed repo path: {repo_path}")
                    update_progress(f"Fetching latest release from {repo_path}...")
                    api_url = f"https://api.github.com/repos/{repo_path}/releases"
                    try:
                        # Use comprehensive GitHub API authentication with retries
                        response = self._make_github_request_with_retries(api_url)
                        releases = json.loads(response.text)
                        if releases:
                            release_data = releases[0]
                            debug_print(f"First release data: {release_data.get('tag_name', 'unknown')} - {len(release_data.get('assets', []))} assets")
                        else:
                            raise Exception(f"No releases found for {repo_path}")
                    except Exception as e:
                        raise Exception(f"GitHub API error: {e}")
                else:
                    raise Exception("Unsupported GitHub releases URL format. Please use a /releases or /releases/latest link.")
            
            # Find APK asset
            update_progress("Searching for APK file...")
            apk_asset = None
            available_assets = []
            for asset in release_data.get('assets', []):
                available_assets.append(asset['name'])
                if asset['name'].endswith('.apk'):
                    apk_asset = asset
                    break
            
            debug_print(f"Available assets: {available_assets}")
            
            if not apk_asset:
                progress_dialog.destroy()
                raise Exception(f"No APK found in latest release for {app_info['name']}. Available assets: {available_assets}")
            
            # Download APK
            download_url = apk_asset['browser_download_url']
            download_path = os.path.join(tempfile.gettempdir(), f"{app_info['name'].replace(' ', '_')}.apk")
            
            update_progress(f"Downloading {app_info['name']}...")
            debug_print(f"Downloading {app_info['name']} from: {download_url}")
            
            # Use comprehensive retry mechanism for APK download
            response = self._make_github_request_with_retries(download_url, stream=True)
            response.raise_for_status()
            # Get file size for progress
            file_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if file_size > 0:
                        percent = (downloaded / file_size) * 100
                        update_progress(f"Downloading {app_info['name']}... {percent:.1f}%")
                    else:
                        update_progress(f"Downloading {app_info['name']}... {downloaded:,} bytes")
            
            update_progress("Download complete!")
            
            debug_print(f"Downloaded {app_info['name']} to: {download_path}")
            return download_path
        except Exception as e:
            debug_print(f"Error downloading app {app_info['name']}: {e}")
            debug_print(f"Full traceback: {traceback.format_exc()}")
            return None
        finally:
            # Always clean up progress dialog
            if progress_dialog:
                try:
                    if progress_dialog.winfo_exists():
                        progress_dialog.destroy()
                except Exception as e:
                    debug_print(f"Error destroying progress dialog: {e}")
    
    def install_downloaded_app(self, app_path):
        """Install downloaded APK using ADB with progress"""
        progress_dialog = None
        try:
            # Create progress dialog
            progress_dialog = self.create_progress_dialog("Installing App")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label') and progress_dialog.winfo_exists():
                        progress_dialog.status_label.config(text=message)
                        progress_dialog.update()
                    debug_print(f"App Install Progress: {message}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress("Installing APK to device...")
            
            success, stdout, stderr = self.run_adb_command(f"install -r \"{app_path}\"")
            
            if success:
                update_progress("Installation completed successfully!")
                debug_print(f"App installed successfully: {app_path}")
                return True, None
            else:
                error_msg = stderr.strip() if stderr else stdout.strip()
                # Provide more user-friendly error messages
                if "no devices/emulators found" in error_msg.lower():
                    user_friendly_error = "No device connected via ADB"
                elif "device offline" in error_msg.lower():
                    user_friendly_error = "Device is offline"
                elif "unauthorized" in error_msg.lower():
                    user_friendly_error = "Device not authorized"
                else:
                    user_friendly_error = error_msg
                
                update_progress(f"Installation failed: {user_friendly_error}")
                debug_print(f"App installation failed: {error_msg}")
                return False, error_msg
                
        except Exception as e:
            debug_print(f"Error during app installation: {e}")
            # Try to install without progress dialog as fallback
            try:
                debug_print("Attempting installation without progress dialog...")
                success, stdout, stderr = self.run_adb_command(f"install -r \"{app_path}\"")
                if success:
                    debug_print(f"App installed successfully (fallback): {app_path}")
                    return True, None
                else:
                    error_msg = stderr.strip() if stderr else stdout.strip()
                    # Provide more user-friendly error messages for fallback too
                    if "no devices/emulators found" in error_msg.lower():
                        user_friendly_error = "No device connected via ADB"
                    elif "device offline" in error_msg.lower():
                        user_friendly_error = "Device is offline"
                    elif "unauthorized" in error_msg.lower():
                        user_friendly_error = "Device not authorized"
                    else:
                        user_friendly_error = error_msg
                    
                    debug_print(f"App installation failed (fallback): {error_msg}")
                    return False, error_msg
            except Exception as fallback_error:
                debug_print(f"Fallback installation also failed: {fallback_error}")
                return False, str(fallback_error)
        finally:
            # Always clean up progress dialog
            if progress_dialog:
                try:
                    if progress_dialog.winfo_exists():
                        progress_dialog.destroy()
                except Exception as e:
                    debug_print(f"Error destroying progress dialog: {e}")
    
    def _update_widget_tree(self, widget):
        """Recursively update widget colors"""
        try:
            # Update widget background and foreground
            if hasattr(widget, 'configure'):
                widget.configure(bg=self.bg_color, fg=self.fg_color)
            
            # Update specific widget types
            if isinstance(widget, tk.Label):
                widget.configure(bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9))
            elif isinstance(widget, tk.Button):
                widget.configure(bg=self.button_bg, fg=self.button_fg, 
                               activebackground=self.button_active_bg, 
                               activeforeground=self.button_active_fg,
                               font=("Segoe UI", 9), relief="flat", bd=1)
            elif isinstance(widget, tk.Checkbutton):
                widget.configure(bg=self.bg_color, fg=self.fg_color, 
                               selectcolor=self.bg_color, font=("Segoe UI", 9))
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=self.bg_color, relief="flat", bd=0)
            elif isinstance(widget, tk.LabelFrame):
                widget.configure(bg=self.bg_color, fg=self.fg_color, 
                               font=("Segoe UI", 9, "bold"), relief="flat", bd=1)
            
            # Recursively update children
            for child in widget.winfo_children():
                self._update_widget_tree(child)
                
        except Exception as e:
            debug_print(f"Failed to update widget {widget}: {e}")
    
    def apply_menu_colors(self):
        """Apply theme colors to all menus"""
        debug_print("Applying menu colors")
        try:
            # Configure menu colors
            menu_config = {
                'bg': self.menu_bg,
                'fg': self.menu_fg,
                'activebackground': self.menu_select_bg,
                'activeforeground': self.menu_select_fg,
                'selectcolor': self.menu_bg,
                'relief': 'flat',
                'bd': 0
            }
            
            # Apply to all existing menus
            if hasattr(self, 'device_menu'):
                self.device_menu.configure(**menu_config)
            if hasattr(self, 'apps_menu'):
                self.apps_menu.configure(**menu_config)
            if hasattr(self, 'debug_menu'):
                self.debug_menu.configure(**menu_config)
            if hasattr(self, 'help_menu'):
                self.help_menu.configure(**menu_config)
            if hasattr(self, 'context_menu'):
                self.context_menu.configure(**menu_config)
            
            # Apply to menubar and all its children
            if hasattr(self, 'menubar'):
                self.menubar.configure(**menu_config)
                # Apply to all cascade menus
                for i in range(self.menubar.index('end') + 1):
                    try:
                        menu = self.menubar.entrycget(i, 'menu')
                        if menu:
                            menu.configure(**menu_config)
                    except:
                        pass
            
            debug_print("Menu colors applied")
        except Exception as e:
            debug_print(f"Failed to apply menu colors: {e}")
    
    def setup_theme_change_detection(self):
        """Setup periodic theme change detection"""
        def check_theme_change():
            try:
                new_dark_mode = self.detect_system_theme()
                if new_dark_mode != self.is_dark_mode:
                    debug_print(f"System theme changed from {'dark' if self.is_dark_mode else 'light'} to {'dark' if new_dark_mode else 'light'}")
                    self.is_dark_mode = new_dark_mode
                    self.apply_theme_colors()
                    self.update_controls_display()
            except Exception as e:
                debug_print(f"Theme change detection error: {e}")
            
            # Check again in 5 seconds
            self.after(5000, check_theme_change)
        
        # Start theme change detection
        self.after(5000, check_theme_change)
    
    def get_adb_path(self):
        """Get ADB executable path from assets directory"""
        debug_print("Getting ADB path")
        if platform.system() == "Windows":
            adb_path = os.path.join(assets_dir, "adb.exe")
        else:
            adb_path = os.path.join(assets_dir, "adb")
        if os.path.exists(adb_path):
            debug_print(f"Found ADB at: {os.path.abspath(adb_path)}")
            return adb_path
        debug_print(f"ADB not found at {adb_path}")
        return adb_path  # Return the expected path anyway
    
    def setup_ui(self):
        # Main frame with modern styling
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Screen viewer frame with modern styling
        screen_frame = ttk.LabelFrame(main_frame, text="Mouse Input Panel (480x360)", padding=8)
        screen_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        
        # Create canvas for screen display (scaled down to 75%) with modern styling
        self.screen_canvas = tk.Canvas(screen_frame, width=self.display_width, height=self.display_height, 
                                     bg='black', cursor='hand2', highlightthickness=0, bd=0,
                                     relief="flat")
        self.screen_canvas.pack()
        self.screen_canvas.config(width=self.display_width, height=self.display_height)
        
        # Create controls display frame with modern styling
        self.controls_frame = ttk.LabelFrame(screen_frame, text="Controls", padding=6)
        self.controls_frame.pack(fill=tk.X, pady=(8, 0))
        
        # Controls display label with compact font
        self.controls_label = ttk.Label(self.controls_frame, text="", justify=tk.LEFT, 
                                       font=("Segoe UI", 8))
        self.controls_label.pack(anchor="w")
        
        # Mode selection frame with reduced padding - now taller with two rows
        mode_frame = ttk.Frame(self.controls_frame)
        mode_frame.pack(fill=tk.X, pady=(6, 0))
        
        # First row - Main controls (now with multiple rows)
        main_controls_frame = ttk.Frame(mode_frame)
        main_controls_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Row 1 - Primary controls
        row1_frame = ttk.Frame(main_controls_frame)
        row1_frame.pack(fill=tk.X, pady=(0, 6))
        
        # Input Mode toggle button with modern styling
        self.input_mode_btn = ttk.Button(
            row1_frame,
            text="Touch Screen Mode",
            command=self.toggle_scroll_wheel_mode,
            style="TButton"
        )
        self.input_mode_btn.pack(side=tk.LEFT, anchor="w")
        
        # Set Time button with modern styling
        self.set_time_btn = ttk.Button(
            row1_frame,
            text="Set Time",
            command=self.sync_device_time,
            style="TButton"
        )
        self.set_time_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Install Firmware button with modern styling
        self.install_firmware_btn = ttk.Button(
            row1_frame,
            text="Install Firmware",
            command=self.install_firmware,
            style="TButton"
        )
        self.install_firmware_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Screenshot button with modern styling
        self.screenshot_btn = ttk.Button(
            row1_frame,
            text="Screenshot",
            command=self.take_screenshot,
            style="TButton"
        )
        self.screenshot_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Update Available button (hidden by default, shown when update is available)
        self.update_btn = ttk.Button(
            row1_frame,
            text="Update Available",
            command=self.check_and_show_update,
            style="TButton"
        )
        self.update_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        self.update_btn.pack_forget()  # Hidden by default
        
        # Update pill will be positioned in bottom right corner later
        
        # Row 2 - Navigation controls
        row2_frame = ttk.Frame(main_controls_frame)
        row2_frame.pack(fill=tk.X, pady=(6, 0))
        
        # Navigation buttons
        self.home_btn = ttk.Button(
            row2_frame,
            text="Home",
            command=self.go_home,
            style="TButton"
        )
        self.home_btn.pack(side=tk.LEFT, anchor="w")
        
        self.back_btn = ttk.Button(
            row2_frame,
            text="Back",
            command=self.send_back_key,
            style="TButton"
        )
        self.back_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Additional navigation buttons
        self.recent_btn = ttk.Button(
            row2_frame,
            text="Recent",
            command=self.show_recent_apps,
            style="TButton"
        )
        self.recent_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        self.menu_btn = ttk.Button(
            row2_frame,
            text="Menu",
            command=self.nav_center,
            style="TButton"
        )
        self.menu_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Invert Scroll Direction checkbox with modern styling
        self.disable_swap_checkbox = ttk.Checkbutton(
            row2_frame,
            text="Invert Scroll Direction",
            variable=self.disable_dpad_swap_var,
            command=self.update_controls_display,
            style="TCheckbutton"
        )
        self.disable_swap_checkbox.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        self.disable_swap_checkbox.pack_forget()  # Hidden by default
        
        # Second row - D-pad controls
        dpad_frame = ttk.Frame(mode_frame)
        dpad_frame.pack(fill=tk.X, pady=(8, 0))
        
        # D-pad label
        dpad_label = ttk.Label(dpad_frame, text="D-pad Controls:", font=("Segoe UI", 9, "bold"))
        dpad_label.pack(side=tk.LEFT, anchor="w")
        
        # D-pad buttons in a cross layout
        dpad_buttons_frame = ttk.Frame(dpad_frame)
        dpad_buttons_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        # Up button
        self.dpad_up_btn = ttk.Button(
            dpad_buttons_frame,
            text="Up",
            command=self.nav_up,
            style="TButton",
            width=8
        )
        self.dpad_up_btn.pack()
        
        # Middle row with left, center, right buttons
        middle_row = ttk.Frame(dpad_buttons_frame)
        middle_row.pack()
        
        self.dpad_left_btn = ttk.Button(
            middle_row,
            text="Left",command=self.nav_left,
            style="TButton",
            width=8
        )
        self.dpad_left_btn.pack(side=tk.LEFT)
        
        self.dpad_center_btn = ttk.Button(
            middle_row,
            text="OK",command=self.nav_center,
            style="TButton",
            width=8
        )
        self.dpad_center_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        self.dpad_right_btn = ttk.Button(
            middle_row,
            text="Right",command=self.nav_right,
            style="TButton",
            width=8
        )
        self.dpad_right_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        # Down button
        self.dpad_down_btn = ttk.Button(dpad_buttons_frame,text="Down",
            command=self.nav_down,
            style="TButton",
            width=8
        )
        self.dpad_down_btn.pack()
        
        # Update pill underneath dpad controls
        self.update_pill = tk.Label(
            dpad_buttons_frame,
            text="Y1 Helper Update Available",
            bg="#0078D4",  # Windows blue
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2"
        )
        self.update_pill.pack(pady=(10, 0))
        self.update_pill.pack_forget()  # Hidden by default
        self.update_pill.bind("<Button-1>", self.show_update_choice_dialog)
        
        # Add tooltips with modern styling
        self._add_tooltip(self.input_mode_btn, (
            "Input Mode: Click to switch between Touch Screen Mode and Scroll Wheel Mode. "
            "Scroll Wheel Mode remaps controls to match the Y1's unique scroll wheel interface. "
            "Up/Down become Left/Right, just like scrolling through a classic iPod menu. "
            "Perfect for Y1-optimised apps!"
        ))
        
        self._add_tooltip(self.screenshot_btn, (
            "Screenshot: Capture the current device screen and save it to a file. "
            "You can choose the save location and filename. "
            "Requires device to be connected."
        ))
        
        self._add_tooltip(self.disable_swap_checkbox, (
            "When checked, inverts the scroll direction in Scroll Wheel Mode. "
            "Use this for apps that expect the opposite scroll behavior."
        ))
        
        self._add_tooltip(self.set_time_btn, (
            "Set Time: Synchronize the device's time with your computer's current time. "
            "This ensures the device has the correct date and time for proper operation."
        ))
        
        self._add_tooltip(self.update_btn, (
            "Update Available: A newer version of Y1 Helper is available for download. "
            "Click to download and install the latest version with bug fixes and improvements."
        ))
        
        self._add_tooltip(self.install_firmware_btn, (
            "Install Firmware: Download and install the latest firmware for your Y1 device. "
            "This updates the device's operating system to the newest version with bug fixes and improvements."
        ))
        
        # Add tooltips for D-pad buttons
        self._add_tooltip(self.dpad_up_btn, (
            "D-pad Up: Navigate up in the current app or menu. "
            "Works in any input mode and sends ADB commands to the device."
        ))
        
        self._add_tooltip(self.dpad_down_btn, (
            "D-pad Down: Navigate down in the current app or menu. "
            "Works in any input mode and sends ADB commands to the device."
        ))
        
        self._add_tooltip(self.dpad_left_btn, (
            "D-pad Left: Navigate left in the current app or menu. "
            "Works in any input mode and sends ADB commands to the device."
        ))
        
        self._add_tooltip(self.dpad_right_btn, (
            "D-pad Right: Navigate right in the current app or menu. "
            "Works in any input mode and sends ADB commands to the device."
        ))
        
        self._add_tooltip(self.dpad_center_btn, (
            "D-pad Center: Select or confirm the current item. "
            "Works in any input mode and sends ADB commands to the device."
        ))
        
        # Status bar at bottom with modern styling
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(12, 0))
        
        # Modern status label with flat styling
        status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                relief="flat", borderwidth=1, padding=(8, 4),
                                font=("Segoe UI", 9))
        status_label.pack(fill=tk.X, side=tk.LEFT, expand=True)
        

        

        
        # Force focus to canvas after window is ready
        self.after(100, lambda: self.screen_canvas.focus_set())
        
        # Mouse click bindings
        self.screen_canvas.bind("<Button-1>", self.on_screen_click)       # Left click
        self.screen_canvas.bind("<Button-3>", self.on_screen_right_click) # Right click
        self.screen_canvas.bind("<Button-2>", self.on_mouse_wheel_click)  # Middle click (wheel click)
        self.screen_canvas.bind("<ButtonRelease-1>", self.on_nav_bar_click)
        
        # Mouse wheel bindings
        self.screen_canvas.bind("<MouseWheel>", self.on_mouse_wheel)      # Windows/macOS
        self.screen_canvas.bind("<Button-4>", self.on_mouse_wheel)        # Linux scroll up
        self.screen_canvas.bind("<Button-5>", self.on_mouse_wheel)        # Linux scroll down
        # Mouse wheel release bindings for cursor control
        self.screen_canvas.bind("<ButtonRelease-4>", self.on_mouse_wheel_release)  # Linux scroll up release
        self.screen_canvas.bind("<ButtonRelease-5>", self.on_mouse_wheel_release)  # Linux scroll down release
        
        # Initialize controls display
        self.update_controls_display()
        
        # Navigation buttons (no virtual nav bar)
        self.nav_bar_height = 0  # No virtual nav bar
        
        # Context menu with modern styling
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Go Home", command=self.go_home)
        self.context_menu.add_command(label="Open Settings", command=self.launch_settings)
        self.context_menu.add_command(label="Recent Apps", command=self.show_recent_apps)
        
        # Controls frame is always visible now - no longer hidden based on device connection
        # self.hide_controls_frame()  # Removed - controls should always be visible
        
        # Flag to track if input should be disabled (when showing ready.png)
        self.input_disabled = True
        
        # Mouse wheel bindings for Linux
        self.screen_canvas.bind("<Button-4>", self.on_mouse_wheel)        # Linux scroll up
        self.screen_canvas.bind("<Button-5>", self.on_mouse_wheel)        # Linux scroll down
        # Mouse wheel release bindings for cursor control
        self.screen_canvas.bind("<ButtonRelease-4>", self.on_mouse_wheel_release)  # Linux scroll up release
        self.screen_canvas.bind("<ButtonRelease-5>", self.on_mouse_wheel_release)  # Linux scroll down release
        
        # Controls are always visible regardless of device connection\n        \n
    
    def hide_controls_frame(self):
        """Hide the controls frame when no device is connected"""
        # Controls frame is always visible now, so this is a no-op
        # if hasattr(self, 'controls_frame'):
        #     self.controls_frame.pack_forget()
        debug_print("Controls frame is always visible - no need to hide")
    
    def show_controls_frame(self):
        """Show the controls frame when device is connected"""
        # Controls frame is always visible now, so this is a no-op
        # if hasattr(self, 'controls_frame'):
        #     self.controls_frame.pack(fill=tk.X, pady=(5, 0))
        debug_print("Controls frame is always visible - no need to show")
    
    def disable_input_bindings(self):
        """Disable all input bindings when device is disconnected"""
        if hasattr(self, 'screen_canvas'):
            # Unbind mouse events
            self.screen_canvas.unbind("<Button-1>")
            self.screen_canvas.unbind("<Button-3>")
            self.screen_canvas.unbind("<MouseWheel>")
            self.screen_canvas.unbind("<Button-2>")
            self.screen_canvas.unbind("<ButtonRelease-2>")
            
            # Unbind global key events
            self.unbind_all("<Key>")
            self.unbind_all("<KeyRelease>")
            
            # Keep Alt key bindings for launcher control toggle
            self.bind("<Alt_L>", self.toggle_launcher_control)
            self.bind("<Alt_R>", self.toggle_launcher_control)
            
            self.input_disabled = True
            debug_print("Input bindings disabled - device disconnected")
    
    def enable_input_bindings(self):
        """Enable all input bindings when device is connected"""
        if hasattr(self, 'screen_canvas'):
            # Rebind mouse events
            self.screen_canvas.bind("<Button-1>", self.on_screen_click)       # Left click
            self.screen_canvas.bind("<Button-3>", self.on_screen_right_click) # Right click
            self.screen_canvas.bind("<MouseWheel>", self.on_mouse_wheel)      # Windows/macOS
            self.screen_canvas.bind("<Button-2>", self.on_mouse_wheel_click)  # Middle click
            self.screen_canvas.bind("<ButtonRelease-2>", self.on_mouse_wheel_release)  # Middle click release
            
            # Rebind global key events
            self.bind_all("<Key>", self.on_key_press)
            self.bind_all("<KeyRelease>", self.on_key_release)
            
            self.input_disabled = False
            # Flag to track if ready placeholder is being displayed
            self.ready_placeholder_shown = False
            debug_print("Input bindings enabled - device connected")
    
    def update_controls_display(self):
        """Update the controls display based on current mode"""
        debug_print("Updating controls display")
        
        if self.scroll_wheel_mode_var.get():
            # Scroll Wheel Mode controls - compact version
            if self.disable_dpad_swap_var.get() or self.y1_launcher_detected:
                # Inverted scroll direction - show inverted mapping
                controls_text = (
                    "Scroll Wheel Mode (Inverted):\n"
                    "Touch: Left Click | Back: Right Click\n"
                    "Scroll: W/S or Up/Down Arrows sends DPAD_RIGHT/DPAD_LEFT\n"
                    "D-pad: A/D or Left/Right Arrows sends DPAD_UP/DPAD_DOWN\n"
                    "Enter: Wheel Click, Enter, E sends ENTER\n"
                    "Toggle: Alt"
                )
            else:
                # Normal scroll direction - show normal mapping
                controls_text = (
                    "Scroll Wheel Mode:\n"
                    "Touch: Left Click | Back: Right Click\n"
                    "Scroll: W/S or Up/Down Arrows sends DPAD_UP/DPAD_DOWN\n"
                    "D-pad: A/D or Left/Right Arrows sends DPAD_LEFT/DPAD_RIGHT\n"
                    "Enter: Wheel Click, Enter, E sends ENTER\n"
                    "Toggle: Alt"
                )
        else:
            # Touch Screen Mode controls - compact version
            controls_text = (
                "Touch Screen Mode:\n"
                "Touch: Left Click | Back: Right Click\n"
                "D-pad: W/A/S/D or Arrow Keys sends DPAD_UP/DPAD_LEFT/DPAD_DOWN/DPAD_RIGHT\n"
                "Enter: Wheel Click, Enter, E sends DPAD_CENTER\n"
                "Toggle: Alt"
            )
        
        self.controls_label.config(text=controls_text)
        debug_print(f"Controls display updated - Y1 launcher detected: {self.y1_launcher_detected}, Invert checkbox: {self.disable_dpad_swap_var.get()}")
    
    def toggle_scroll_wheel_mode(self):
        """Toggle between Scroll Wheel Mode and Touch Screen Mode"""
        debug_print("Toggling scroll wheel mode")
        is_scroll_wheel_mode = not self.scroll_wheel_mode_var.get()  # Toggle the value
        self.scroll_wheel_mode_var.set(is_scroll_wheel_mode)
        
        # Sync the control_launcher variable with scroll wheel mode
        self.control_launcher = is_scroll_wheel_mode
        
        # Set manual override flag
        self.manual_mode_override = True
        self.last_manual_mode_change = time.time()
        debug_print("Manual mode override set")
        
        if is_scroll_wheel_mode:
            # Update button text to show current mode
            self.input_mode_btn.config(text="Scroll Wheel Mode")
            
            # Show the disable D-pad swap checkbox
            self.disable_swap_checkbox.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
            self.status_var.set("Scroll Wheel Mode enabled")
            debug_print("Scroll Wheel Mode enabled")
            
            # Keep regular cursor for scroll wheel mode (only if not showing ready placeholder)
            if not self.ready_placeholder_shown:
                self.screen_canvas.config(cursor="")
                debug_print("Cursor set to regular for Scroll Wheel Mode")
        else:
            # Update button text to show current mode
            self.input_mode_btn.config(text="Touch Screen Mode")
            
            # Hide the disable D-pad swap checkbox
            self.disable_swap_checkbox.pack_forget()
            self.status_var.set("Touch Screen Mode enabled")
            debug_print("Touch Screen Mode enabled")
            
            # Set cursor to pointing hand for touch screen mode (only if not showing ready placeholder)
            if not self.ready_placeholder_shown:
                self.screen_canvas.config(cursor="hand2")
                debug_print("Cursor set to pointing hand for Touch Screen Mode")
        
        # Update controls display
        self.update_controls_display()
    
    def toggle_launcher_control(self, event=None):
        """Toggle launcher control mode (legacy function for Alt key)"""
        debug_print("Toggling launcher control (Alt key)")
        self.scroll_wheel_mode_var.set(not self.scroll_wheel_mode_var.get())
        self.toggle_scroll_wheel_mode()
    
    def toggle_launcher_control_legacy(self, event=None):
        """Legacy toggle function - now redirects to new system"""
        self.toggle_launcher_control(event)
    
    def setup_menu(self):
        menubar = Menu(self)
        self.config(menu=menubar)
        self.menubar = menubar  # Store reference for theme application
        device_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Device", menu=device_menu)
        self.device_menu = device_menu
        
        # Add standard device menu items
        self.device_menu.add_command(label="Device Info", command=self.show_device_info)
        self.device_menu.add_command(label="ADB Shell", command=self.open_adb_shell)
        # File Explorer is hidden from menu but accessible via Ctrl+F
        # self.device_menu.add_command(label="File Explorer", command=self.open_file_explorer)
        self.device_menu.add_command(label="Take Screenshot", command=self.take_screenshot)
        self.device_menu.add_command(label="Recent Apps", command=self.show_recent_apps)
        self.device_menu.add_command(label="Change Device Language", command=self.change_device_language)
        self.device_menu.add_command(label="Sync Device Time", command=self.sync_device_time)
        self.device_menu.add_separator()
        self.device_menu.add_command(label="Install Firmware", command=self.install_firmware)
        # self.device_menu.add_command(label="Repair Device", command=self.repair_device)  # Removed
        self.device_menu.add_separator()
        self.device_menu.add_command(label="Rockbox Utility", command=self.launch_rockbox_utility)
        self.device_menu.add_command(label="SP Flash Tool", command=self.launch_sp_flash_tool)
        self.device_menu.add_separator()
        self.device_menu.add_command(label="Restart Device", command=self.restart_device)
        
        self.apps_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Apps", menu=self.apps_menu)
        self.apps_menu.add_command(label="Browse APKs...", command=self.browse_apks)
        self.apps_menu.add_command(label="Install Apps", command=self.install_apps)
        self.apps_menu.add_separator()
        self.refresh_apps()  # Populate on startup
        
        # Debug menu (hidden by default, shown with Ctrl+D)
        self.debug_menu = Menu(menubar, tearoff=0)
        self.debug_menu.add_command(label="Change Update Branch...", command=self.change_update_branch)
        self.debug_menu.add_command(label="Show Current Branch", command=self.show_current_branch)
        self.debug_menu.add_separator()
        self.debug_menu.add_command(label="Run Updater", command=self.run_updater)
        
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="Reinstall App", command=self.menu_reinstall_app)
        help_menu.add_command(label="Update App", command=self.menu_update_app)
        help_menu.add_separator()
        help_menu.add_command(label="Run Older Version", command=self.launch_old_version)
        help_menu.add_separator()
        help_menu.add_command(label="r/innioasis", command=lambda: webbrowser.open_new_tab("https://www.reddit.com/r/innioasis"))
        help_menu.add_command(label="Project Gallagher Discord", command=lambda: webbrowser.open_new_tab("https://discord.gg/nAeFsqDB"))
        help_menu.add_separator()
        help_menu.add_command(label="Become a Patron", command=lambda: webbrowser.open_new_tab("https://www.patreon.com/c/TeamSlide"))
        menubar.add_cascade(label="Help", menu=help_menu)
        self.help_menu = help_menu  # Store reference for theme application
        
        # Store reference to help menu for dynamic label updates
        self.help_menu_label = "Help"
        self.help_menu_index = len(menubar.winfo_children()) - 1  # Index of Help menu in menubar
        self.update_app_index = 1  # Update App is now at index 1
        self.reinstall_app_index = 0  # Reinstall App is now at index 0
        
        # Bind menu click event to handle update available clicks
        self.bind("<<MenuSelect>>", self.on_menu_select)
        
        # Bind Apps menu events to track user interaction
        self.apps_menu.bind("<<MenuSelect>>", self.on_apps_menu_select)
        self.apps_menu.bind("<Leave>", self.on_apps_menu_leave)
        
        # Apply theme colors after all menus are created
        self.apply_menu_colors()
    

    
    def refresh_apps(self):
        """Refresh list of installed apps (Apps menu only)"""
        # Skip refresh if user is actively interacting with the Apps menu
        if self.apps_menu_active:
            debug_print("Skipping apps refresh - user is actively using Apps menu")
            return
        
        # Use threading to prevent UI blocking
        def refresh_apps_thread():
            try:
                debug_print("Refreshing apps list in background")
                
                # Get user-installed apps with shorter timeout
                success_user, stdout_user, stderr_user = self.run_adb_command(
                    "shell pm list packages -3 -f", timeout=5)
                user_apps = []
                
                # Get system apps with shorter timeout
                success_system, stdout_system, stderr_system = self.run_adb_command(
                    "shell pm list packages -s -f", timeout=5)
                system_apps = []
                
                # Parse user apps
                if success_user:
                    debug_print(f"Found {len(stdout_user.strip().split('\n'))} user package lines")
                    for line in stdout_user.strip().split('\n'):
                        if line.startswith('package:'):
                            if '=' in line:
                                package_name = line.split('=')[1]
                            else:
                                package_name = line[len('package:'):]
                            if package_name and package_name.strip():
                                user_apps.append(package_name)
                
                # Parse system apps
                if success_system:
                    debug_print(f"Found {len(stdout_system.strip().split('\n'))} system package lines")
                    for line in stdout_system.strip().split('\n'):
                        if line.startswith('package:'):
                            if '=' in line:
                                package_name = line.split('=')[1]
                            else:
                                package_name = line[len('package:'):]
                            if package_name and package_name.strip():
                                system_apps.append(package_name)
                
                # Remove duplicates (system apps might also appear in user apps list)
                user_apps = list(set(user_apps))
                system_apps = list(set(system_apps))
                
                debug_print(f"Found {len(user_apps)} user apps and {len(system_apps)} system apps")
                
                # Update UI in main thread
                self.after(0, lambda: self._update_apps_menu(user_apps, system_apps))
                
            except Exception as e:
                debug_print(f"Error refreshing apps: {e}")
        
        # Start the background thread
        import threading
        thread = threading.Thread(target=refresh_apps_thread, daemon=True)
        thread.start()
    
    def _update_apps_menu(self, user_apps, system_apps):
        """Update the apps menu with the provided app lists (called in main thread)"""
        try:
            self.apps_menu.delete(0, tk.END)
            self.apps_menu.add_command(label="Browse APKs...", command=self.browse_apks)
            self.apps_menu.add_command(label="Install Apps", command=self.install_apps)
            self.apps_menu.add_separator()
            
            # Add User Apps submenu
            if user_apps:
                user_apps_menu = Menu(self.apps_menu, tearoff=0)
                for app in sorted(user_apps):
                    app_menu = Menu(user_apps_menu, tearoff=0)
                    app_menu.add_command(label="Launch", command=lambda a=app: self.launch_app(a))
                    app_menu.add_command(label="Uninstall", command=lambda a=app: self.uninstall_app(a))
                    
                    # Add restart option for Rockbox
                    if app == "org.rockbox":
                        app_menu.add_separator()
                        app_menu.add_command(label="Restart Rockbox", command=self.restart_rockbox)
                    
                    user_apps_menu.add_cascade(label=app, menu=app_menu)
                    
                    # Apply theme colors to new app menu
                    if hasattr(self, 'menu_bg'):
                        app_menu.configure(
                            bg=self.menu_bg,
                            fg=self.menu_fg,
                            activebackground=self.menu_select_bg,
                            activeforeground=self.menu_select_fg,
                            selectcolor=self.menu_bg,
                            relief='flat',
                            bd=0
                        )
                
                # Apply theme colors to user apps submenu
                if hasattr(self, 'menu_bg'):
                    user_apps_menu.configure(
                        bg=self.menu_bg,
                        fg=self.menu_fg,
                        activebackground=self.menu_select_bg,
                        activeforeground=self.menu_select_fg,
                        selectcolor=self.menu_bg,
                        relief='flat',
                        bd=0
                    )
                
                self.apps_menu.add_cascade(label=f"User Apps ({len(user_apps)})", menu=user_apps_menu)
            else:
                self.apps_menu.add_command(label="No user apps installed", state="disabled")
            
            # Add System Apps submenu
            if system_apps:
                system_apps_menu = Menu(self.apps_menu, tearoff=0)
                for app in sorted(system_apps):
                    app_menu = Menu(system_apps_menu, tearoff=0)
                    app_menu.add_command(label="Launch", command=lambda a=app: self.launch_app(a))
                    # Don't allow uninstall for system apps
                    app_menu.add_command(label="Uninstall", command=lambda a=app: self.uninstall_app(a), state="disabled")
                    system_apps_menu.add_cascade(label=app, menu=app_menu)
                    
                    # Apply theme colors to new app menu
                    if hasattr(self, 'menu_bg'):
                        app_menu.configure(
                            bg=self.menu_bg,
                            fg=self.menu_fg,
                            activebackground=self.menu_select_bg,
                            activeforeground=self.menu_select_fg,
                            selectcolor=self.menu_bg,
                            relief='flat',
                            bd=0
                        )
                
                # Apply theme colors to system apps submenu
                if hasattr(self, 'menu_bg'):
                    system_apps_menu.configure(
                        bg=self.menu_bg,
                        fg=self.menu_fg,
                        activebackground=self.menu_select_bg,
                        activeforeground=self.menu_select_fg,
                        selectcolor=self.menu_bg,
                        relief='flat',
                        bd=0
                    )
                
                self.apps_menu.add_cascade(label=f"System Apps ({len(system_apps)})", menu=system_apps_menu)
            else:
                self.apps_menu.add_command(label="No system apps found", state="disabled")
            
            debug_print(f"Added {len(user_apps)} user apps and {len(system_apps)} system apps to menu")
            
        except Exception as e:
            debug_print(f"Error updating apps menu: {e}")
    
    def unified_device_check(self):
        """Unified method to check device connection and refresh app list with enhanced robustness"""
        # Use thread lock to prevent race conditions, but with timeout to prevent hanging
        if not self.device_connection_lock.acquire(timeout=1.0):
            debug_print("Device check lock timeout, skipping this check")
            return
            
        try:
            adb_path = self.get_adb_path()
            current_time = time.time()
            
            # Check device connection with more robust parsing and shorter timeout
            result = subprocess.run([adb_path, "devices"], 
                                  capture_output=True, text=True, timeout=2)
            
            # More robust device detection - look for actual device lines
            device_lines = [line.strip() for line in result.stdout.strip().split('\n') 
                          if line.strip() and not line.startswith('List of devices')]
            
            device_found = False
            for line in device_lines:
                if line.endswith('device'):  # Only fully authorized devices
                    device_found = True
                    break
            
            if device_found:
                # Device appears to be connected, validate it's actually responsive
                if current_time - self.last_device_validation > self.device_validation_interval:
                    if self.validate_device_connection():
                        self.device_check_failures = 0  # Reset failure counter
                        self.consecutive_framebuffer_failures = 0  # Reset framebuffer failures
                        self.last_device_validation = current_time
                        
                        if not self.device_connected:
                            # Device just reconnected
                            self.device_connected = True
                            self.status_var.set("Device connected")
                            
                            # Show controls frame and enable input bindings when device connects
                            self.show_controls_frame()
                            self.enable_input_bindings()
                            
                            # Set device to stay awake
                            self.set_device_stay_awake()
                        
                        # Schedule app refresh instead of calling directly to prevent blocking
                        if not self.apps_menu_active:
                            self.after(100, self.refresh_apps)
                    else:
                        # Device detected but not responsive
                        self.device_check_failures += 1
                        
                        if self.device_check_failures >= self.max_device_check_failures:
                            if self.device_connected:
                                self.device_connected = False
                                self.status_var.set("Device disconnected - not responsive")
                                
                                # Disable input bindings but keep controls frame visible
                                self.disable_input_bindings()
                else:
                    # Skip validation this time, but ensure device is marked as connected if it was before
                    if not self.device_connected:
                        self.device_connected = True
                        self.status_var.set("Device connected")
                        
                        # Show controls frame and enable input bindings
                        self.show_controls_frame()
                        self.enable_input_bindings()
                        
                        # Set device to stay awake
                        self.set_device_stay_awake()
                    
                    # Schedule app refresh instead of calling directly
                    if not self.apps_menu_active:
                        self.after(100, self.refresh_apps)
                    
            else:
                # No device found
                self.device_check_failures += 1
                
                if self.device_connected or self.device_check_failures >= self.max_device_check_failures:
                    self.device_connected = False
                    self.status_var.set("First time? Install a Firmware from the Device Menu.")
                    
                    # Disable input bindings but keep controls frame visible
                    self.disable_input_bindings()
                
            self.last_device_check_time = current_time
                
        except subprocess.TimeoutExpired:
            debug_print("ADB devices command timed out")
            self.device_check_failures += 1
        except Exception as e:
            debug_print(f"Device check error: {e}")
            self.device_check_failures += 1
            
            if self.device_connected or self.device_check_failures >= self.max_device_check_failures:
                self.device_connected = False
                self.status_var.set("First time? Install a Firmware from the Device Menu.")
                self.disable_input_bindings()
        finally:
            self.device_connection_lock.release()
        
        # Check if firmware flashing is in progress
        if getattr(self, 'is_flashing_firmware', False):
            return
    
    def detect_current_app(self):
        """Detect currently running app and set launcher control accordingly"""
        debug_print("Detecting current app")
        
        # Don't detect app if device is not connected
        if not self.device_connected:
            debug_print("Device not connected, skipping app detection")
            return
            
        try:
            # Get the currently focused activity
            success, stdout, stderr = self.run_adb_command("shell dumpsys activity activities | grep mResumedActivity")
            detected_package = None
            if success and stdout:
                debug_print(f"Activity dump output: {stdout.strip()}")
                for line in stdout.strip().split('\n'):
                    if 'mResumedActivity' in line:
                        # Extract package name (regex for package/activity)
                        import re
                        match = re.search(r' ([a-zA-Z0-9_.]+)/(\S+)', line)
                        if match:
                            detected_package = match.group(1)
                            debug_print(f"Detected package from activity: {detected_package}")
                        break
            if not detected_package:
                debug_print("No package detected from activity, trying window focus")
                # Fallback: try alternative method
                success, stdout, stderr = self.run_adb_command("shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'")
                if success and stdout:
                    debug_print(f"Window focus output: {stdout.strip()}")
                    for line in stdout.strip().split('\n'):
                        import re
                        match = re.search(r' ([a-zA-Z0-9_.]+)/(\S+)', line)
                        if match:
                            detected_package = match.group(1)
                            debug_print(f"Detected package from window focus: {detected_package}")
                        break
            # Update current_app and launcher control logic
            if detected_package:
                # Check if app has changed
                if self.current_app != detected_package:
                    self.current_app = detected_package
                    self.last_app_change = time.time()
                    debug_print(f"App changed to: {detected_package}, resetting app change timer")
                    
                    # Clear manual override when app changes on device (not from Y1 helper)
                    self.manual_mode_override = False
                    debug_print("Manual mode override cleared due to app change on device")
                else:
                    self.current_app = detected_package
                    debug_print(f"Current app: {detected_package}")
                
                # Always show the input mode button for any app
                self.input_mode_btn.pack(side=tk.LEFT, anchor="w")
                
                # Check if Y1 launcher is detected for scroll direction inversion
                self.y1_launcher_detected = (detected_package == "com.innioasis.y1")
                debug_print(f"Y1 launcher detected: {self.y1_launcher_detected}")
                
                # Update controls display to reflect new Y1 launcher detection
                self.update_controls_display()
                
                # Check if this is a Y1 app or Rockbox - auto-enable scroll wheel mode
                if self._should_auto_enable_scroll_wheel(detected_package):
                    # Only auto-enable if no manual override is active
                    if not self.manual_mode_override:
                        self.control_launcher = True
                        self.scroll_wheel_mode_var.set(True)
                        self.status_var.set("Scroll Wheel Mode automatically enabled for this app")
                        debug_print("Scroll Wheel Mode automatically enabled for Y1/Rockbox app")
                        
                        # Update button text to show current mode
                        self.input_mode_btn.config(text="Scroll Wheel Mode")
                        
                        # Show the disable D-pad swap checkbox when auto-enabling scroll wheel mode
                        self.disable_swap_checkbox.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
                    else:
                        debug_print("Manual mode override active, not auto-enabling scroll wheel mode")
                        # Keep current mode but update UI
                        if self.scroll_wheel_mode_var.get():
                            self.input_mode_btn.config(text="Scroll Wheel Mode")
                            self.disable_swap_checkbox.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
                        else:
                            self.input_mode_btn.config(text="Touch Screen Mode")
                            self.disable_swap_checkbox.pack_forget()
                else:
                    # For other apps, keep the current state (user can manually toggle)
                    self.control_launcher = self.scroll_wheel_mode_var.get()
                    if self.control_launcher:
                        self.status_var.set("Scroll Wheel Mode manually enabled for this app")
                        debug_print("Scroll Wheel Mode manually enabled for non-Y1 app")
                        
                        # Update button text to show current mode
                        self.input_mode_btn.config(text="Scroll Wheel Mode")
                        
                        # Show the disable D-pad swap checkbox if scroll wheel mode is enabled
                        self.disable_swap_checkbox.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
                    else:
                        self.status_var.set("Scroll Wheel Mode available for this app")
                        debug_print("Scroll Wheel Mode available for non-Y1 app")
                        
                        # Update button text to show current mode
                        self.input_mode_btn.config(text="Touch Screen Mode")
                        
                        # Hide the disable D-pad swap checkbox if scroll wheel mode is disabled
                        self.disable_swap_checkbox.pack_forget()
                
                # Update controls display to reflect current mode
                self.update_controls_display()
                
                # Hide firmware installation menu for Y1 apps
                if self._should_show_launcher_toggle(detected_package):
                    self.hide_firmware_installation_menu()
            else:
                # App detection failed - keep toggle visible but revert to touch screen mode
                self.current_app = "unknown"
                self.control_launcher = False
                self.scroll_wheel_mode_var.set(False)
                
                # Keep the input mode button visible even when detection fails
                self.input_mode_btn.pack(side=tk.LEFT, anchor="w")
                
                # Hide the disable D-pad swap checkbox when reverting to touch screen mode
                self.disable_swap_checkbox.pack_forget()
                
                self.status_var.set("App detection failed - Touch Screen Mode active")
                debug_print("App detection failed, keeping toggle visible but reverting to Touch Screen Mode")
                
                # Update controls display to reflect touch screen mode
                self.update_controls_display()
        except Exception as e:
            debug_print(f"Error detecting current app: {e}")
            self.current_app = "unknown"
            self.control_launcher = False
            self.scroll_wheel_mode_var.set(False)
            
            # Keep the input mode button visible even on error
            self.input_mode_btn.pack(side=tk.LEFT, anchor="w")
            
            # Hide the disable D-pad swap checkbox on error
            self.disable_swap_checkbox.pack_forget()
            
            self.status_var.set("App detection error - Touch Screen Mode active")
            debug_print("App detection error, keeping toggle visible but reverting to Touch Screen Mode")
            
            # Update controls display to reflect touch screen mode
            self.update_controls_display()
        
        # Schedule next check using unified interval if app is still running
        if hasattr(self, 'is_capturing') and self.is_capturing:
            self.after(self.unified_check_interval * 1000, self.detect_current_app)
    

    
    def check_device_prepared(self):
        """Check if device has stock launcher installed (installed only, not running)"""
        success, stdout, stderr = self.run_adb_command("shell pm list packages com.innioasis.y1")
        if not success:
            self.device_prepared = None  # Unknown, don't prompt
            return None
        if "com.innioasis.y1" in stdout:
            self.device_prepared = True
            return True
        else:
            self.device_prepared = False
            return False
    
    def show_unprepared_device_prompt(self):
        """Show prompt for unprepared device"""
        result = messagebox.askyesno("Unprepared Device Detected", 
                                   "This Y1 device does not have the stock launcher installed.\n\n"
                                   "The device appears to be running a factory testing OS image.\n\n"
                                   "Would you like to prepare the device by installing the stock Y1 launcher?\n\n"
                                   "This will allow you to:\n"
                                   "� Start developing Y1 apps targeting Android API Level 16\n"
                                   "� Test apps on real hardware with the correct display and input setup\n"
                                   "� Use the full Y1 Helper functionality")
        if result:
            self.install_firmware()
    
    def validate_device_connection(self):
        """Validate that the detected device is actually responsive and accessible"""
        try:
            # Test basic device responsiveness with a simple command
            success, stdout, stderr = self.run_adb_command("shell echo 'test'", timeout=2)
            if not success:
                return False
            
            # Test if we can get device properties (more comprehensive check)
            success, stdout, stderr = self.run_adb_command("shell getprop ro.product.model", timeout=2)
            if not success or not stdout.strip():
                return False
            
            # Test if we can access the framebuffer (critical for screen capture)
            success, stdout, stderr = self.run_adb_command("shell ls /dev/graphics/fb0", timeout=2)
            if not success:
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def run_adb_command(self, command, timeout=10):
        """Run ADB command and return result"""
        debug_print(f"Running ADB command: {command}")
        try:
            adb_path = self.get_adb_path()
            
            # Handle commands with quoted paths properly
            if '"' in command:
                # For commands with quoted paths, use shell=True on Windows
                if platform.system() == "Windows":
                    full_command = f'"{adb_path}" {command}'
                    debug_print(f"Windows shell command: {full_command}")
                    result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=timeout)
                else:
                    # On Unix systems, split carefully
                    import shlex
                    full_command = [adb_path] + shlex.split(command)
                    debug_print(f"Unix command: {full_command}")
                    result = subprocess.run(full_command, capture_output=True, text=True, timeout=timeout)
            else:
                # Simple command splitting for non-path commands
                full_command = [adb_path] + command.split()
                debug_print(f"Simple command: {full_command}")
                result = subprocess.run(full_command, capture_output=True, text=True, timeout=timeout)
            
            success = result.returncode == 0
            debug_print(f"ADB command result: success={success}, stdout={len(result.stdout)} chars, stderr={len(result.stderr)} chars")
            if result.stderr:
                debug_print(f"ADB stderr: {result.stderr.strip()}")
            
            return success, result.stdout, result.stderr
        except Exception as e:
            debug_print(f"ADB command failed with exception: {e}")
            return False, "", str(e)
    
    def start_screen_capture(self):
        debug_print("Starting screen capture")
        if not self.capture_thread or not self.capture_thread.is_alive():
            self.is_capturing = True
            self.capture_thread = threading.Thread(target=self.capture_screen_loop, daemon=True)
            self.capture_thread.start()
            self.status_var.set("Screen capture started")
            debug_print("Screen capture thread started")
        else:
            debug_print("Screen capture already running")
    
    def capture_screen_loop(self):
        """Optimized screen capture loop with 1-second refresh rate"""
        import tempfile
        import os
        
        temp_dir = tempfile.gettempdir()
        fb_temp_path = os.path.join(temp_dir, "y1_fb0.tmp")
        placeholder_shown = False
        
        while self.is_capturing:
            try:
                current_time = time.time()
                
                # Periodically check device connection status
                if current_time - self.last_unified_check > self.unified_check_interval:
                    self.unified_device_check()
                    self.last_unified_check = current_time
                
                # Check if device is connected using thread-safe access
                with self.device_connection_lock:
                    device_connected = self.device_connected
                
                if not device_connected:
                    if not placeholder_shown:
                        self.safe_after(self, 0, self.show_ready_placeholder)
                        placeholder_shown = True
                        self.safe_after(self, 0, lambda: self.safe_ui_update(self.status_var, "set", "First time? Install a Firmware from the Device Menu."))
                        # Disable input bindings when device is disconnected
                        self.safe_after(self, 0, self.disable_input_bindings)
                    time.sleep(1)  # Check less frequently when disconnected
                    continue
                
                # Reset placeholder flag when device is connected
                if placeholder_shown:
                    placeholder_shown = False
                    self.safe_after(self, 0, lambda: self.safe_ui_update(self.status_var, "set", "Device connected"))
                    # Enable input bindings when device reconnects
                    self.safe_after(self, 0, self.enable_input_bindings)
                
                # Use consistent refresh interval for better performance
                refresh_interval = self.framebuffer_refresh_interval
                
                # Only pull framebuffer if enough time has passed or force refresh requested
                should_refresh = (
                    current_time - self.last_framebuffer_refresh > refresh_interval or
                    self.force_refresh_requested
                )
                
                if should_refresh:
                    # Skip framebuffer pull if input command is in progress to avoid interference
                    if self.input_command_in_progress:
                        time.sleep(0.1)
                        continue
                        
                    success, stdout, stderr = self.run_adb_command(f"pull /dev/graphics/fb0 \"{fb_temp_path}\"")
                    if success:
                        if os.path.exists(fb_temp_path):
                            self.process_framebuffer(fb_temp_path)
                            self.consecutive_framebuffer_failures = 0  # Reset failure counter on success
                            self.last_framebuffer_refresh = current_time
                            self.force_refresh_requested = False
                        else:
                            # Framebuffer pull succeeded but file doesn't exist
                            self.consecutive_framebuffer_failures += 1
                            if self.consecutive_framebuffer_failures >= self.max_framebuffer_failures:
                                if not placeholder_shown:
                                    self.safe_after(self, 0, self.show_ready_placeholder)
                                    placeholder_shown = True
                                    self.safe_after(self, 0, lambda: self.safe_ui_update(self.status_var, "set", "First time? Install a Firmware from the Device Menu."))
                            self.last_framebuffer_refresh = current_time
                            self.force_refresh_requested = False
                    else:
                        # Framebuffer pull failed
                        self.consecutive_framebuffer_failures += 1
                        if self.consecutive_framebuffer_failures >= self.max_framebuffer_failures:
                            if not placeholder_shown:
                                self.safe_after(self, 0, self.show_ready_placeholder)
                                placeholder_shown = True
                                self.safe_after(self, 0, lambda: self.safe_ui_update(self.status_var, "set", "First time? Install a Firmware from the Device Menu."))
                        time.sleep(0.5)
                else:
                    # Sleep when not refreshing to reduce CPU usage
                    time.sleep(0.1)
                    
            except Exception as e:
                if not placeholder_shown:
                    self.device_connected = False
                    self.safe_after(self, 0, self.show_ready_placeholder)
                    placeholder_shown = True
                    self.safe_after(self, 0, lambda: self.safe_ui_update(self.status_var, "set", "First time? Install a Firmware from the Device Menu."))
                time.sleep(0.5)
    
    def process_framebuffer(self, fb_path):
        """Process framebuffer data and display on canvas (optimized)"""
        try:
            if not os.path.exists(fb_path):
                debug_print("Framebuffer file does not exist")
                self.safe_after(self, 0, self.show_ready_placeholder)
                return
            file_size = os.path.getsize(fb_path)
            if file_size == 0:
                debug_print("0-byte framebuffer detected, showing sleeping.png")
                self.show_sleeping_placeholder()
                return
            if file_size < 100:
                debug_print(f"Framebuffer too small ({file_size} bytes), showing sleeping.png")
                self.show_sleeping_placeholder()
                return
            with open(fb_path, 'rb') as f:
                data = f.read(file_size)
            if len(data) < 100:
                debug_print(f"Framebuffer data too small ({len(data)} bytes), showing sleeping.png")
                self.show_sleeping_placeholder()
                return
            
            # Filter out null bytes from the data
            data = data.replace(b'\x00', b'\x01')  # Replace null bytes with 0x01 to prevent errors
            img_rgb = None
            expected_rgba = self.device_width * self.device_height * 4
            expected_rgb = self.device_width * self.device_height * 3
            expected_rgb565 = self.device_width * self.device_height * 2
            selected_profile = self.rgb_profile_var.get()
            formats_to_try = []
            if selected_profile == "Auto":
                if file_size >= expected_rgba:
                    formats_to_try = [
                        ("RGBA8888", "RGBA", expected_rgba, False),
                        ("BGRA8888", "RGBA", expected_rgba, True)
                    ]
                elif file_size >= expected_rgb:
                    formats_to_try = [
                        ("RGB888", "RGB", expected_rgb, False),
                        ("BGR888", "RGB", expected_rgb, True)
                    ]
                elif file_size >= expected_rgb565:
                    formats_to_try = [("RGB565", "RGB565", expected_rgb565, False)]
            else:
                if selected_profile == "RGBA8888":
                    formats_to_try = [("RGBA8888", "RGBA", expected_rgba, False)]
                elif selected_profile == "BGRA8888":
                    formats_to_try = [("BGRA8888", "RGBA", expected_rgba, True)]
                elif selected_profile == "RGB888":
                    formats_to_try = [("RGB888", "RGB", expected_rgb, False)]
                elif selected_profile == "BGR888":
                    formats_to_try = [("BGR888", "RGB", expected_rgb, True)]
                elif selected_profile == "RGB565":
                    formats_to_try = [("RGB565", "RGB565", expected_rgb565, False)]
            for format_name, pil_format, expected_size, swap_rb in formats_to_try:
                try:
                    if pil_format == "RGB565":
                        rgb_data = bytearray(expected_rgb)
                        for i in range(0, expected_rgb565, 2):
                            if i + 1 < len(data):
                                # Ensure we don't have null bytes in the pixel data
                                byte1 = data[i] if data[i] != 0 else 1
                                byte2 = data[i + 1] if data[i + 1] != 0 else 1
                                pixel = (byte2 << 8) | byte1
                                r = ((pixel >> 11) & 0x1F) << 3
                                g = ((pixel >> 5) & 0x3F) << 2
                                b = (pixel & 0x1F) << 3
                                rgb_idx = (i // 2) * 3
                                if rgb_idx + 2 < len(rgb_data):
                                    rgb_data[rgb_idx] = r
                                    rgb_data[rgb_idx + 1] = g
                                    rgb_data[rgb_idx + 2] = b
                        img = Image.frombytes('RGB', (self.device_width, self.device_height), bytes(rgb_data))
                        img_rgb = img
                    elif swap_rb:
                        arr = np.frombuffer(data[:expected_size], dtype=np.uint8)
                        # Filter out any null values
                        arr = np.where(arr == 0, 1, arr)
                        arr = arr.reshape((self.device_height, self.device_width, int(expected_size // (self.device_width * self.device_height))))
                        arr = arr[..., [2, 1, 0, 3]] if arr.shape[2] == 4 else arr[..., [2, 1, 0]]
                        img = Image.fromarray(arr)
                        img_rgb = img.convert('RGB')
                    else:
                        # Ensure the data doesn't contain null bytes
                        clean_data = data[:expected_size].replace(b'\x00', b'\x01')
                        img = Image.frombytes(pil_format, (self.device_width, self.device_height), clean_data)
                        img_rgb = img.convert('RGB') if pil_format == 'RGBA' else img
                    break
                except Exception as e:
                    continue
            if img_rgb is None:
                debug_print("Failed to process framebuffer, showing sleeping.png")
                self.show_sleeping_placeholder()
                return
            
            # Check if screen is blank/black
            if self.is_screen_blank(img_rgb):
                current_time = time.time()
                if current_time - self.last_blank_screen_detection > self.blank_screen_threshold:
                    # Show sleeping placeholder when blank screen is detected
                    debug_print("Blank screen detected for extended period, showing sleeping.png")
                    self.show_sleeping_placeholder()
                    self.last_blank_screen_detection = current_time
                    return
                else:
                    self.last_blank_screen_detection = current_time
            else:
                # Reset blank screen detection if screen has content
                self.last_blank_screen_detection = 0
            
            # No cropping - display full image
            resized_img = img_rgb.resize((self.display_width, self.display_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(resized_img)
            self.after_idle(lambda: self.update_screen_display(photo, self.display_height))
            # Save the last screen image for input mapping
            self.last_screen_image = img_rgb
        except Exception as e:
            debug_print(f"Framebuffer processing error: {e}")
            self.show_sleeping_placeholder()
    
    def force_framebuffer_refresh(self):
        """Force an immediate framebuffer refresh (non-blocking)"""
        debug_print("Forcing framebuffer refresh")
        
        # Set a flag to request immediate refresh in the background thread
        self.force_refresh_requested = True
        
        # Don't block the UI - let the background thread handle it
        # This prevents the wait cursor from staying too long
    
    def update_screen_display(self, photo, display_height=None):
        """Update screen display on main thread, with dynamic canvas height if needed"""
        # Reset ready placeholder flag when real screen is displayed
        self.ready_placeholder_shown = False
        try:
            if hasattr(self, 'current_photo'):
                del self.current_photo
            self.safe_ui_update(self.screen_canvas, "config", height=self.display_height)
            
            # Use the provided photo directly - it's already a PhotoImage
            # Just display it as is without trying to modify it
            self.current_photo = photo
            
            # Use safe UI update to modify canvas
            def update_canvas():
                try:
                    if self.screen_canvas.winfo_exists():
                        self.screen_canvas.delete("all")
                        self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=self.current_photo)
                except Exception as e:
                    debug_print(f"Error updating canvas in update_screen_display: {e}")
            
            # Schedule the update on the main thread
            self.safe_after(self, 0, update_canvas)
            
        except Exception as e:
            debug_print(f"Display update error: {e}")
    

    def show_sleeping_placeholder(self):
        """Show sleeping.png placeholder when device screen is black/sleeping"""
        try:
            # Try to load sleeping.png from the current directory
            sleeping_path = "sleeping.png"
            if os.path.exists(sleeping_path):
                img = Image.open(sleeping_path)
                # Resize to display dimensions
                img = img.resize((self.display_width, self.display_height), Image.Resampling.LANCZOS)
            else:
                # Fallback: create a simple sleeping placeholder
                img = Image.new('RGB', (self.display_width, self.display_height), (20, 20, 20))  # Very dark gray
                draw = ImageDraw.Draw(img)
                
                # Draw a simple "sleeping" icon (moon shape)
                center_x = self.display_width // 2
                center_y = self.display_height // 2
                radius = min(self.display_width, self.display_height) // 4
                
                # Draw a crescent moon
                draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius], 
                           outline=(100, 100, 100), width=8)
                draw.ellipse([center_x - radius//2, center_y - radius//2, center_x + radius//2, center_y + radius//2], 
                           fill=(20, 20, 20), outline=(20, 20, 20))
                
                # Add "Sleeping" text
                try:
                    font_size = 14
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
                    
                    text = "Sleeping"
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_x = (self.display_width - text_width) // 2
                    text_y = center_y + radius + 20
                    
                    draw.text((text_x, text_y), text, fill=(100, 100, 100), font=font)
                except:
                    pass
            
            # Convert to PhotoImage and display
            photo = ImageTk.PhotoImage(img)
            
            # Use safe UI update to modify canvas
            def update_canvas():
                try:
                    if self.screen_canvas.winfo_exists():
                        self.screen_canvas.delete("all")
                        self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                        
                        # Store reference
                        if hasattr(self, 'current_photo'):
                            del self.current_photo
                        self.current_photo = photo
                except Exception as e:
                    debug_print(f"Error updating canvas in show_sleeping_placeholder: {e}")
            
            # Schedule the update on the main thread
            self.safe_after(self, 0, update_canvas)
            
        except Exception as e:
            debug_print(f"Sleeping placeholder display error: {e}")
    
    def show_ready_placeholder(self):
        """Show ready.png placeholder when device is ready but no framebuffer response"""
        # Set flag to indicate ready placeholder is being shown
        self.ready_placeholder_shown = True
        try:
            # Try to load ready.png from the current directory
            ready_path = "ready.png"
            if os.path.exists(ready_path):
                img = Image.open(ready_path)
                # Resize to display dimensions
                img = img.resize((self.display_width, self.display_height), Image.Resampling.LANCZOS)
            else:
                # Fallback: create a simple ready placeholder
                img = Image.new('RGB', (self.display_width, self.display_height), (30, 30, 30))  # Dark gray
                draw = ImageDraw.Draw(img)
                
                # Draw a simple "ready" icon (checkmark)
                center_x = self.display_width // 2
                center_y = self.display_height // 2
                size = min(self.display_width, self.display_height) // 6
                
                # Draw a checkmark
                draw.line([center_x - size, center_y, center_x, center_y + size], 
                         fill=(0, 255, 0), width=8)
                draw.line([center_x, center_y + size, center_x + size, center_y - size], 
                         fill=(0, 255, 0), width=8)
                
                # Add "Ready" text
                try:
                    font_size = 14
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
                    
                    text = "Ready"
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_x = (self.display_width - text_width) // 2
                    text_y = center_y + size + 20
                    
                    draw.text((text_x, text_y), text, fill=(0, 255, 0), font=font)
                except:
                    pass
            
            # Convert to PhotoImage and display
            photo = ImageTk.PhotoImage(img)
            
            # Use safe UI update to modify canvas
            def update_canvas():
                try:
                    if self.screen_canvas.winfo_exists():
                        self.screen_canvas.delete("all")
                        self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                        
                        # Store reference
                        if hasattr(self, 'current_photo'):
                            del self.current_photo
                        self.current_photo = photo
                except Exception as e:
                    debug_print(f"Error updating canvas in show_ready_placeholder: {e}")
            
            # Schedule the update on the main thread
            self.safe_after(self, 0, update_canvas)
            
        except Exception as e:
            debug_print(f"Ready placeholder display error: {e}")
    
    def send_back_key(self):
        """Send back key event (for back button)"""
        debug_print("Back button pressed")
        if not self._input_paced():
            debug_print("Input paced, ignoring back button")
            return
            
        # Force framebuffer refresh before sending input
        self.force_framebuffer_refresh()
        
        debug_print("Sending BACK key")
        success, stdout, stderr = self.run_adb_command("shell input keyevent 4")  # KEYCODE_BACK
        if success:
            self.safe_ui_update(self.status_var, "set", "Back button pressed")
            debug_print("BACK key sent successfully")
            # Force framebuffer refresh after sending input
            self.safe_after(self, 100, self.force_framebuffer_refresh)
        else:
            self.safe_ui_update(self.status_var, "set", f"Back button failed: {stderr}")
            debug_print(f"BACK key failed: {stderr}")
    
    def set_device_stay_awake(self):
        """Set device to stay awake while charging to ensure consistent framebuffer output"""
        if not self.device_connected or self.device_stay_awake_set:
            return
        
        debug_print("Setting device to stay awake while charging")
        try:
            # Set stay awake while charging (requires WRITE_SETTINGS permission)
            success, stdout, stderr = self.run_adb_command("shell settings put global stay_on_while_plugged_in 3")
            if success:
                self.device_stay_awake_set = True
                debug_print("Device stay awake setting applied successfully")
            else:
                debug_print(f"Failed to set stay awake: {stderr}")
        except Exception as e:
            debug_print(f"Error setting stay awake: {e}")
    
    def sync_device_time(self):
        """Sync device time with host system time using toolbox date format"""
        if not self.device_connected:
            messagebox.showerror("Device Not Connected", "Please connect your device first.")
            return
        try:
            import datetime
            # Get current system time in toolbox format: YYYYMMDD.HHmmss
            now = datetime.datetime.now()
            toolbox_time = now.strftime('%Y%m%d.%H%M%S')
            current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")

            # Check if toolbox is available
            check_toolbox, out, err = self.run_adb_command('shell toolbox date')
            if not check_toolbox or 'not found' in out or 'not found' in err:
                messagebox.showerror("Toolbox Not Found", "The 'toolbox' binary is not available on this device. Time sync cannot proceed.")
                self.status_var.set("Toolbox not found on device")
                return

            # Set the system time using toolbox
            set_cmd = f'shell su 0 toolbox date -s {toolbox_time}'
            success, stdout, stderr = self.run_adb_command(set_cmd)

            if success and (str(now.year) in stdout or str(now.year) in stderr):
                debug_print(f"Device time synced successfully: {current_time_str}")
                
                # Check if org.rockbox is running and restart it
                rockbox_check, rockbox_out, rockbox_err = self.run_adb_command('shell dumpsys activity activities | grep org.rockbox')
                if rockbox_check and 'org.rockbox' in rockbox_out:
                    debug_print("Rockbox is running, restarting it...")
                    # Force stop org.rockbox
                    self.run_adb_command('shell am force-stop org.rockbox')
                    # Wait a moment
                    time.sleep(1)
                    # Start org.rockbox again
                    self.run_adb_command('shell am start -n org.rockbox/.RockboxActivity')
                    debug_print("Rockbox restarted")
                
                # Send home command to return to launcher
                self.run_adb_command('shell input keyevent 3')  # KEYCODE_HOME
                debug_print("Sent home command")
                
                messagebox.showinfo("Time Sync Complete", f"Device time has been successfully set to:\n{current_time_str}\n\nRockbox has been restarted if it was running.")
                self.status_var.set("Device time synced successfully")
            else:
                debug_print(f"Failed to sync device time: {stderr or stdout}")
                messagebox.showwarning("Time Sync Failed", f"Unable to set the device time.\n\nADB output:\n{stderr or stdout}\n\nThis feature requires root access and toolbox support.")
                self.status_var.set("Time sync failed")
        except Exception as e:
            debug_print(f"Exception syncing device time: {e}")
            messagebox.showerror("Time Sync Error", f"An error occurred while syncing device time:\n{str(e)}")
            self.status_var.set("Time sync failed")
    
    def is_screen_blank(self, img):
        """Detect if the screen is blank/black (mostly dark with low variance)"""
        try:
            import numpy as np
            arr = np.array(img)
            
            # Filter out any null values that might cause issues
            arr = np.nan_to_num(arr, nan=0.0, posinf=255.0, neginf=0.0)
            
            # Convert to RGB if needed
            if len(arr.shape) == 3:
                # Calculate mean luminance across all pixels
                # Use luminance formula: 0.299*R + 0.587*G + 0.114*B
                luminance = np.dot(arr[..., :3], [0.299, 0.587, 0.114])
                mean_luminance = np.mean(luminance)
                
                # Calculate standard deviation to check for variance
                std_luminance = np.std(luminance)
                
                # Get the first pixel as reference
                first_pixel = arr[0, 0]
                
                # Check if it's a dark color (R, G, B all < 20 for more lenient detection)
                is_dark = np.all(first_pixel < 20)
                
                # Check if variance is very low (mostly uniform)
                is_low_variance = std_luminance < 5.0
                
                # Check if mean luminance is very low
                is_low_luminance = mean_luminance < 15.0
                
                debug_print(f"Screen luminance check: mean={mean_luminance:.2f}, std={std_luminance:.2f}, dark={is_dark}, low_variance={is_low_variance}, low_luminance={is_low_luminance}")
                
                # Screen is blank if it's dark AND has low variance AND low mean luminance
                return is_dark and is_low_variance and is_low_luminance
            else:
                # Grayscale image
                mean_value = np.mean(arr)
                std_value = np.std(arr)
                is_dark = mean_value < 20
                is_low_variance = std_value < 5.0
                
                debug_print(f"Screen luminance check (grayscale): mean={mean_value:.2f}, std={std_value:.2f}, dark={is_dark}, low_variance={is_low_variance}")
                
                return is_dark and is_low_variance
        except Exception as e:
            debug_print(f"Error detecting blank screen: {e}")
            return False
    
    def launch_settings(self):
        """Launch Android Settings app"""
        success, stdout, stderr = self.run_adb_command(
            "shell am start -n com.android.settings/.Settings")
        if success:
            self.status_var.set("Settings launched")
            self.current_app = "com.android.settings"
            self.control_launcher = False  # Disable launcher control
            self.scroll_wheel_mode_var.set(False)  # Update UI checkbox
        else:
            self.status_var.set(f"Failed to launch settings: {stderr}")
    
    def go_home(self):
        """Restart the built-in home app (com.innioasis.y1)"""
        self.status_var.set("Restarting Home App...")
        # Force-stop the home app
        self.run_adb_command("shell am force-stop com.innioasis.y1")
        # Launch the home app
        success, stdout, stderr = self.run_adb_command("shell monkey -p com.innioasis.y1 -c android.intent.category.LAUNCHER 1")
        if success:
            self.status_var.set("Home app restarted (com.innioasis.y1)")
            self.current_app = "com.innioasis.y1"
            self.control_launcher = True  # Enable launcher control
            self.scroll_wheel_mode_var.set(True)  # Update UI checkbox
        else:
            self.status_var.set("Failed to restart home app: " + (stderr or stdout))
            messagebox.showerror("Restart Home App", "Failed to restart the home app.\n\nPlease ensure:\n- Device is unlocked\n- Y1 launcher is installed\n- Device is responsive")
    
    def browse_apks(self):
        """Browse and install APK file"""
        file_path = filedialog.askopenfilename(
            title="Select APK file",
            filetypes=[("APK files", "*.apk"), ("All files", "*.*")]
        )
        if file_path:
            # Create progress dialog for APK installation
            progress_dialog = self.create_progress_dialog("Installing APK")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label'):
                        progress_dialog.status_label.config(text=message)
                        progress_dialog.update()
                    debug_print(f"APK Install Progress: {message}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress("Preparing APK for installation...")
            self.status_var.set("Installing APK...")
            
            # Convert to absolute path using platform-appropriate methods
            import os
            import platform
            file_path = os.path.abspath(file_path)
            
            update_progress("Installing APK to device...")
            
            # Use the full path in the ADB command
            success, stdout, stderr = self.run_adb_command(f"install -r \"{file_path}\"")
            
            # Close progress dialog
            if progress_dialog:
                try:
                    progress_dialog.destroy()
                except Exception as e:
                    debug_print(f"Error destroying progress dialog: {e}")
            
            if success:
                self.status_var.set("APK installed successfully")
                self.refresh_apps()
            else:
                # Provide more detailed error information
                error_msg = stderr.strip() if stderr else stdout.strip()
                if "device not found" in error_msg.lower():
                    self.status_var.set("APK installation failed: Device not connected")
                elif "permission denied" in error_msg.lower():
                    self.status_var.set("APK installation failed: Permission denied - check USB debugging")
                elif "failed to install" in error_msg.lower():
                    self.status_var.set("APK installation failed: Incompatible APK or insufficient storage")
                else:
                    self.status_var.set(f"APK installation failed: {error_msg}")
                
                # Show detailed error in console for debugging
                print(f"APK Installation Error:")
                print(f"  File: {file_path}")
                print(f"  Error: {error_msg}")
        else:
            self.status_var.set("APK installation cancelled")
    
    def install_apps(self):
        """Install apps from the manifest"""
        if not self.device_connected:
            messagebox.showerror(
                "No Device Connected", 
                "No device is currently connected via ADB. Please connect a device before installing apps."
            )
            return
        
        # Mark that user triggered a cache refresh
        self.user_triggered_cache_refresh = True
        
        try:
            # Create progress dialog for manifest fetching
            progress_dialog = self.create_progress_dialog("Fetching App Manifest")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label'):
                        progress_dialog.status_label.config(text=message)
                        progress_dialog.update()
                    debug_print(f"App Install Progress: {message}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress("Connecting to manifest server...")
            self.status_var.set("Fetching app manifest...")
            
            # Refresh cache if needed and rebuild file URLs
            self.refresh_cache_if_needed()
            
            # Try to get manifest content with fallback to cache
            manifest_content = None
            
            # Method 1: Try to download fresh manifest
            try:
                debug_print("Attempting to download fresh manifest...")
                response = self._make_github_request_with_retries(self.manifest_url)
                if response and response.status_code == 200:
                    manifest_content = response.text
                    debug_print("Fresh manifest downloaded successfully")
                    # Update cache with fresh manifest and rebuild file URLs
                    try:
                        self.build_cache_index_with_releases(manifest_content)
                        debug_print("Cache updated with fresh manifest and file URLs")
                    except Exception as e:
                        debug_print(f"Cache update failed: {e}")
                else:
                    debug_print("Fresh manifest download failed, using cache")
            except Exception as e:
                debug_print(f"Error downloading fresh manifest: {e}")
            
            # Method 2: Fallback to cached manifest
            if not manifest_content:
                debug_print("Using cached manifest...")
                manifest_content = self.get_cached_manifest()
            
            # Parse manifest to find app repositories
            update_progress("Parsing app manifest...")
            app_options = self.parse_app_manifest(manifest_content)
            
            # Close manifest progress dialog
            if progress_dialog:
                try:
                    progress_dialog.destroy()
                except Exception as e:
                    debug_print(f"Error destroying progress dialog: {e}")
            
            if not app_options:
                # Show error message inline in the app selection dialog
                self.show_app_selection_dialog_with_error("No apps currently available. Apps will appear here once they are published to the Slidia repository.")
                return
            
            # Show app selection dialog
            selected_app = self.show_app_selection_dialog(app_options)
            if not selected_app:
                return
            
            # Download the selected app
            self.status_var.set(f"Downloading {selected_app['name']}...")
            debug_print(f"Starting download for app: {selected_app['name']}")
            app_path = self.download_app(selected_app)
            
            if not app_path:
                debug_print(f"Download failed for app: {selected_app['name']}")
                messagebox.showerror("Download Failed", f"Failed to download {selected_app['name']}. Check the debug logs for details.")
                return
            
            # Install the app using ADB
            self.status_var.set("Installing app...")
            success, error_msg = self.install_downloaded_app(app_path)
            
            if success:
                messagebox.showinfo("Installation Complete", "App installation completed successfully!")
                self.status_var.set("App installation complete")
                self.refresh_apps()
            else:
                # Check if the error is due to no device connection
                user_friendly_error = "App installation failed. Check the logs for details."
                if error_msg and "no devices/emulators found" in error_msg.lower():
                    user_friendly_error = "App installation failed: No device connected via ADB.\n\nPlease ensure your device is:\n� Connected via USB\n� Has USB debugging enabled\n� Is authorized for ADB connections"
                elif error_msg and "device offline" in error_msg.lower():
                    user_friendly_error = "App installation failed: Device is offline.\n\nPlease check that your device is properly connected and try again."
                elif error_msg and "unauthorized" in error_msg.lower():
                    user_friendly_error = "App installation failed: Device not authorized.\n\nPlease check the authorization dialog on your device and tap 'Allow'."
                elif error_msg:
                    user_friendly_error = f"App installation failed: {error_msg}"
                
                messagebox.showerror("Installation Failed", user_friendly_error)
                self.status_var.set("App installation failed")
                
        except Exception as e:
            debug_print(f"App installation error: {e}")
            messagebox.showerror("Installation Error", f"An error occurred during app installation: {str(e)}")
            self.status_var.set("App installation error")
    
    # prepare_device method removed - replaced with install_firmware
    
    def open_nova_launcher(self):
        self.run_adb_command("shell monkey -p com.teslacoilsw.launcher -c android.intent.category.LAUNCHER 1")
        self.status_var.set("Nova Launcher opened")

    def open_keycode_disp(self):
        self.run_adb_command("shell monkey -p jp.ne.neko.freewing.KeyCodeDisp -c android.intent.category.LAUNCHER 1")
        self.status_var.set("KeyCode Display app opened")

    def open_launcher(self, pkg):
        self.run_adb_command(f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        self.status_var.set(f"Launcher {pkg} opened")
    
    def launch_app(self, package_name):
        """Launch specified app"""
        debug_print(f"Launching app: {package_name}")
        success, stdout, stderr = self.run_adb_command(
            f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
        if success:
            self.status_var.set(f"Launched {package_name}")
            self.current_app = package_name
            
            # Clear manual override when launching app from Y1 helper
            self.manual_mode_override = False
            debug_print("Manual mode override cleared due to app launch from Y1 helper")
            
            # Set appropriate mode based on app type
            if self._should_auto_enable_scroll_wheel(package_name):
                self.control_launcher = True
                self.scroll_wheel_mode_var.set(True)
                self.input_mode_btn.config(text="Scroll Wheel Mode")
                self.disable_swap_checkbox.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
            else:
                self.control_launcher = False
                self.scroll_wheel_mode_var.set(False)
                self.input_mode_btn.config(text="Touch Screen Mode")
                # Hide checkbox when switching to touch screen mode
                self.disable_swap_checkbox.pack_forget()
            
            debug_print(f"App {package_name} launched successfully")
            self.refresh_apps()  # Ensure app list is up to date after launch
        else:
            self.status_var.set(f"Failed to launch {package_name}: {stderr}")
            debug_print(f"Failed to launch {package_name}: {stderr}")
    
    def uninstall_app(self, package_name):
        debug_print(f"Uninstalling app: {package_name}")
        confirm = messagebox.askyesno("Uninstall App", f"Are you sure you want to uninstall {package_name}?")
        if not confirm:
            debug_print("App uninstall cancelled by user")
            return
        
        # Create progress dialog for uninstallation
        progress_dialog = self.create_progress_dialog("Uninstalling App")
        progress_dialog.progress_bar.start()
        
        def update_progress(message):
            try:
                if progress_dialog and hasattr(progress_dialog, 'status_label'):
                    progress_dialog.status_label.config(text=message)
                    progress_dialog.update()
                debug_print(f"App Uninstall Progress: {message}")
            except Exception as e:
                debug_print(f"Progress update failed: {e}")
        
        update_progress(f"Uninstalling {package_name}...")
        self.status_var.set(f"Uninstalling {package_name}...")
        
        success, stdout, stderr = self.run_adb_command(f"uninstall {package_name}")
        
        # Close progress dialog
        if progress_dialog:
            try:
                progress_dialog.destroy()
            except Exception as e:
                debug_print(f"Error destroying progress dialog: {e}")
        
        if success:
            self.status_var.set(f"{package_name} uninstalled successfully")
            debug_print(f"App {package_name} uninstalled successfully")
            self.refresh_apps()
        else:
            self.status_var.set(f"Failed to uninstall {package_name}: {stderr}")
            debug_print(f"Failed to uninstall {package_name}: {stderr}")
    
    def toggle_launcher_control_old(self, event=None):
        """Legacy toggle launcher control mode (deprecated)"""
        debug_print("Toggling launcher control (legacy)")
        self.control_launcher = not self.control_launcher
        self.scroll_wheel_mode_var.set(self.control_launcher)
        status = "enabled" if self.control_launcher else "disabled"
        self.status_var.set(f"Launcher control {status}")
        debug_print(f"Launcher control {status}")
    
    def on_screen_click(self, event):
        """Handle left click on screen (touch input or enter in launcher mode)"""
        if self.input_disabled:
            debug_print("Input disabled - device disconnected, ignoring click")
            return
        debug_print(f"Screen click at ({event.x}, {event.y})")
        if not self._input_paced():
            debug_print("Input paced, ignoring click")
            return
        # Calculate coordinates directly (no cropping offset)
        x = int(event.x / self.display_scale)
        y = int(event.y / self.display_scale)
        
        # Check if click is within the display area
        if x < 0 or x >= self.device_width or y < 0 or y >= self.device_height:
            debug_print("Click outside image area, ignoring")
            return  # Click outside the image area
        debug_print(f"Adjusted coordinates: ({x}, {y})")
        
        # Force framebuffer refresh before sending input
        self.force_framebuffer_refresh()
        
        if self.control_launcher and self.scroll_wheel_mode_var.get():
            debug_print("Sending ENTER key (scroll wheel mode)")
            success, stdout, stderr = self.run_adb_command("shell input keyevent 66")  # KEYCODE_ENTER
            if success:
                self.status_var.set("Enter key sent")
                debug_print("ENTER key sent successfully")
                # Force framebuffer refresh after sending input
                self.after(100, self.force_framebuffer_refresh)
            else:
                self.status_var.set(f"Enter key failed: {stderr}")
                debug_print(f"ENTER key failed: {stderr}")
        else:
            debug_print(f"Sending touch input to ({x}, {y})")
            success, stdout, stderr = self.run_adb_command(
                f"shell input tap {x} {y}")
            if success:
                self.status_var.set(f"Touch input sent to ({x}, {y})")
                debug_print("Touch input sent successfully")
                # Force framebuffer refresh after sending input
                self.after(100, self.force_framebuffer_refresh)
            else:
                self.status_var.set(f"Touch input failed: {stderr}")
                debug_print(f"Touch input failed: {stderr}")
    
    def on_screen_right_click(self, event):
        """Handle right click on screen (back button)"""
        if self.input_disabled:
            debug_print("Input disabled - device disconnected, ignoring right click")
            return
        debug_print("Screen right click (back button)")
        if not self._input_paced():
            debug_print("Input paced, ignoring right click")
            return
            
        # Force framebuffer refresh before sending input
        self.force_framebuffer_refresh()
        
        debug_print("Sending BACK key")
        success, stdout, stderr = self.run_adb_command("shell input keyevent 4")  # KEYCODE_BACK
        if success:
            self.status_var.set("Back button pressed")
            debug_print("BACK key sent successfully")
            # Force framebuffer refresh after sending input
            self.after(100, self.force_framebuffer_refresh)
        else:
            self.status_var.set(f"Back button failed: {stderr}")
            debug_print(f"BACK key failed: {stderr}")
    
    def on_mouse_wheel(self, event):
        if self.input_disabled:
            debug_print("Input disabled - device disconnected, ignoring mouse wheel")
            return
        debug_print(f"Mouse wheel event: {event}")
        if not self._input_paced():
            debug_print("Input paced, ignoring mouse wheel")
            return
        direction = 0
        if hasattr(event, 'delta') and event.delta != 0:
            if event.delta > 0:
                direction = 1
            else:
                direction = -1
            debug_print(f"Mouse wheel direction from delta: {direction}")
        elif hasattr(event, 'num'):
            if event.num == 4:
                direction = 1
            elif event.num == 5:
                direction = -1
            else:
                debug_print(f"Unknown mouse wheel button: {event.num}")
                return
            debug_print(f"Mouse wheel direction from button: {direction}")
        else:
            debug_print("No mouse wheel direction detected")
            return
        
        # Show scroll cursor if in scroll wheel mode
        if self.scroll_wheel_mode_var.get():
            self.show_scroll_cursor()
        # Scroll wheel mapping in scroll wheel mode
        if self.control_launcher and self.scroll_wheel_mode_var.get():
            # Check if direction should be inverted (Y1 launcher detected OR checkbox enabled)
            should_invert = self.disable_dpad_swap_var.get() or self.y1_launcher_detected
            
            if should_invert:
                # Inverted direction - remap scroll wheel to D-pad (no direction reversal)
                if direction > 0:
                    keycode = 22  # KEYCODE_DPAD_RIGHT (up becomes right)
                    dir_str = "right"
                else:
                    keycode = 21  # KEYCODE_DPAD_LEFT (down becomes left)
                    dir_str = "left"
                debug_print(f"Scroll wheel mode (inverted): sending D-pad {dir_str}")
            else:
                # Normal direction - standard behavior
                if direction > 0:
                    keycode = 19  # KEYCODE_DPAD_UP
                    dir_str = "up"
                else:
                    keycode = 20  # KEYCODE_DPAD_DOWN
                    dir_str = "down"
                debug_print(f"Scroll wheel mode (normal): sending D-pad {dir_str}")
        else:
            if direction > 0:
                keycode = 19  # KEYCODE_DPAD_UP
                dir_str = "up"
            else:
                keycode = 20  # KEYCODE_DPAD_DOWN
                dir_str = "down"
            debug_print(f"Touch screen mode: sending D-pad {dir_str}")
        
        # Set input command flag to prevent false disconnection detection
        self.input_command_in_progress = True
        
        # Send input immediately (framebuffer refresh is now non-blocking)
        success, stdout, stderr = self.run_adb_command(f"shell input keyevent {keycode}")
        
        # Clear input command flag
        self.input_command_in_progress = False
        
        if success:
            self.status_var.set(f"D-pad {dir_str} pressed")
            debug_print(f"D-pad {dir_str} sent successfully")
            # Request framebuffer refresh after sending input (non-blocking)
            self.after(50, self.force_framebuffer_refresh)
        else:
            self.status_var.set(f"D-pad {dir_str} failed: {stderr}")
            debug_print(f"D-pad {dir_str} failed: {stderr}")
            # Don't trigger device disconnection for input command failures
            # as they can be temporary and don't indicate device disconnection
    
    def on_mouse_wheel_click(self, event):
        if self.input_disabled:
            debug_print("Input disabled - device disconnected, ignoring mouse wheel click")
            return
        debug_print("Mouse wheel click")
        if not self._input_paced():
            debug_print("Input paced, ignoring mouse wheel click")
            return
        # Y1 scroll wheel center = ENTER, back/menu = BACK
        if self.control_launcher and self.scroll_wheel_mode_var.get():
            keycode = 66  # KEYCODE_ENTER
            action = "enter"
            debug_print("Scroll wheel mode: sending ENTER key")
        else:
            keycode = 23  # KEYCODE_DPAD_CENTER
            action = "d-pad center"
            debug_print("Touch screen mode: sending D-pad center")
        
        # Set input command flag to prevent false disconnection detection
        self.input_command_in_progress = True
        
        # Send input immediately (framebuffer refresh is now non-blocking)
        success, stdout, stderr = self.run_adb_command(f"shell input keyevent {keycode}")
        
        # Clear input command flag
        self.input_command_in_progress = False
        
        if success:
            self.status_var.set(f"Mouse wheel click: {action} pressed")
            debug_print(f"Mouse wheel click ({action}) sent successfully")
            # Request framebuffer refresh after sending input (non-blocking)
            self.after(50, self.force_framebuffer_refresh)
        else:
            self.status_var.set(f"Mouse wheel click failed: {stderr}")
            debug_print(f"Mouse wheel click failed: {stderr}")
            # Don't trigger device disconnection for input command failures
            # as they can be temporary and don't indicate device disconnection
    
    def on_key_press(self, event):
        if self.input_disabled:
            debug_print("Input disabled - device disconnected, ignoring key press")
            return
        debug_print(f"Key press: {event.keysym}")
        if not self._input_paced():
            debug_print("Input paced, ignoring key press")
            return
        key = event.keysym.lower()
        dpad_map = {
            'w': 19, 'up': 19,
            's': 20, 'down': 20,
            'a': 21, 'left': 21,
            'd': 22, 'right': 22
        }
        direction_map = {
            19: 'up', 20: 'down', 21: 'left', 22: 'right'
        }
        if key in dpad_map:
            keycode = dpad_map[key]
            direction = direction_map[keycode]
            debug_print(f"D-pad key detected: {key} -> {direction}")
            if self.control_launcher and self.scroll_wheel_mode_var.get():
                # Check if direction should be inverted (Y1 launcher detected OR checkbox enabled)
                should_invert = self.disable_dpad_swap_var.get() or self.y1_launcher_detected
                
                if should_invert:
                    # Inverted direction - remap D-pad axes (no direction reversal)
                    if keycode == 19:  # UP
                        keycode = 22  # RIGHT (up becomes right)
                        direction = 'right'
                        debug_print("Scroll wheel mode: remapping up -> right (inverted)")
                    elif keycode == 20:  # DOWN
                        keycode = 21  # LEFT (down becomes left)
                        direction = 'left'
                        debug_print("Scroll wheel mode: remapping down -> left (inverted)")
                    elif keycode == 21:  # LEFT
                        keycode = 20  # DOWN (left becomes down)
                        direction = 'down'
                        debug_print("Scroll wheel mode: remapping left -> down (inverted)")
                    elif keycode == 22:  # RIGHT
                        keycode = 19  # UP (right becomes up)
                        direction = 'up'
                        debug_print("Scroll wheel mode: remapping right -> up (inverted)")
                else:
                    debug_print("Scroll wheel mode: using normal mapping")
                
                # Show scroll cursor for keyboard navigation in scroll wheel mode
                if key in ['w', 'up', 's', 'down', 'a', 'left', 'd', 'right']:
                    self.show_scroll_cursor()
            else:
                debug_print("Touch screen mode: using normal D-pad mapping")
        elif key in ['return', 'e', 'shift_r']:
            if self.control_launcher and self.scroll_wheel_mode_var.get():
                keycode = 66
                direction = "enter"
                debug_print("Scroll wheel mode: sending ENTER key")
            else:
                keycode = 23
                direction = "center"
                debug_print("Touch screen mode: sending D-pad center")
        elif key in ['q', 'slash', 'Escape']:
            keycode = 4
            direction = "back"
            debug_print("Sending BACK key")
        elif key == 'space':
            keycode = 85
            direction = "play/pause"
            debug_print("Sending play/pause key")
        elif key == 'prior':
            keycode = 87
            direction = "next"
            debug_print("Sending next track key")
        elif key == 'next':
            keycode = 88
            direction = "previous"
            debug_print("Sending previous track key")
        elif key == 'd' and event.state & 0x4:  # Ctrl+D
            toggle_debug_mode()
            return  # Don't send any key to device
        else:
            debug_print(f"Unrecognized key: {key}")
            return
        debug_print(f"Sending keycode {keycode} ({direction})")
        
        # Set input command flag to prevent false disconnection detection
        self.input_command_in_progress = True
        
        # Send input immediately (framebuffer refresh is now non-blocking)
        success, stdout, stderr = self.run_adb_command(f"shell input keyevent {keycode}")
        
        # Clear input command flag
        self.input_command_in_progress = False
        
        if success:
            self.status_var.set(f"Key {direction} pressed")
            debug_print(f"Key {direction} sent successfully")
            # Request framebuffer refresh after sending input (non-blocking)
            self.after(50, self.force_framebuffer_refresh)
            self.after(1500, lambda: self.status_var.set("Ready"))
        else:
            self.status_var.set(f"Key {direction} failed: {stderr}")
            debug_print(f"Key {direction} failed: {stderr}")
            # Don't trigger device disconnection for input command failures
            # as they can be temporary and don't indicate device disconnection
    
    def on_key_release(self, event):
        """Handle key release to hide scroll cursor immediately"""
        if self.input_disabled:
            debug_print("Input disabled - device disconnected, ignoring key release")
            return
        key = event.keysym.lower()
        # Check if this is a navigation key that would show the scroll cursor
        nav_keys = ['w', 'up', 's', 'down', 'a', 'left', 'd', 'right']
        if key in nav_keys and self.scroll_wheel_mode_var.get():
            # Hide scroll cursor immediately on key release
            if self.scroll_cursor_timer:
                self.after_cancel(self.scroll_cursor_timer)
                self.scroll_cursor_timer = None
            self.hide_scroll_cursor()
            debug_print(f"Key release detected for {key}, hiding scroll cursor")
    
    def on_mouse_wheel_release(self, event):
        """Handle mouse wheel release to hide scroll cursor immediately"""
        if self.input_disabled:
            debug_print("Input disabled - device disconnected, ignoring mouse wheel release")
            return
        if self.scroll_wheel_mode_var.get():
            # Hide scroll cursor immediately on mouse wheel release
            if self.scroll_cursor_timer:
                self.after_cancel(self.scroll_cursor_timer)
                self.scroll_cursor_timer = None
            self.hide_scroll_cursor()
            debug_print("Mouse wheel release detected, hiding scroll cursor")
    
    def toggle_play_pause(self):
        """Toggle play/pause on device"""
        self.force_framebuffer_refresh()
        self.run_adb_command("shell input keyevent 85")  # KEYCODE_MEDIA_PLAY_PAUSE
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def previous_track(self):
        """Send previous track key event"""
        self.force_framebuffer_refresh()
        self.run_adb_command("shell input keyevent 88")  # KEYCODE_MEDIA_PREVIOUS
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def next_track(self):
        """Send next track key event"""
        self.force_framebuffer_refresh()
        self.run_adb_command("shell input keyevent 87")  # KEYCODE_MEDIA_NEXT
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def nav_up(self):
        """Navigate up (inverted for launcher)"""
        self.force_framebuffer_refresh()
        if self.control_launcher:
            self.run_adb_command("shell input keyevent 20")  # KEYCODE_DPAD_DOWN
        else:
            self.run_adb_command("shell input keyevent 19")  # KEYCODE_DPAD_UP
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def nav_down(self):
        """Navigate down (inverted for launcher)"""
        self.force_framebuffer_refresh()
        if self.control_launcher:
            self.run_adb_command("shell input keyevent 19")  # KEYCODE_DPAD_UP
        else:
            self.run_adb_command("shell input keyevent 20")  # KEYCODE_DPAD_DOWN
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def nav_left(self):
        """Navigate left (inverted for launcher)"""
        self.force_framebuffer_refresh()
        if self.control_launcher:
            self.run_adb_command("shell input keyevent 22")  # KEYCODE_DPAD_RIGHT
        else:
            self.run_adb_command("shell input keyevent 21")  # KEYCODE_DPAD_LEFT
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def nav_right(self):
        """Navigate right (inverted for launcher)"""
        self.force_framebuffer_refresh()
        if self.control_launcher:
            self.run_adb_command("shell input keyevent 21")  # KEYCODE_DPAD_LEFT
        else:
            self.run_adb_command("shell input keyevent 22")  # KEYCODE_DPAD_RIGHT
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def nav_center(self):
        """Send center/select key event"""
        self.force_framebuffer_refresh()
        if self.control_launcher:
            self.run_adb_command("shell input keyevent 66")  # KEYCODE_ENTER
        else:
            self.run_adb_command("shell input keyevent 23")  # KEYCODE_DPAD_CENTER
        self.after(100, self.force_framebuffer_refresh)
        self.after(1500, lambda: self.status_var.set("Ready"))

    def open_adb_shell(self):
        """Open ADB shell in new window"""
        debug_print("Opening ADB shell")
        try:
            adb_path = self.get_adb_path()
            debug_print(f"ADB shell path: {adb_path}")
            
            subprocess.Popen([adb_path, "shell"], 
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
            debug_print("ADB shell opened successfully")
        except Exception as e:
            debug_print(f"Failed to open ADB shell: {e}")
            messagebox.showerror("Error", f"Failed to open ADB shell: {e}")
    
    def show_device_info(self):
        """Show device information"""
        info = []
        
        # Get device model
        success, stdout, stderr = self.run_adb_command("shell getprop ro.product.model")
        if success:
            info.append(f"Model: {stdout.strip()}")
        
        # Get Android version
        success, stdout, stderr = self.run_adb_command("shell getprop ro.build.version.release")
        if success:
            info.append(f"Android: {stdout.strip()}")
        
        # Get screen resolution
        success, stdout, stderr = self.run_adb_command("shell wm size")
        if success:
            info.append(f"Screen: {stdout.strip()}")
        
        # Get framebuffer info
        success, stdout, stderr = self.run_adb_command("shell cat /sys/class/graphics/fb0/bits_per_pixel")
        if success:
            info.append(f"Framebuffer bits per pixel: {stdout.strip()}")
        
        success, stdout, stderr = self.run_adb_command("shell cat /sys/class/graphics/fb0/stride")
        if success:
            info.append(f"Framebuffer stride: {stdout.strip()}")
        
        info_text = "\n".join(info) if info else "Unable to get device info"
        messagebox.showinfo("Device Information", info_text)
    
    def change_device_language(self):
        """Open Android language settings"""
        if not self.device_connected:
            messagebox.showerror("Error", "Device not connected!\n\nPlease ensure:\n- Device is connected via USB\n- USB debugging is enabled\n- Device is authorized for ADB")
            return
        
        self.status_var.set("Opening language settings...")
        success, stdout, stderr = self.run_adb_command("shell am start -a android.settings.LOCALE_SETTINGS")
        
        if success:
            self.status_var.set("Language settings opened")
            messagebox.showinfo("Language Settings", 
                              "Language settings have been opened on your device.\n\n"
                              "You can now:\n"
                              "� Select your preferred language\n"
                              "� Choose regional settings\n"
                              "� Configure input methods")
        else:
            error_msg = stderr.strip() if stderr else stdout.strip()
            self.status_var.set(f"Failed to open language settings: {error_msg}")
            messagebox.showerror("Error", 
                               f"Failed to open language settings:\n\n{error_msg}\n\n"
                               "Please ensure:\n"
                               "- Device is unlocked\n"
                               "- Settings app is available\n"
                               "- Device is responsive")
    
    def open_file_explorer(self):
        """Open the file explorer dialog"""
        debug_print("Opening file explorer")
        try:
            adb_path = self.get_adb_path()
            explorer = FileExplorerDialog(self, adb_path)
            explorer.show()
        except Exception as e:
            debug_print(f"Error opening file explorer: {e}")
            messagebox.showerror("Error", f"Failed to open file explorer: {e}")
    
    def restart_device(self):
        """Restart the connected device"""
        debug_print("Restarting device")
        try:
            success, stdout, stderr = self.run_adb_command("reboot")
            if success:
                self.status_var.set("Device restarting...")
                debug_print("Device restart command sent successfully")
            else:
                self.status_var.set(f"Failed to restart device: {stderr}")
                debug_print(f"Device restart failed: {stderr}")
                messagebox.showerror("Error", f"Failed to restart device: {stderr}")
        except Exception as e:
            debug_print(f"Error restarting device: {e}")
            messagebox.showerror("Error", f"Failed to restart device: {e}")
    
    def launch_rockbox_utility(self):
        """Launch Rockbox Utility from assets directory"""
        try:
            debug_print("Launching Rockbox Utility...")
            rockbox_utility_path = os.path.join(self.base_dir, "assets", "RockboxUtility.exe")
            
            if not os.path.exists(rockbox_utility_path):
                debug_print("RockboxUtility.exe not found in assets directory")
                messagebox.showerror("Error", "RockboxUtility.exe not found in assets directory")
                return
            
            debug_print(f"Launching Rockbox Utility from: {rockbox_utility_path}")
            
            # Launch normally - Rockbox Utility will request its own privileges
            import subprocess
            subprocess.Popen([rockbox_utility_path], cwd=os.path.dirname(rockbox_utility_path))
            
            self.status_var.set("Rockbox Utility launched")
            debug_print("Rockbox Utility launched successfully")
        except Exception as e:
            debug_print(f"Error launching Rockbox Utility: {e}")
            messagebox.showerror("Error", f"Failed to launch Rockbox Utility: {e}")
    
    def launch_sp_flash_tool(self):
        """Launch SP Flash Tool from assets directory"""
        try:
            debug_print("Launching SP Flash Tool...")
            flash_tool_path = os.path.join(self.base_dir, "assets", "flash_tool.exe")
            
            if not os.path.exists(flash_tool_path):
                debug_print("flash_tool.exe not found in assets directory")
                messagebox.showerror("Error", "flash_tool.exe not found in assets directory")
                return
            
            debug_print(f"Launching SP Flash Tool from: {flash_tool_path}")
            import subprocess
            subprocess.Popen([flash_tool_path], cwd=os.path.dirname(flash_tool_path))
            self.status_var.set("SP Flash Tool launched")
            debug_print("SP Flash Tool launched successfully")
        except Exception as e:
            debug_print(f"Error launching SP Flash Tool: {e}")
            messagebox.showerror("Error", f"Failed to launch SP Flash Tool: {e}")
    
    def restart_rockbox(self):
        """Restart Rockbox application"""
        debug_print("Restarting Rockbox")
        try:
            # Force stop Rockbox
            success, stdout, stderr = self.run_adb_command("shell am force-stop org.rockbox")
            if not success:
                self.status_var.set(f"Failed to stop Rockbox: {stderr}")
                debug_print(f"Failed to stop Rockbox: {stderr}")
                messagebox.showerror("Error", f"Failed to stop Rockbox: {stderr}")
                return
            
            # Wait a moment for the app to fully stop
            time.sleep(1)
            
            # Launch Rockbox
            success, stdout, stderr = self.run_adb_command("shell monkey -p org.rockbox -c android.intent.category.LAUNCHER 1")
            if success:
                self.status_var.set("Rockbox restarted")
                debug_print("Rockbox restarted successfully")
            else:
                self.status_var.set(f"Failed to restart Rockbox: {stderr}")
                debug_print(f"Failed to restart Rockbox: {stderr}")
                messagebox.showerror("Error", f"Failed to restart Rockbox: {stderr}")
        except Exception as e:
            debug_print(f"Error restarting Rockbox: {e}")
            messagebox.showerror("Error", f"Failed to restart Rockbox: {e}")
    
    def repair_device(self):
        """Repair device by removing Rockbox and installing stock ROM"""
        try:
            if not self.device_connected:
                messagebox.showerror("No Device Connected", "No device is currently connected via ADB.")
                return
            
            # Show confirmation dialog
            result = messagebox.askyesno(
                "Repair Device", 
                "This will:\n\n"
                "1. Uninstall Rockbox (if present)\n"
                "2. Remove Rockbox directories from device\n"
                "3. Install stock ROM firmware\n\n"
                "This process will erase all data on your device.\n\n"
                "Do you want to continue?"
            )
            
            if not result:
                return
            
            # Create progress dialog
            dialog, status_label, ok_button, progress_bar, text_widget = self.show_firmware_progress_modal("Device Repair Progress")
            progress_bar = ttk.Progressbar(dialog, mode="indeterminate")
            progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
            progress_bar.start()
            
            def do_repair():
                try:
                    # Step 1: Uninstall Rockbox
                    status_label.config(text="Uninstalling Rockbox...")
                    dialog.update()
                    
                    try:
                        self.run_adb_command("shell pm uninstall org.rockbox")
                        debug_print("Rockbox uninstalled successfully")
                    except Exception as e:
                        debug_print(f"Rockbox not installed or uninstall failed: {e}")
                    
                    # Step 2: Remove Rockbox directories
                    status_label.config(text="Removing Rockbox directories...")
                    dialog.update()
                    
                    rockbox_paths = [
                        "/sdcard/rockbox",
                        "/sdcard/Android/data/org.rockbox",
                        "/storage/sdcard0/rockbox",
                        "/storage/sdcard1/rockbox"
                    ]
                    
                    for path in rockbox_paths:
                        try:
                            self.run_adb_command(f"shell rm -rf {path}")
                            debug_print(f"Removed {path}")
                        except Exception as e:
                            debug_print(f"Could not remove {path}: {e}")
                    
                    # Step 3: Get stock ROM info from manifest
                    status_label.config(text="Fetching stock ROM information...")
                    dialog.update()
                    
                    # Refresh cache and get manifest
                    self.refresh_cache_if_needed()
                    manifest_content = self.get_cached_manifest()
                    
                    if not manifest_content:
                        # Try to download fresh manifest
                        try:
                            response = self._make_github_request_with_retries(self.manifest_url)
                            if response and response.status_code == 200:
                                manifest_content = response.text
                        except Exception as e:
                            debug_print(f"Error downloading manifest: {e}")
                    
                    if not manifest_content:
                        raise Exception("Could not get manifest content")
                    
                    # Parse manifest to find stock ROM
                    firmware_options = self.parse_firmware_manifest(manifest_content)
                    stock_rom = None
                    
                    for firmware in firmware_options:
                        if 'stock' in firmware.get('name', '').lower() or 'y1-stock-rom' in firmware.get('repo', '').lower():
                            stock_rom = firmware
                            break
                    
                    if not stock_rom:
                        # Fallback: create stock ROM info manually
                        stock_rom = {
                            'name': 'Stock ROM',
                            'repo': 'team-slide/y1-stock-rom',
                            'url': 'https://github.com/team-slide/y1-stock-rom/releases/latest',
                            'handler': 'Firmware'
                        }
                    
                    # Step 4: Install stock ROM
                    status_label.config(text="Installing stock ROM...")
                    dialog.update()
                    
                    # Use the existing firmware installation flow
                    self._download_and_flash_selected_firmware(stock_rom)
                    
                    # Close the repair dialog
                    dialog.destroy()
                    
                    messagebox.showinfo("Repair Complete", "Device repair completed successfully!")
                    
                except Exception as e:
                    debug_print(f"Error during device repair: {e}")
                    dialog.destroy()
                    messagebox.showerror("Repair Failed", f"Device repair failed: {e}")
            
            # Run repair in background thread
            import threading
            repair_thread = threading.Thread(target=do_repair, daemon=True)
            repair_thread.start()
            
        except Exception as e:
            debug_print(f"Error starting device repair: {e}")
            messagebox.showerror("Error", f"Failed to start device repair: {e}")
    
    def cleanup(self):
        """Clean up resources before closing"""
        debug_print("Cleaning up resources")
        try:
            # Stop capture
            self.is_capturing = False
            debug_print("Screen capture stopped")
        except Exception as e:
            debug_print(f"Cleanup error: {e}")
    
    def on_closing(self):
        """Handle window closing"""
        debug_print("Window closing")
        # Save startup tracking before closing
        self.save_startup_tracking()
        self.cleanup()
        self.quit()

    def _input_paced(self):
        import time
        now = time.time()
        if now - self.last_input_time < self.input_pacing_interval:
            debug_print(f"Input paced: {now - self.last_input_time:.3f}s < {self.input_pacing_interval}s")
            return False
        self.last_input_time = now
        
        # Track user activity
        self.last_user_activity = now
        debug_print(f"User activity detected, resetting inactivity timer")
        
        return True

    def _add_tooltip(self, widget, text):
        # Simple tooltip for Tkinter widgets
        tooltip = tk.Toplevel(widget)
        tooltip.withdraw()
        tooltip.overrideredirect(True)
        label = tk.Label(tooltip, text=text, background="#fff", relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9), wraplength=320, justify=tk.LEFT)
        label.pack(ipadx=4, ipady=2)
        def enter(event):
            try:
                if widget.winfo_exists():
                    x = widget.winfo_rootx() + 20
                    y = widget.winfo_rooty() + 20
                    tooltip.geometry(f"+{x}+{y}")
                    tooltip.deiconify()
            except:
                pass
        def leave(event):
            try:
                if tooltip.winfo_exists():
                    tooltip.withdraw()
            except:
                pass
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
    
    def safe_ui_update(self, widget, method, *args, **kwargs):
        """Safely update a UI widget, checking if it exists first"""
        try:
            if widget and widget.winfo_exists():
                if method == "config":
                    widget.config(*args, **kwargs)
                elif method == "pack":
                    widget.pack(*args, **kwargs)
                elif method == "pack_forget":
                    widget.pack_forget()
                elif method == "place":
                    widget.place(*args, **kwargs)
                elif method == "grid":
                    widget.grid(*args, **kwargs)
                else:
                    getattr(widget, method)(*args, **kwargs)
        except Exception as e:
            debug_print(f"Safe UI update failed for {widget}: {e}")
    
    def safe_after(self, widget, delay, callback, *args):
        """Safely schedule an after callback, checking if widget exists"""
        try:
            if widget and widget.winfo_exists():
                widget.after(delay, callback, *args)
        except Exception as e:
            debug_print(f"Safe after failed for {widget}: {e}")
    
    def _should_show_launcher_toggle(self, package_name):
        # Show toggle if .y1 or .y1app in package name
        result = package_name and (".y1" in package_name or ".y1app" in package_name)
        debug_print(f"Should show launcher toggle for {package_name}: {result}")
        return result
    
    def _should_auto_enable_scroll_wheel(self, package_name):
        """Check if scroll wheel mode should be automatically enabled for this app"""
        # Auto-enable for org.rockbox and Y1 apps
        auto_enable = (package_name == "org.rockbox" or 
                      (package_name and (".y1" in package_name or ".y1app" in package_name)))
        debug_print(f"Should auto-enable scroll wheel for {package_name}: {auto_enable}")
        return auto_enable
    
    def show_scroll_cursor(self):
        """Show wait cursor when scrolling in scroll wheel mode (very brief)"""
        if not self.scroll_wheel_mode_var.get():
            return  # Only show in scroll wheel mode
        
        # Don't change cursor if ready placeholder is being shown
        if self.ready_placeholder_shown:
            return
        
        # Cancel any existing timer
        if self.scroll_cursor_timer:
            self.after_cancel(self.scroll_cursor_timer)
        
        # Set wait cursor
        if platform.system() == "Windows":
            self.screen_canvas.config(cursor="wait")  # Windows wait cursor
        else:
            self.screen_canvas.config(cursor="")  # Normal cursor on other platforms
        
        self.scroll_cursor_active = True
        debug_print("Scroll cursor shown")
        
        # Set timer to restore normal cursor (very brief - UI should feel responsive)
        self.scroll_cursor_timer = self.after(self.scroll_cursor_duration, self.hide_scroll_cursor)
    
    def hide_scroll_cursor(self):
        """Hide scroll cursor and restore normal cursor"""
        self.scroll_cursor_active = False
        self.scroll_cursor_timer = None
        
        # Don't change cursor if ready placeholder is being shown
        if self.ready_placeholder_shown:
            return
        
        # Restore the appropriate cursor
        if self.scroll_wheel_mode_var.get():
            self.screen_canvas.config(cursor="")  # Regular cursor for scroll wheel mode
        else:
            self.screen_canvas.config(cursor="hand2")  # Pointing hand for touch mode
        
        debug_print("Scroll cursor hidden")
    
    def take_screenshot(self):
        """Capture the latest framebuffer and save it to a user-selected location"""
        debug_print("Taking screenshot")
        
        if not self.device_connected:
            messagebox.showwarning("Device Not Connected", 
                                 "Cannot take screenshot: Device is not connected.\n\n"
                                 "Please ensure your Y1 device is connected via USB and ADB is working.")
            return
        
        if not hasattr(self, 'last_screen_image') or self.last_screen_image is None:
            messagebox.showwarning("No Screen Data", 
                                 "Cannot take screenshot: No screen data available.\n\n"
                                 "Please wait for the device screen to load or try refreshing.")
            return
        
        try:
            # Generate default filename with timestamp
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"Y1_Screenshot_{timestamp}.png"
            
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                title="Save Screenshot",
                defaultextension=".png",
                filetypes=[
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg"),
                    ("All files", "*.*")
                ],
                initialfile=default_filename
            )
            
            if not file_path:
                debug_print("Screenshot cancelled by user")
                return
            
            # Get the last screen image (full resolution, not scaled)
            screenshot_img = self.last_screen_image.copy()
            
            # Apply the same cropping as the display (remove status bar if present)
            if screenshot_img.height > 50:
                def has_black_status_bar(img):
                    import numpy as np
                    arr = np.array(img)
                    if arr.shape[0] < 50:
                        return False
                    top = arr[:25, :, :3]
                    return (top.mean() < 16)
                
                if has_black_status_bar(screenshot_img):
                    screenshot_img = screenshot_img.crop((0, 25, screenshot_img.width, screenshot_img.height))
                    debug_print("Cropped black status bar from screenshot")
            
            # Save the screenshot
            screenshot_img.save(file_path, quality=95)
            
            # Show success message
            self.status_var.set(f"Screenshot saved: {os.path.basename(file_path)}")
            messagebox.showinfo("Screenshot Saved", 
                              f"Screenshot saved successfully!\n\n"
                              f"File: {os.path.basename(file_path)}\n"
                              f"Location: {os.path.dirname(file_path)}\n\n"
                              f"Resolution: {screenshot_img.width}x{screenshot_img.height}")
            
            debug_print(f"Screenshot saved to: {file_path}")
            
        except Exception as e:
            debug_print(f"Screenshot error: {e}")
            messagebox.showerror("Screenshot Error", 
                               f"Failed to save screenshot:\n\n{str(e)}\n\n"
                               "Please try again or check if the selected location is writable.")
            self.status_var.set("Screenshot failed")

    def on_nav_bar_click(self, event):
        """Handle clicks on the virtual nav bar: left=back, right=home"""
        debug_print(f"Nav bar click at ({event.x}, {event.y})")
        canvas_height = int(self.screen_canvas.cget('height'))
        nav_y = canvas_height - self.nav_bar_height
        if event.y >= nav_y:
            if event.x < self.display_width // 2:
                # Left half: Back (circle)
                debug_print("Nav bar: sending BACK key")
                self.run_adb_command('shell input keyevent 4')  # KEYCODE_BACK
                self.status_var.set('Back button (virtual nav bar) pressed')
            else:
                # Right half: Home (triangle)
                debug_print("Nav bar: sending HOME key")
                self.run_adb_command('shell input keyevent 3')  # KEYCODE_HOME
                self.status_var.set('Home button (virtual nav bar) pressed')
            
            # Request framebuffer refresh after sending input (non-blocking)
            self.after(50, self.force_framebuffer_refresh)
        else:
            debug_print("Click not in nav bar area")

    def show_context_menu(self, x, y):
        self.context_menu.tk_popup(x, y)

    def show_recent_apps(self):
        debug_print("Showing recent apps")
        self.run_adb_command("shell input keyevent 187")  # KEYCODE_APP_SWITCH
        self.status_var.set("Recent Apps opened")
        debug_print("Recent apps key sent")

    def toggle_debug_menu(self, event=None):
        """Toggle debug menu visibility with Ctrl+D"""
        try:
            # Get the menubar
            menubar = self.nametowidget(self.cget("menu"))
            
            # Check if debug menu is already visible
            debug_visible = False
            for i in range(menubar.index('end') + 1):
                try:
                    if menubar.entrycget(i, 'label') == 'Debug':
                        debug_visible = True
                        break
                except:
                    continue
            
            if debug_visible:
                # Remove debug menu
                for i in range(menubar.index('end') + 1):
                    try:
                        if menubar.entrycget(i, 'label') == 'Debug':
                            menubar.delete(i)
                            break
                    except:
                        continue
            else:
                # Add debug menu
                menubar.add_cascade(label="Debug", menu=self.debug_menu)
                self.apply_menu_colors()
                
        except Exception as e:
            debug_print(f"Error toggling debug menu: {e}")

    def change_update_branch(self):
        """Change the update branch via dialog"""
        try:
            # Read current branch
            current_branch = "master"
            branch_path = os.path.join(assets_dir, "branch.txt")
            if os.path.exists(branch_path):
                with open(branch_path, 'r', encoding='utf-8') as f:
                    current_branch = f.read().strip() or "master"
            
            # Show dialog to change branch
            new_branch = simpledialog.askstring(
                "Change Update Branch",
                f"Enter the branch name for updates:\n\nCurrent branch: {current_branch}",
                initialvalue=current_branch
            )
            
            if new_branch and new_branch.strip():
                new_branch = new_branch.strip()
                with open(branch_path, 'w', encoding='utf-8') as f:
                    f.write(new_branch)
                
                messagebox.showinfo(
                    "Branch Updated",
                    f"Update branch changed to: {new_branch}\n\nThis will be used by the updater for future updates."
                )
                debug_print(f"Update branch changed to: {new_branch}")
            else:
                debug_print("Branch change cancelled")
                
        except Exception as e:
            debug_print(f"Error changing update branch: {e}")
            messagebox.showerror("Error", f"Failed to change update branch: {e}")

    def show_current_branch(self):
        """Show the current update branch"""
        try:
            current_branch = "master"
            branch_path = os.path.join(assets_dir, "branch.txt")
            if os.path.exists(branch_path):
                with open(branch_path, 'r', encoding='utf-8') as f:
                    current_branch = f.read().strip() or "master"
            
            messagebox.showinfo(
                "Current Update Branch",
                f"Current update branch: {current_branch}\n\nUse Ctrl+D ? Change Update Branch to modify this."
            )
            debug_print(f"Current update branch: {current_branch}")
            
        except Exception as e:
            debug_print(f"Error showing current branch: {e}")
            messagebox.showerror("Error", f"Failed to read current branch: {e}")

    def run_updater(self):
        """Run the Y1 updater"""
        try:
            debug_print("Launching Y1 updater")
            subprocess.Popen([sys.executable, os.path.join(assets_dir, "y1_updater.py")])
            self.status_var.set("Updater launched")
            debug_print("Y1 updater launched successfully")
        except Exception as e:
            debug_print(f"Error launching updater: {e}")
            messagebox.showerror("Error", f"Failed to launch updater: {e}")

    def setup_bindings(self):
        debug_print("Setting up key bindings")
        # Global key bindings
        self.bind("<Alt_L>", self.toggle_launcher_control)
        self.bind("<Alt_R>", self.toggle_launcher_control)
        
        # Debug menu toggle with Ctrl+D
        self.bind("<Control-d>", self.toggle_debug_menu)
        self.bind("<Control-D>", self.toggle_debug_menu)
        
        # File Explorer with Ctrl+F (hidden from menu)
        self.bind("<Control-f>", lambda e: self.open_file_explorer())
        self.bind("<Control-F>", lambda e: self.open_file_explorer())
        
        # Global key handling for all key presses
        self.bind_all("<Key>", self.on_key_press)
        # Global key release handling for cursor control
        self.bind_all("<KeyRelease>", self.on_key_release)
        debug_print("Key bindings set up complete")
        
        # Initialize update system
        self.initialize_update_system()
    
    def initialize_update_system(self):
        """Initialize the update system with background checks and UI elements"""
        debug_print("Initializing update system...")
        
        # Show patch status if patches were applied
        if self.patches_applied:
            self.show_patch_status_message()
        
        # Schedule background update check
        self.after(5000, self.background_update_check)  # Check after 5 seconds
        
        # Schedule periodic update checks
        self.after(self.update_check_interval, self.periodic_update_check)
        
        debug_print("Update system initialized")
    
    def background_update_check(self):
        """Background update check that runs once at startup with API call optimization"""
        try:
            debug_print("Running background update check...")
            
            # Check if we should skip API calls due to recent startup
            if self.should_skip_api_checks():
                debug_print("Skipping background update check due to recent startup")
                return
            
            # Update last API check time
            self.last_api_check_time = datetime.datetime.now()
            self.save_startup_tracking()
            
            # Refresh cache in background only if needed
            try:
                if self.should_refresh_cache():
                    self.refresh_cache_if_needed()
                    self.last_cache_refresh_time = datetime.datetime.now()
                    self.save_startup_tracking()
                    debug_print("Cache refreshed in background")
                else:
                    debug_print("Cache refresh not needed, using existing cache")
                    
            except Exception as e:
                debug_print(f"Background cache refresh failed: {e}")
            
            update_info = self.check_for_team_slide_updates()
            
            if update_info:
                self.update_available = True
                self.update_info = update_info
                debug_print(f"Update available: {update_info['version']}")
                
                # Show update prompt dialog
                self.after(1000, lambda: self.show_team_slide_update_prompt(update_info))
                
                # Show update button in UI
                self.after(2000, self.show_update_pill_if_needed)
            else:
                debug_print("No updates available")
                
        except Exception as e:
            debug_print(f"Background update check failed: {e}")
    
    def periodic_update_check(self):
        """Periodic update check that runs every 15 minutes with API call optimization"""
        try:
            debug_print("Running periodic update check...")
            
            # Check if we should skip API calls due to recent startup
            if self.should_skip_api_checks():
                debug_print("Skipping periodic update check due to recent startup")
                # Schedule next check
                self.after(self.update_check_interval, self.periodic_update_check)
                return
            
            # Update last API check time
            self.last_api_check_time = datetime.datetime.now()
            self.save_startup_tracking()
            
            # Refresh cache periodically only if needed
            try:
                if self.should_refresh_cache():
                    self.refresh_cache_if_needed()
                    self.last_cache_refresh_time = datetime.datetime.now()
                    self.save_startup_tracking()
                    debug_print("Cache refreshed in periodic check")
                else:
                    debug_print("Cache refresh not needed in periodic check")
            except Exception as e:
                debug_print(f"Periodic cache refresh failed: {e}")
            
            # Periodic cache cleanup to prevent over-reliance on cached data
            try:
                self.cleanup_cache_directory()
                debug_print("Periodic cache cleanup completed")
            except Exception as e:
                debug_print(f"Periodic cache cleanup failed: {e}")
            
            update_info = self.check_for_team_slide_updates()
            
            if update_info and not self.update_available:
                self.update_available = True
                self.update_info = update_info
                debug_print(f"New update available: {update_info['version']}")
                
                # Show update prompt dialog
                self.show_team_slide_update_prompt(update_info)
                
                # Show update button in UI
                self.show_update_pill_if_needed
            
            # Schedule next check
            self.after(self.update_check_interval, self.periodic_update_check)
            
        except Exception as e:
            debug_print(f"Periodic update check failed: {e}")
            # Schedule next check even if this one failed
            self.after(self.update_check_interval, self.periodic_update_check)

    def _destroy_splash(self):
        if hasattr(self, '_splash') and self._splash.winfo_exists():
            self._splash.destroy()

    def show_firmware_progress_modal(self, title="Firmware Flash Progress"):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("600x400")  # Increased height to accommodate text widget
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Apply theme colors to dialog
        self.apply_dialog_theme(dialog)
        
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Status label at the top
        status_label = ttk.Label(frame, text="", font=("Segoe UI", 11), wraplength=560, justify=tk.CENTER)
        status_label.pack(fill=tk.X, pady=(0, 10))
        
        # Progress bar
        progress_bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
        progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Text widget for flash tool output with scrollbar
        output_frame = ttk.Frame(frame)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create text widget with scrollbar
        text_widget = tk.Text(output_frame, height=12, font=("Consolas", 9), wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Apply theme colors to text widget
        try:
            if hasattr(self, 'bg_color') and hasattr(self, 'fg_color'):
                text_widget.configure(bg=self.bg_color, fg=self.fg_color, insertbackground=self.fg_color)
        except Exception as e:
            debug_print(f"Could not apply theme to text widget: {e}")
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # OK button at the bottom
        ok_button = ttk.Button(frame, text="OK", command=dialog.destroy, state=tk.DISABLED)
        ok_button.pack(pady=(10, 5))
        
        return dialog, status_label, ok_button, progress_bar, text_widget

    def install_firmware(self, local_file=None):
        """Unified firmware flashing: handles both manifest and local file, always uses _download_and_flash_selected_firmware for robust debug and error handling."""
        debug_print(f"install_firmware called with local_file={local_file}")
        
        # Mark that user triggered a cache refresh
        self.user_triggered_cache_refresh = True
        
        if local_file:
            # Clear ROM directory before local firmware installation
            self.clear_rom_directory_for_firmware()
            
            # Treat local file as a firmware_info dict with a 'url' key
            firmware_info = {'url': local_file}
            self._download_and_flash_selected_firmware(firmware_info)
        else:
            # Refresh cache if needed and rebuild file URLs
            self.refresh_cache_if_needed()
            
            debug_print(f"Attempting to download manifest from: {self.manifest_url}")
            try:
                # Try to get manifest content with fallback to cache
                manifest_content = None
                
                # Method 1: Try to download fresh manifest
                try:
                    debug_print("Attempting to download fresh manifest...")
                    response = self._make_github_request_with_retries(self.manifest_url)
                    if response and response.status_code == 200:
                        manifest_content = response.text
                        debug_print("Fresh manifest downloaded successfully")
                        # Update cache with fresh manifest and rebuild file URLs
                        try:
                            self.build_cache_index_with_releases(manifest_content)
                            debug_print("Cache updated with fresh manifest and file URLs")
                        except Exception as e:
                            debug_print(f"Cache update failed: {e}")
                    else:
                        debug_print("Fresh manifest download failed, using cache")
                except Exception as e:
                    debug_print(f"Error downloading fresh manifest: {e}")
                
                # Method 2: Fallback to cached manifest
                if not manifest_content:
                    debug_print("Using cached manifest...")
                    manifest_content = self.get_cached_manifest()
                
                if not manifest_content:
                    debug_print("No manifest content available from any source")
                    self.show_firmware_selection_dialog_with_error("Unable to load firmware listing. Please check your internet connection and try again.")
                    return
                
                firmware_options = self.parse_firmware_manifest(manifest_content)
                if not firmware_options:
                    # Show error message inline in the firmware selection dialog
                    self.show_firmware_selection_dialog_with_error("No firmware currently available. Firmware will appear here once they are published to the Slidia repository.")
                    return
                selected_firmware = self.show_firmware_selection_dialog(firmware_options)
                if not selected_firmware:
                    return
                self._download_and_flash_selected_firmware(selected_firmware)
            except Exception as e:
                debug_print(f"Exception while downloading or parsing manifest: {e}")
                messagebox.showerror("Manifest Error", f"Failed to download or parse manifest: {e}")

    def browse_firmware_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Firmware File",
            filetypes=[("Firmware files", "*.img"), ("All files", "*.")]
        )
        if not file_path:
            return
        # Custom popup with 'Continue' button
        root = self if isinstance(self, tk.Tk) else tk.Tk()
        popup = tk.Toplevel(root)
        popup.title("Unplug Device")
        popup.geometry("400x120")
        popup.transient(root)
        popup.grab_set()
        msg = ttk.Label(popup, text="Please turn off and unplug your Y1, then click Continue to proceed.", font=("Segoe UI", 10), wraplength=380, justify=tk.CENTER)
        msg.pack(pady=(20, 10), padx=10)
        btn = ttk.Button(popup, text="Continue", command=popup.destroy)
        btn.pack(pady=(0, 15))
        popup.wait_window()
        self.install_firmware(local_file=file_path)

    def install_firmware_with_local_file(self, file_path):
        """Deprecated: Use install_firmware(local_file=...) instead for unified workflow."""
        debug_print("install_firmware_with_local_file is deprecated. Use install_firmware(local_file=...) instead.")
        self.install_firmware(local_file=file_path)

    def _prepare_rom_files(self, firmware_dir, dialog, status_label, progress_bar):
        """
        Replace pre-populated ROM files with downloaded files and run flash_tool.exe.
        
        This function:
        1. Replaces files in the ROM directory with downloaded files (if available)
        2. Ensures system.img comes from the downloaded ROM
        3. Runs flash_tool.exe -c -d -f install_rom.xml
        
        The ROM directory is pre-populated at app startup, so this function just handles
        file replacement and flash tool execution.
        """
        try:
            debug_print(f"Preparing ROM files in: {firmware_dir}")
            dialog.after(0, status_label.config, {"text": "Preparing ROM files..."})
            
            # Ensure ROM directory exists
            os.makedirs(firmware_dir, exist_ok=True)
            
            # Log what files are currently in the ROM directory
            debug_print(f"Files currently in ROM directory {firmware_dir}:")
            existing_files = []
            if os.path.exists(firmware_dir):
                for file in os.listdir(firmware_dir):
                    file_path = os.path.join(firmware_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        debug_print(f"  {file} ({file_size} bytes)")
                        existing_files.append(file)
                    else:
                        debug_print(f"  {file} (directory)")
            else:
                debug_print("  ROM directory does not exist yet")
            
            # Check if system.img exists (should come from downloaded ROM)
            system_img_path = os.path.join(firmware_dir, "system.img")
            if not os.path.exists(system_img_path):
                debug_print("Warning: system.img not found - this should come from the downloaded ROM")
                dialog.after(0, status_label.config, {"text": "Warning: system.img not found in downloaded ROM"})
                return False
            
            debug_print(f"ROM preparation completed: {len(existing_files)} files present")
            dialog.after(0, status_label.config, {"text": f"ROM files prepared successfully ({len(existing_files)} files)"})
            
            # Run flash_tool.exe -c -d -f install_rom.xml
            def run_flash_tool():
                try:
                    debug_print("Running flash_tool.exe -c -d -f install_rom.xml...")
                    flash_tool_path = os.path.join(self.base_dir, "assets", "flash_tool.exe")
                    install_rom_xml = os.path.join(firmware_dir, "install_rom.xml")
                    
                    if not os.path.exists(flash_tool_path):
                        debug_print("flash_tool.exe not found in assets directory")
                        return
                    
                    if not os.path.exists(install_rom_xml):
                        debug_print("install_rom.xml not found in ROM directory")
                        return
                    
                    # Run flash tool in assets directory with correct syntax for SP Flash Tool 5.1904
                    import subprocess
                    assets_dir_path = os.path.join(self.base_dir, "assets")
                    scatter_file = os.path.join(assets_dir_path, "rom", "MT6572_Android_scatter.txt")
                    
                    # SP Flash Tool 5.1904 syntax: flash_tool -c download -s scatter_file
                    cmd = [flash_tool_path, "-c", "download", "-s", scatter_file]
                    debug_print(f"Running command: {' '.join(cmd)} in {assets_dir_path}")
                    
                    result = subprocess.run(cmd, cwd=assets_dir_path, capture_output=True, text=True, timeout=300)
                    debug_print(f"Flash tool output: {result.stdout}")
                    if result.stderr:
                        debug_print(f"Flash tool errors: {result.stderr}")
                    
                    debug_print(f"Flash tool completed with return code: {result.returncode}")
                    
                except Exception as e:
                    debug_print(f"Error running flash_tool.exe: {e}")
            
            # Run flash tool in a separate thread to avoid blocking UI
            import threading
            flash_thread = threading.Thread(target=run_flash_tool, daemon=True)
            flash_thread.start()
            
            return True
                
        except Exception as e:
            debug_print(f"Error preparing ROM files: {e}")
            dialog.after(0, status_label.config, {"text": f"Error preparing ROM files: {e}"})
            return False

    def _download_and_flash_selected_firmware(self, firmware_info):
        self.is_flashing_firmware = True
        try:
            firmware_dir = os.path.join(assets_dir, "rom")
            
            # Clear ROM directory before firmware download to prevent contamination
            self.clear_rom_directory_for_firmware()
            
            os.makedirs(firmware_dir, exist_ok=True)
            dialog = tk.Toplevel(self)
            dialog.title("Firmware Flash Progress")
            dialog.geometry("600x400")
            dialog.transient(self)
            dialog.grab_set()
            dialog.resizable(False, False)
            frame = ttk.Frame(dialog, padding="20")
            frame.pack(fill=tk.BOTH, expand=True)
            status_label = ttk.Label(frame, text="", font=("Segoe UI", 11), wraplength=560, justify=tk.CENTER)
            status_label.pack(fill=tk.X, pady=(0, 5))
            warn_label = ttk.Label(frame, text="Please make sure your Y1 is turned off and disconnected.", font=("Segoe UI", 9), foreground="#d9534f")
            warn_label.pack(fill=tk.X, pady=(0, 10))
            ok_button = ttk.Button(frame, text="OK", command=dialog.destroy, state=tk.DISABLED)
            ok_button.pack(pady=(10, 5))
            progress_bar = ttk.Progressbar(frame, mode="indeterminate")
            progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
            progress_bar.stop()  # Only start after download
            
            def do_download_and_flash():
                try:
                    repo_url = firmware_info['url']
                    # Check if we have cached file URLs for this firmware
                    cached_files = firmware_info.get('cached_files', [])
                    
                    # Look for rom.zip or system.img in cached files first
                    if cached_files:
                        rom_zip_file = None
                        system_img_file = None
                        
                        for file_info in cached_files:
                            if file_info.get('name', '').lower() == 'rom.zip':
                                rom_zip_file = file_info
                            elif file_info.get('name', '').lower() == 'system.img':
                                system_img_file = file_info
                        
                        if rom_zip_file:
                            # Download rom.zip from cached URL
                            download_url = rom_zip_file['url']
                            zip_path = os.path.join(firmware_dir, 'rom.zip')
                            dialog.after(0, status_label.config, {"text": "Downloading firmware files..."})
                            
                            response = requests.get(download_url, stream=True, timeout=60)
                            response.raise_for_status()
                            file_size = int(response.headers.get('content-length', 0))
                            downloaded = 0
                            progress_bar.config(mode='determinate', maximum=file_size)
                            
                            with open(zip_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    percent = (downloaded / file_size) * 100 if file_size else 0
                                    dialog.after(0, status_label.config, {"text": f"Downloading firmware files... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
                                    dialog.after(0, progress_bar.step, (len(chunk),))
                            
                            dialog.after(0, lambda: progress_bar.config(value=0))
                            
                            # Extract rom.zip
                            dialog.after(0, status_label.config, {"text": "Extracting rom.zip..."})
                            progress_bar.config(mode='indeterminate')
                            progress_bar.start()
                            
                            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                zip_ref.extractall(firmware_dir)
                            
                            # Clean up the zip file
                            os.remove(zip_path)
                            
                            # Prepare all required ROM files
                            if not self._prepare_rom_files(firmware_dir, dialog, status_label, progress_bar):
                                dialog.after(0, status_label.config, {"text": "Failed to prepare ROM files. Aborting."})
                                dialog.after(0, ok_button.config, {"state": "normal"})
                                return
                            
                            dialog.after(0, warn_label.pack_forget)
                            dialog.after(0, status_label.config, {"text": "Please connect your device and wait a few minutes."})
                            time.sleep(1.0)
                            debug_print(f"Starting flash with rom directory: {firmware_dir}")
                            self._flash_with_modal(dialog, status_label, ok_button, firmware_dir, progress_bar)
                            return
                        
                        elif system_img_file:
                            # Download system.img directly from cached URL
                            download_url = system_img_file['url']
                            system_img_path = os.path.join(firmware_dir, 'system.img')
                            dialog.after(0, status_label.config, {"text": "Downloading firmware files..."})
                            
                            response = requests.get(download_url, stream=True, timeout=60)
                            response.raise_for_status()
                            file_size = int(response.headers.get('content-length', 0))
                            downloaded = 0
                            progress_bar.config(mode='determinate', maximum=file_size)
                            
                            with open(system_img_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    percent = (downloaded / file_size) * 100 if file_size else 0
                                    dialog.after(0, status_label.config, {"text": f"Downloading firmware files... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
                                    dialog.after(0, progress_bar.step, (len(chunk),))
                            
                            dialog.after(0, lambda: progress_bar.config(value=0))
                            
                            # Prepare all required ROM files
                            if not self._prepare_rom_files(firmware_dir, dialog, status_label, progress_bar):
                                dialog.after(0, status_label.config, {"text": "Failed to prepare ROM files. Aborting."})
                                dialog.after(0, ok_button.config, {"state": "normal"})
                                return
                            
                            dialog.after(0, warn_label.pack_forget)
                            dialog.after(0, status_label.config, {"text": "Please connect your device and wait a few minutes."})
                            time.sleep(1.0)
                            debug_print(f"Starting flash with rom directory: {firmware_dir}")
                            self._flash_with_modal(dialog, status_label, ok_button, firmware_dir, progress_bar)
                            return
                    
                    # Fallback to original method if no cached files or no suitable files found
                    # Download all .img and .bin assets from the release
                    downloaded_files = {}
                    if 'github.com' in repo_url and ('/releases/latest' in repo_url or '/releases/' in repo_url or repo_url.rstrip('/').endswith('/releases')):
                        if '/releases/latest' in repo_url:
                            repo_path = repo_url.replace('https://github.com/', '').replace('/releases/latest', '')
                            api_url = f"https://api.github.com/repos/{repo_path}/releases/latest"
                        elif '/releases/' in repo_url or repo_url.rstrip('/').endswith('/releases'):
                            # Handle /releases/ or /releases
                            repo_path = repo_url.replace('https://github.com/', '').replace('/releases/', '').replace('/releases', '')
                            api_url = f"https://api.github.com/repos/{repo_path}/releases/latest"
                        r = requests.get(api_url)
                        release_data = r.json()
                        assets = release_data.get('assets', [])
                        
                        # Check if rom.zip is available
                        rom_zip_asset = None
                        for asset in assets:
                            if asset['name'] == 'rom.zip':
                                rom_zip_asset = asset
                                break
                        
                        if rom_zip_asset:
                            # Download only rom.zip
                            download_url = rom_zip_asset['browser_download_url']
                            zip_path = os.path.join(firmware_dir, 'rom.zip')
                            dialog.after(0, status_label.config, {"text": "Downloading firmware files..."})
                            
                            # Use comprehensive retry mechanism for file download
                            response = self._make_github_request_with_retries(download_url, stream=True)
                            response.raise_for_status()
                            file_size = int(response.headers.get('content-length', 0))
                            downloaded = 0
                            progress_bar.config(mode='determinate', maximum=file_size)
                            with open(zip_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    percent = (downloaded / file_size) * 100 if file_size else 0
                                    dialog.after(0, status_label.config, {"text": f"Downloading firmware files... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
                                    dialog.after(0, progress_bar.step, (len(chunk),))
                            dialog.after(0, lambda: progress_bar.config(value=0))
                            
                            # Extract rom.zip
                            dialog.after(0, status_label.config, {"text": "Extracting firmware files..."})
                            progress_bar.config(mode='indeterminate')
                            progress_bar.start()
                            
                            try:
                                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                    zip_ref.extractall(firmware_dir)
                                
                                # Get list of extracted files
                                extracted_files = []
                                for root, dirs, files in os.walk(firmware_dir):
                                    for file in files:
                                        if file != 'rom.zip':  # Exclude the zip file itself
                                            extracted_files.append(file)
                                            # Add to downloaded_files with correct path
                                            if file.endswith('.img') or file.endswith('.bin'):
                                                downloaded_files[file] = os.path.join(root, file)
                                                debug_print(f"Found firmware file: {file} at {os.path.join(root, file)}")
                                
                                debug_print(f"Total extracted files: {len(extracted_files)}")
                                debug_print(f"Firmware files found: {list(downloaded_files.keys())}")
                                
                                # Clean up the zip file
                                os.remove(zip_path)
                                
                            except Exception as e:
                                dialog.after(0, status_label.config, {"text": f"Error extracting rom.zip: {e}"})
                                dialog.after(0, ok_button.config, {"state": "normal"})
                                return
                            
                            progress_bar.stop()
                            
                        else:
                            # Fall back to downloading individual files
                            for asset in assets:
                                name = asset['name']
                                if name.endswith('.img') or name.endswith('.bin'):
                                    download_url = asset['browser_download_url']
                                    dest_path = os.path.join(firmware_dir, name)
                                    dialog.after(0, status_label.config, {"text": "Downloading firmware files..."})
                                    
                                    # Use comprehensive retry mechanism for file download
                                    response = self._make_github_request_with_retries(download_url, stream=True)
                                    response.raise_for_status()
                                    file_size = int(response.headers.get('content-length', 0))
                                    downloaded = 0
                                    progress_bar.config(mode='determinate', maximum=file_size)
                                    with open(dest_path, 'wb') as f:
                                        for chunk in response.iter_content(chunk_size=8192):
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                            downloaded += len(chunk)
                                            percent = (downloaded / file_size) * 100 if file_size else 0
                                            dialog.after(0, status_label.config, {"text": f"Downloading firmware files... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
                                            dialog.after(0, progress_bar.step, (len(chunk),))
                                    dialog.after(0, lambda: progress_bar.config(value=0))
                                    downloaded_files[name] = dest_path
                    else:
                        # Direct URL to a single file (legacy/local)
                        name = os.path.basename(repo_url)
                        if name.endswith('.img') or name.endswith('.bin'):
                            dest_path = os.path.join(firmware_dir, name)
                            dialog.after(0, status_label.config, {"text": "Downloading firmware files..."})
                            
                            # Use comprehensive retry mechanism for file download
                            response = self._make_github_request_with_retries(repo_url, stream=True)
                            response.raise_for_status()
                            file_size = int(response.headers.get('content-length', 0))
                            downloaded = 0
                            progress_bar.config(mode='determinate', maximum=file_size)
                            with open(dest_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    percent = (downloaded / file_size) * 100 if file_size else 0
                                    dialog.after(0, status_label.config, {"text": f"Downloading firmware files... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
                                    dialog.after(0, progress_bar.step, (len(chunk),))
                            dialog.after(0, lambda: progress_bar.config(value=0))
                            downloaded_files[name] = dest_path
                    
                    # Check for system.img
                    debug_print(f"Checking for system.img in downloaded_files: {list(downloaded_files.keys())}")
                    if "system.img" not in downloaded_files:
                        debug_print("system.img not found in downloaded_files!")
                        dialog.after(0, status_label.config, {"text": "Error: system.img not found in release. Aborting."})
                        dialog.after(0, ok_button.config, {"state": "normal"})
                        return
                    else:
                        debug_print(f"system.img found at: {downloaded_files['system.img']}")
                    
                    # Prepare all required ROM files
                    if not self._prepare_rom_files(firmware_dir, dialog, status_label, progress_bar):
                        dialog.after(0, status_label.config, {"text": "Failed to prepare ROM files. Aborting."})
                        dialog.after(0, ok_button.config, {"state": "normal"})
                        return
                    
                    dialog.after(0, warn_label.pack_forget)
                    dialog.after(0, status_label.config, {"text": "Please connect your device and wait a few minutes."})
                    time.sleep(1.0)
                    debug_print(f"Starting flash with rom directory: {firmware_dir}")
                    self._flash_with_modal(dialog, status_label, ok_button, firmware_dir, progress_bar)
                    
                except Exception as e:
                    debug_print(f"Exception in do_download_and_flash: {e}")
                    dialog.after(0, status_label.config, {"text": f"Error: {e}"})
                    dialog.after(0, ok_button.config, {"state": "normal"})
            
            threading.Thread(target=do_download_and_flash, daemon=True).start()
            dialog.wait_window()
        finally:
            self.is_flashing_firmware = False

    def _flash_with_modal(self, dialog, status_label, ok_button, rom_dir, progress_bar=None, text_widget=None):
        import subprocess
        import threading
        try:
            debug_print("Entered _flash_with_modal")
            flash_tool_path = os.path.join(assets_dir, "flash_tool.exe")
            install_rom_path = os.path.join(assets_dir, "install_rom.xml")
            debug_print(f"Checking for flash_tool.exe at: {flash_tool_path}")
            if not os.path.exists(flash_tool_path):
                debug_print("flash_tool.exe not found!")
                error_msg = "flash_tool.exe not found in assets directory. Please ensure the flash tool is properly installed."
                dialog.after(0, status_label.config, {"text": error_msg})
                dialog.after(0, ok_button.pack)
                dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                messagebox.showerror("Flash Tool Missing", error_msg)
                return
            debug_print(f"Checking for install_rom.xml at: {install_rom_path}")
            if not os.path.exists(install_rom_path):
                debug_print("install_rom.xml not found!")
                error_msg = "install_rom.xml not found in assets directory. This file is required for firmware installation."
                dialog.after(0, status_label.config, {"text": error_msg})
                dialog.after(0, ok_button.pack)
                dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                messagebox.showerror("Configuration Missing", error_msg)
                return
            if progress_bar is None:
                progress_bar = tk.ttk.Progressbar(dialog, mode="determinate", maximum=100)
                progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
            else:
                progress_bar.config(mode="determinate", maximum=100)
            progress_bar.config(value=0)
            dialog.after(0, ok_button.pack_forget)
            # Run flash tool from assets directory with correct syntax for SP Flash Tool 5.1904
            scatter_file = os.path.join(assets_dir, "rom", "MT6572_Android_scatter.txt")
            
            # SP Flash Tool 5.1904 syntax: flash_tool -c download -s scatter_file
            command = [flash_tool_path, "-c", "download", "-s", scatter_file]
            debug_print(f"About to run flash command: {' '.join(command)} (cwd={assets_dir})")
            debug_print(f"Flash tool path exists: {os.path.exists(flash_tool_path)}")
            debug_print(f"Scatter file exists: {os.path.exists(scatter_file)}")
            def run_flash():
                debug_print("Starting flash_tool.exe subprocess...")
                flash_done = False
                all_done_seen = False
                disconnect_seen = False
                error_seen = False
                
                # Progress timer variables
                start_time = time.time()
                progress_timer = None
                progress_duration = 240  # 4 minutes in seconds
                
                def update_progress():
                    nonlocal progress_timer
                    if flash_done or all_done_seen or error_seen:
                        return
                    
                    # Check if dialog and progress_bar still exist
                    try:
                        if not dialog.winfo_exists() or not progress_bar.winfo_exists():
                            return
                    except:
                        return
                    
                    elapsed = time.time() - start_time
                    if elapsed >= progress_duration:
                        # Progress complete, stop timer
                        try:
                            dialog.after(0, lambda: progress_bar.config({"value": 100}) if progress_bar.winfo_exists() else None)
                        except:
                            pass
                        return
                    
                    # Calculate progress percentage
                    progress_percent = min(int((elapsed / progress_duration) * 100), 99)
                    try:
                        dialog.after(0, lambda: progress_bar.config({"value": progress_percent}) if progress_bar.winfo_exists() else None)
                    except:
                        pass
                    
                    # Schedule next update in 1 second
                    progress_timer = threading.Timer(1.0, update_progress)
                    progress_timer.start()
                
                # Start progress timer
                update_progress()
                process = subprocess.Popen(
                    command,
                    cwd=assets_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                debug_print(f"Flash tool process started with PID: {process.pid}")
                dialog.after(0, status_label.config, {"text": "Flash tool started. Please connect your device and wait for the process to complete."})
                debug_print("Reading flash tool output...")
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    line = line.strip()
                    debug_print(f"Flash tool output: {line}")
                    if text_widget:
                        try:
                            dialog.after(0, lambda: text_widget.insert(tk.END, line + "\n") if text_widget and text_widget.winfo_exists() else None)
                            dialog.after(0, lambda: text_widget.see(tk.END) if text_widget and text_widget.winfo_exists() else None)
                        except:
                            pass
                    if "search usb" in line.lower() or "search-usb" in line.lower():
                        debug_print("Found 'search usb' prompt")
                        dialog.after(0, status_label.config, {"text": "Flash tool is searching for USB device. Please connect your Y1 device."})
                    elif "all command exec done!" in line.lower():
                        debug_print("Found 'All command exec done!' message")
                        all_done_seen = True
                        flash_done = True
                        dialog.after(0, status_label.config, {"text": "Flash completed successfully! Please wait for device to restart."})
                        dialog.after(0, lambda: progress_bar.config({"value": 100}) if progress_bar.winfo_exists() else None)
                        if progress_timer:
                            progress_timer.cancel()
                        break
                    elif "disconnect!" in line.lower():
                        debug_print("Found 'Disconnect!' message")
                        disconnect_seen = True
                        dialog.after(0, status_label.config, {"text": "Device disconnected. Flash process completed."})
                        dialog.after(0, lambda: progress_bar.config({"value": 100}) if progress_bar.winfo_exists() else None)
                        if progress_timer:
                            progress_timer.cancel()
                        break
                    elif "error" in line.lower() or "failed" in line.lower():
                        debug_print(f"Error detected in flash tool output: {line}")
                        error_seen = True
                        dialog.after(0, status_label.config, {"text": f"Flash error detected: {line}"})
                        dialog.after(0, lambda: progress_bar.config({"value": 0}) if progress_bar.winfo_exists() else None)
                        if progress_timer:
                            progress_timer.cancel()
                        break
                process.wait()
                debug_print(f"Flash tool process completed with return code: {process.returncode}")
                if process.returncode != 0 and not flash_done:
                    debug_print("Flash tool exited with non-zero return code")
                    dialog.after(0, status_label.config, {"text": f"Flash tool exited with error code: {process.returncode}"})
                    dialog.after(0, lambda: progress_bar.config({"value": 0}) if progress_bar.winfo_exists() else None)
                elif flash_done:
                    debug_print("Flash completed successfully")
                    dialog.after(0, status_label.config, {"text": "Firmware flash completed successfully!"})
                    dialog.after(0, lambda: progress_bar.config({"value": 100}) if progress_bar.winfo_exists() else None)
                else:
                    debug_print("Flash tool completed but no completion message was detected")
                    dialog.after(0, status_label.config, {"text": "Flash tool completed. Please check if the firmware was installed successfully."})
                    dialog.after(0, lambda: progress_bar.config({"value": 100}) if progress_bar.winfo_exists() else None)
                dialog.after(0, ok_button.pack)
                dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                if progress_timer:
                    progress_timer.cancel()
            threading.Thread(target=run_flash, daemon=True).start()
        except Exception as e:
            debug_print(f"Exception in _flash_with_modal: {e}")
            dialog.after(0, status_label.config, {"text": f"Error starting flash tool: {e}"})
            dialog.after(0, ok_button.pack)
            dialog.after(0, ok_button.config, {"state": tk.NORMAL})

    def create_progress_dialog(self, title="Progress"):
        """Create a compact progress dialog with detailed status and progress bar"""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("450x180")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Apply theme colors to dialog
        self.apply_dialog_theme(dialog)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (dialog.winfo_screenheight() // 2) - (180 // 2)
        dialog.geometry(f"450x180+{x}+{y}")
        
        # Create frame
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Main status label
        status_label = ttk.Label(frame, text="Initializing...", font=("Segoe UI", 10, "bold"))
        status_label.pack(pady=(0, 8))
        
        # Detailed progress label
        detail_label = ttk.Label(frame, text="", font=("Segoe UI", 9))
        detail_label.pack(pady=(0, 12))
        
        # Progress bar
        progress_bar = ttk.Progressbar(frame, mode='determinate', length=350)
        progress_bar.pack(pady=(0, 8))
        
        # Speed/ETA label
        speed_label = ttk.Label(frame, text="", font=("Segoe UI", 8))
        speed_label.pack(pady=(0, 5))
        
        # Store references
        dialog.status_label = status_label
        dialog.detail_label = detail_label
        dialog.progress_bar = progress_bar
        dialog.speed_label = speed_label
        
        return dialog

    def parse_firmware_manifest(self, manifest_content):
        """Parse the manifest XML to find firmware options with fallback to cache"""
        try:
            # Try to parse the provided manifest content first
            if manifest_content:
                root = ET.fromstring(manifest_content)
                firmware_options = []
                
                # Look for package elements with handler types "Firmware" or "Custom Firmware"
                for package in root.findall('.//package'):
                    name = package.get('name', '')
                    repo = package.get('repo', '')
                    url = package.get('url', '')
                    handler = package.get('handler', '')
                    
                    # Check if this is a firmware package
                    if handler in ['Firmware', 'Custom Firmware']:
                        firmware_info = {
                            'name': name,
                            'repo': repo,
                            'url': url,
                            'handler': handler
                        }
                        
                        # Try to get cached file URLs for this firmware
                        cached_files = self._get_cached_file_urls(repo, 'firmware')
                        if cached_files:
                            firmware_info['cached_files'] = cached_files
                            debug_print(f"Using cached file URLs for firmware {name}: {len(cached_files)} files")
                        
                        firmware_options.append(firmware_info)
                
                if firmware_options:
                    debug_print(f"Found {len(firmware_options)} firmware options from manifest")
                    return firmware_options
            
            # Fallback to cache if no firmware found in manifest
            debug_print("No firmware found in manifest, trying cache...")
            cached_index = self.get_cached_index()
            if cached_index:
                firmware_options = []
                for entry in cached_index.findall('.//firmware/entry'):
                    firmware_options.append({
                        'name': entry.get('name', ''),
                        'repo': entry.get('repo', ''),
                        'url': entry.get('url', ''),
                        'handler': entry.get('handler', ''),
                        'release_url': entry.get('release_url', ''),
                        'cached_files': self._get_cached_file_urls(entry.get('repo', ''), 'firmware')
                    })
                
                if firmware_options:
                    debug_print(f"Found {len(firmware_options)} firmware options from cache")
                    return firmware_options
            
            debug_print("No firmware found in manifest or cache")
            return []
            
        except Exception as e:
            debug_print(f"Error parsing manifest: {e}")
            return []

    def show_firmware_selection_dialog_with_error(self, error_message):
        """Show firmware selection dialog with error message inline"""
        from tkinter import filedialog
        dialog = tk.Toplevel(self)
        dialog.title("Select Firmware")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Apply theme colors to dialog
        self.apply_dialog_theme(dialog)
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        label = ttk.Label(frame, text="Select a firmware to install:", font=("Segoe UI", 11))
        label.pack(pady=(0, 10))
        listbox = tk.Listbox(frame, font=("Segoe UI", 10))
        listbox.pack(fill=tk.BOTH, expand=True)
        
        # Apply theme colors to listbox (only if theme colors are available)
        try:
            if hasattr(self, 'bg_color') and hasattr(self, 'fg_color') and hasattr(self, 'accent_color'):
                listbox.configure(bg=self.bg_color, fg=self.fg_color, selectbackground=self.accent_color, selectforeground=self.fg_color)
        except Exception as e:
            debug_print(f"Could not apply theme to listbox: {e}")
        
        # Show error message in listbox
        listbox.insert(tk.END, error_message)
        listbox.itemconfig(0, fg='red')  # Make error message red
        
        # Disable selection for error message
        def on_select(event):
            if listbox.curselection() and listbox.curselection()[0] == 0:
                listbox.selection_clear(0, tk.END)
        
        listbox.bind('<<ListboxSelect>>', on_select)
        
        # Disable install button when error is shown
        install_btn = ttk.Button(frame, text="Install", command=lambda: None, state='disabled')
        install_btn.pack(pady=(10, 0))
        
        def browse_and_install():
            dialog.destroy()
            file_path = filedialog.askopenfilename(
                title="Select Firmware File",
                filetypes=[("Firmware files", "*.img"), ("All files", "*.")]
            )
            if not file_path:
                return
            root = self if isinstance(self, tk.Tk) else tk.Tk()
            popup = tk.Toplevel(root)
            popup.title("Unplug Device")
            popup.geometry("400x120")
            popup.transient(root)
            popup.grab_set()
            msg = ttk.Label(popup, text="Please turn off and unplug your Y1, then click Continue to proceed.", font=("Segoe UI", 10), wraplength=380, justify=tk.CENTER)
            msg.pack(pady=(20, 10), padx=10)
            btn = ttk.Button(popup, text="Continue", command=popup.destroy)
            btn.pack(pady=(0, 15))
            popup.wait_window()
            self.install_firmware(local_file=file_path)
        browse_btn = ttk.Button(frame, text="Browse Firmware (.img)", command=browse_and_install)
        browse_btn.pack(pady=(5, 0))
        
        # Add close button
        close_btn = ttk.Button(frame, text="Close", command=dialog.destroy)
        close_btn.pack(pady=(5, 0))

    def show_firmware_selection_dialog(self, firmware_options):
        """Show firmware selection dialog with actual firmware options"""
        from tkinter import filedialog
        dialog = tk.Toplevel(self)
        dialog.title("Select Firmware")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Apply theme colors to dialog
        self.apply_dialog_theme(dialog)
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        label = ttk.Label(frame, text="Select a firmware to install:", font=("Segoe UI", 11))
        label.pack(pady=(0, 10))
        listbox = tk.Listbox(frame, font=("Segoe UI", 10))
        listbox.pack(fill=tk.BOTH, expand=True)
        
        # Apply theme colors to listbox (only if theme colors are available)
        try:
            if hasattr(self, 'bg_color') and hasattr(self, 'fg_color') and hasattr(self, 'accent_color'):
                listbox.configure(bg=self.bg_color, fg=self.fg_color, selectbackground=self.accent_color, selectforeground=self.fg_color)
        except Exception as e:
            debug_print(f"Could not apply theme to listbox: {e}")
        
        for i, fw in enumerate(firmware_options):
            listbox.insert(tk.END, fw.get('name', f"Firmware {i+1}"))
        
        selected = [None]
        def confirm_and_close():
            idx = listbox.curselection()
            if not idx:
                return
            selected[0] = firmware_options[idx[0]]
            dialog.destroy()
        
        def on_double_click(event):
            confirm_and_close()
        
        def on_enter(event):
            confirm_and_close()
        
        listbox.bind('<Double-Button-1>', on_double_click)
        listbox.bind('<Return>', on_enter)
        
        install_btn = ttk.Button(frame, text="Install", command=confirm_and_close)
        install_btn.pack(pady=(10, 0))
        
        def browse_and_install():
            dialog.destroy()
            file_path = filedialog.askopenfilename(
                title="Select Firmware File",
                filetypes=[("Firmware files", "*.img"), ("All files", "*.")]
            )
            if not file_path:
                return
            root = self if isinstance(self, tk.Tk) else tk.Tk()
            popup = tk.Toplevel(root)
            popup.title("Unplug Device")
            popup.geometry("400x120")
            popup.transient(root)
            popup.grab_set()
            msg = ttk.Label(popup, text="Please turn off and unplug your Y1, then click Continue to proceed.", font=("Segoe UI", 10), wraplength=380, justify=tk.CENTER)
            msg.pack(pady=(20, 10), padx=10)
            btn = ttk.Button(popup, text="Continue", command=popup.destroy)
            btn.pack(pady=(0, 15))
            popup.wait_window()
            self.install_firmware(local_file=file_path)
        
        browse_btn = ttk.Button(frame, text="Browse Firmware (.img)", command=browse_and_install)
        browse_btn.pack(pady=(5, 0))
        dialog.wait_window()
        if selected[0] is not None:
            root = self if isinstance(self, tk.Tk) else tk.Tk()
            popup = tk.Toplevel(root)
            popup.title("Unplug Device")
            popup.geometry("400x120")
            popup.transient(root)
            popup.grab_set()
            msg = ttk.Label(popup, text="Please turn off and unplug your Y1, then click Continue to proceed.", font=("Segoe UI", 10), wraplength=380, justify=tk.CENTER)
            msg.pack(pady=(20, 10), padx=10)
            btn = ttk.Button(popup, text="Continue", command=popup.destroy)
            btn.pack(pady=(0, 15))
            popup.wait_window()
            self._download_and_flash_selected_firmware(selected[0])

    def menu_reinstall_app(self):
        """Reinstall app with progress modal"""
        try:
            # Create progress dialog
            progress_dialog = self.create_progress_dialog("Reinstalling App")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                if progress_dialog and hasattr(progress_dialog, 'status_label'):
                    progress_dialog.status_label.config(text=message)
                    progress_dialog.update()
            
            def do_reinstall():
                try:
                    update_progress("Checking for latest installer...")
                    update_info = self.check_for_team_slide_updates()
                    
                    if update_info and update_info.get('installer_asset'):
                        update_progress("Downloading installer...")
                        self.download_and_run_installer(update_info['installer_asset'])
                    else:
                        update_progress("No installer found")
                        messagebox.showwarning("Reinstall", "No installer found for reinstall")
                except Exception as e:
                    update_progress(f"Error: {e}")
                    messagebox.showerror("Reinstall Error", f"Failed to reinstall: {str(e)}")
                finally:
                    if progress_dialog:
                        progress_dialog.destroy()
            
            # Run in background thread
            import threading
            threading.Thread(target=do_reinstall, daemon=True).start()
            
        except Exception as e:
            debug_print(f"Error in menu_reinstall_app: {e}")
            messagebox.showerror("Error", f"Failed to start reinstall: {str(e)}")

    def menu_update_app(self):
        """Update app with progress modal"""
        try:
            # Create progress dialog
            progress_dialog = self.create_progress_dialog("Updating App")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                if progress_dialog and hasattr(progress_dialog, 'status_label'):
                    progress_dialog.status_label.config(text=message)
                    progress_dialog.update()
            
            def do_update():
                try:
                    update_progress("Checking for latest patch...")
                    update_info = self.check_for_team_slide_updates()
                    
                    if update_info and update_info.get('patch_asset'):
                        update_progress("Downloading patch...")
                        self.download_and_run_patch(update_info['patch_asset'])
                    else:
                        update_progress("No patch found")
                        messagebox.showwarning("Update", "No patch found for update")
                except Exception as e:
                    update_progress(f"Error: {e}")
                    messagebox.showerror("Update Error", f"Failed to update: {str(e)}")
                finally:
                    if progress_dialog:
                        progress_dialog.destroy()
            
            # Run in background thread
            import threading
            threading.Thread(target=do_update, daemon=True).start()
            
        except Exception as e:
            debug_print(f"Error in menu_update_app: {e}")
            messagebox.showerror("Error", f"Failed to start update: {str(e)}")

    def download_and_run_installer_from_latest(self):
        """Always fetch the latest release from GitHub and run installer.exe if present."""
        try:
            debug_print("Fetching latest release for installer...")
            # Use the same fallback logic as check_for_team_slide_updates, but ignore version check
            update_info = self._check_updates_via_api()
            if not update_info:
                debug_print("API method failed, trying releases page fallback...")
                update_info = self._check_updates_via_releases_page()
            if not update_info:
                debug_print("Releases page failed, trying master branch fallback...")
                update_info = self._check_updates_via_master_branch()
            if update_info and update_info.get('installer_asset'):
                self.download_and_run_installer(update_info['installer_asset'])
            else:
                messagebox.showwarning("Reinstall", "No installer.exe found in the latest release.")
        except Exception as e:
            debug_print(f"Error in download_and_run_installer_from_latest: {e}")
            messagebox.showerror("Reinstall Error", f"Failed to fetch installer: {str(e)}")

    def download_and_run_patch_from_latest(self):
        """Always fetch the latest release from GitHub and run patch.exe if present."""
        try:
            debug_print("Fetching latest release for patch...")
            # Use the same fallback logic as check_for_team_slide_updates, but ignore version check
            update_info = self._check_updates_via_api()
            if not update_info:
                debug_print("API method failed, trying releases page fallback...")
                update_info = self._check_updates_via_releases_page()
            if not update_info:
                debug_print("Releases page failed, trying master branch fallback...")
                update_info = self._check_updates_via_master_branch()
            if update_info and update_info.get('patch_asset'):
                self.download_and_run_patch(update_info['patch_asset'])
            else:
                messagebox.showwarning("Update", "No patch.exe found in the latest release.")
        except Exception as e:
            debug_print(f"Error in download_and_run_patch_from_latest: {e}")
            messagebox.showerror("Update Error", f"Failed to fetch patch: {str(e)}")

    def _run_update_exe_and_wait(self, exe_path, friendly_name):
        import subprocess
        try:
            # Kill all y1_helper processes first
            self.kill_all_y1_helper_processes()
            
            # Launch the update executable
            subprocess.Popen([exe_path], shell=True)
            
            # Force quit this process immediately
            import os
            os._exit(0)  # Force exit without cleanup
        except Exception as e:
            debug_print(f"Error in _run_update_exe_and_wait: {e}")
            import os
            os._exit(0)  # Force exit even on error

    def kill_all_y1_helper_processes(self):
        import psutil, os
        current_pid = os.getpid()
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid == current_pid:
                    continue  # Skip current process for now
                    
                if 'python' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('y1_helper.py' in arg for arg in cmdline):
                        debug_print(f"Terminating y1_helper process: PID {proc.pid}")
                        proc.terminate()
                        killed_count += 1
                        
                        # Wait a bit for graceful termination
                        try:
                            proc.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            debug_print(f"Force killing process: PID {proc.pid}")
                            proc.kill()
                            
            except Exception as e:
                debug_print(f"Error killing process {proc.pid}: {e}")
                continue
        
        debug_print(f"Killed {killed_count} y1_helper processes")
        
        # Now terminate the current process
        debug_print(f"Terminating current process: PID {current_pid}")
        return killed_count


    def startup_update_check(self):
        try:
            debug_print("Running startup update check...")
            
            # First check cached update info
            cached_update = self._get_cached_update_info()
            if cached_update and self._is_cached_update_newer(cached_update):
                debug_print(f"Found cached update info: {cached_update['version']}")
                debug_print("Cached update is newer than current version")
                self.update_info = cached_update
                self.update_available = True
                
                # Check if patch.exe is available for automatic update
                if cached_update.get('patch_asset'):
                    debug_print("Cached patch.exe available - starting automatic update")
                    # Block UI and start automatic patch
                    self.disable_input_bindings()
                    self.after(1000, lambda: self.download_and_run_patch(cached_update['patch_asset']))
                else:
                    # No patch available - show update pill for manual update
                    debug_print("No cached patch.exe available - showing update pill")
                    self.after(1000, self.show_update_pill_if_needed)
                return
            
            # Check if we should skip API calls due to recent startup
            if self.should_skip_api_checks():
                debug_print("Skipping startup update check due to recent startup")
                return
            
            # Update last API check time
            self.last_api_check_time = datetime.datetime.now()
            self.save_startup_tracking()
            
            # Check for updates using all methods
            update_info = self._check_updates_via_api()
            if not update_info:
                update_info = self._check_updates_via_releases_page()
            if not update_info:
                update_info = self._check_updates_via_master_branch()
            
            if update_info:
                # Compare versions to see if it's actually newer
                if self.compare_versions(update_info['version'], self.version) > 0:
                    debug_print(f"Newer version available at startup: {update_info['version']}")
                    self.update_info = update_info
                    self.update_available = True
                    
                    # Check if patch.exe is available for automatic update
                    if update_info.get('patch_asset'):
                        debug_print("Patch.exe available - starting automatic update")
                        # Block UI and start automatic patch
                        self.disable_input_bindings()
                        self.after(1000, lambda: self.download_and_run_patch(update_info['patch_asset']))
                    else:
                        # No patch available - show update pill for manual update
                        debug_print("No patch.exe available - showing update pill")
                        self.after(2000, self.show_update_pill_if_needed)
                else:
                    debug_print("No newer version available at startup")
            else:
                debug_print("No update information available at startup")
                
        except Exception as e:
            debug_print(f"Error in startup_update_check: {e}")

    def show_startup_update_dialog(self, update_info):
        """Show startup update dialog asking if user wants to update"""
        try:
            # Create startup dialog
            dialog = tk.Toplevel(self)
            dialog.title("Update Available")
            dialog.geometry("450x300")
            dialog.transient(self)
            dialog.grab_set()
            
            # Apply theme colors to dialog
            self.apply_dialog_theme(dialog)
            
            # Center dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
            y = (dialog.winfo_screenheight() // 2) - (300 // 2)
            dialog.geometry(f"450x300+{x}+{y}")
            
            # Create frame
            frame = ttk.Frame(dialog, padding="20")
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(frame, text="Update Available!", 
                                   font=("Segoe UI", 16, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Version info
            version_label = ttk.Label(frame, 
                                     text=f"A newer version (v{update_info['version']}) is available!\n"
                                          f"Current version: v{self.version}",
                                     font=("Segoe UI", 11))
            version_label.pack(pady=(0, 20))
            
            # Description
            desc_label = ttk.Label(frame, text="Would you like to update now?", 
                                  font=("Segoe UI", 10))
            desc_label.pack(pady=(0, 20))
            
            # Buttons frame
            buttons_frame = ttk.Frame(frame)
            buttons_frame.pack(fill=tk.X, pady=(0, 20))
            
            def update_now():
                dialog.destroy()
                self.show_update_choice_dialog()
            
            def later():
                dialog.destroy()
                # Show the update pill instead
                self.show_update_pill_if_needed()
            
            # Update Now button
            update_btn = ttk.Button(buttons_frame, text="Update Now", 
                                   command=update_now, style="TButton")
            update_btn.pack(fill=tk.X, pady=(0, 10))
            
            # Later button
            later_btn = ttk.Button(buttons_frame, text="Later", command=later)
            later_btn.pack(fill=tk.X)
            
        except Exception as e:
            debug_print(f"Error in show_startup_update_dialog: {e}")
            messagebox.showerror("Update Error", f"Failed to show startup update dialog: {str(e)}")

    def show_update_pill_if_needed(self):
        """Show the update pill if update is available"""
        try:
            if hasattr(self, 'update_info') and self.update_info:
                debug_print("Showing update pill")



                self.update_pill.config(text="Y1 Helper Update Available")
                self.help_menu_label = "Update Available"
                self.menubar.entryconfig("Help", label=self.help_menu_label)
        except Exception as e:
            debug_print(f"Error in show_update_pill_if_needed: {e}")

    def on_menu_select(self, event):
        """Handle menu selection events, specifically for update available clicks"""
        try:
            # Get the currently selected menu item
            menu_index = self.menubar.index("@%s,%s" % (event.x, event.y))
            if menu_index is not None:
                menu_label = self.menubar.entrycget(menu_index, "label")
                
                # Check if Help menu is clicked and shows "Update Available"
                if "Update Available" in menu_label and hasattr(self, 'update_info') and self.update_info:
                    debug_print("Update Available menu clicked, showing update dialog")
                    self.show_update_choice_dialog()
        except Exception as e:
            debug_print(f"Error in on_menu_select: {e}")
    
    def on_apps_menu_select(self, event):
        """Track when user is interacting with Apps menu"""
        self.apps_menu_active = True
        self.apps_menu_last_interaction = datetime.datetime.now()
        debug_print("Apps menu interaction detected")
    
    def on_apps_menu_leave(self, event):
        """Track when user leaves Apps menu"""
        # Delay the deactivation to prevent flickering
        self.after(500, self._deactivate_apps_menu)
    
    def _deactivate_apps_menu(self):
        """Deactivate Apps menu after a delay"""
        if self.apps_menu_last_interaction:
            time_since_interaction = datetime.datetime.now() - self.apps_menu_last_interaction
            if time_since_interaction.total_seconds() > 0.5:  # 500ms delay
                self.apps_menu_active = False
                debug_print("Apps menu deactivated")

    def show_update_choice_dialog(self, event=None):
        """Show dialog to choose between quick update (patch) or full update (installer)"""
        try:
            if not hasattr(self, 'update_info') or not self.update_info:
                # Fetch latest release info
                update_info = self._check_updates_via_api()
                if not update_info:
                    update_info = self._check_updates_via_releases_page()
                if not update_info:
                    update_info = self._check_updates_via_master_branch()
                
                if not update_info:
                    messagebox.showinfo("Update", "No update information available.")
                    return
                
                self.update_info = update_info
            
            # Create choice dialog
            dialog = tk.Toplevel(self)
            dialog.title("Update Available")
            dialog.geometry("400x250")
            dialog.transient(self)
            dialog.grab_set()
            
            # Apply theme colors to dialog
            self.apply_dialog_theme(dialog)
            
            # Center dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (dialog.winfo_screenheight() // 2) - (250 // 2)
            dialog.geometry(f"400x250+{x}+{y}")
            
            # Create frame
            frame = ttk.Frame(dialog, padding="20")
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(frame, text=f"Update to v{self.update_info['version']} Available", 
                                   font=("Segoe UI", 14, "bold"))
            title_label.pack(pady=(0, 20))
            
            # Description
            desc_label = ttk.Label(frame, text="Choose your update method:", 
                                  font=("Segoe UI", 10))
            desc_label.pack(pady=(0, 20))
            
            # Buttons frame
            buttons_frame = ttk.Frame(frame)
            buttons_frame.pack(fill=tk.X, pady=(0, 20))
            
            def quick_update():
                if self.update_info.get('patch_asset'):
                    dialog.destroy()
                    self.download_and_run_patch(self.update_info['patch_asset'])
                else:
                    # No patch available, redirect to full installer
                    dialog.destroy()
                    if self.update_info.get('installer_asset'):
                        self.download_and_run_installer(self.update_info['installer_asset'])
                    else:
                        messagebox.showwarning("Update", "No update executables available.")
            
            def full_update():
                if self.update_info.get('installer_asset'):
                    dialog.destroy()
                    self.download_and_run_installer(self.update_info['installer_asset'])
                else:
                    messagebox.showwarning("Full Update", "No installer.exe available for full update.")
            
            def cancel():
                dialog.destroy()
            
            # Quick Update button (patch) - only show if patch is available
            if self.update_info.get('patch_asset'):
                quick_btn = ttk.Button(buttons_frame, text="Quick Update (Patch)", 
                                      command=quick_update, style="TButton")
                quick_btn.pack(fill=tk.X, pady=(0, 10))
            
            # Full Update button (installer) - show if installer is available
            if self.update_info.get('installer_asset'):
                if self.update_info.get('patch_asset'):
                    # Both available - show as "Full Update"
                    full_btn = ttk.Button(buttons_frame, text="Full Update (Installer)", 
                                         command=full_update, style="TButton")
                else:
                    # Only installer available - show as "Update"
                    full_btn = ttk.Button(buttons_frame, text="Update", 
                                         command=full_update, style="TButton")
                full_btn.pack(fill=tk.X, pady=(0, 10))
            
            # Cancel button
            cancel_btn = ttk.Button(buttons_frame, text="Cancel", command=cancel)
            cancel_btn.pack(fill=tk.X)
            
        except Exception as e:
            debug_print(f"Error in show_update_choice_dialog: {e}")
            messagebox.showerror("Update Error", f"Failed to show update dialog: {str(e)}")

    def launch_old_version(self):
        """Launch old.py and exit current instance"""
        try:
            debug_print("Launching old.py...")
            
            # Get the path to old.py
            old_py_path = os.path.join(self.base_dir, "old.py")
            python_exe = os.path.join(self.base_dir, "assets", "python", "python.exe")
            
            if not os.path.exists(old_py_path):
                messagebox.showerror("Error", "old.py not found in the project directory")
                return
            
            if not os.path.exists(python_exe):
                messagebox.showerror("Error", "Python executable not found at assets/python/python.exe")
                return
            
            # Set up environment variables
            env = os.environ.copy()
            env['Y1_HELPER_ROOT'] = self.base_dir
            env['Y1_HELPER_ASSETS'] = os.path.join(self.base_dir, 'assets')
            
            # Launch old.py
            subprocess.Popen([python_exe, old_py_path], cwd=self.base_dir, env=env)
            
            # Exit current instance
            self.quit()
            
        except Exception as e:
            debug_print(f"Error launching old.py: {e}")
            messagebox.showerror("Error", f"Failed to launch old.py: {e}")
    
    def show_team_slide_update_prompt(self, update_info):
        if self.update_prompt_shown:
            return
        self.update_prompt_shown = True
        # ... existing code ...

class FileExplorerDialog:
    """Comprehensive file explorer dialog for Y1 device with full file management"""
    
    def __init__(self, parent, adb_path):
        self.parent = parent
        self.adb_path = adb_path
        self.dialog = None
        self.tree = None
        self.path_var = None
        self.status_var = None
        self.progress_var = None
        self.progress_bar = None
        self.clipboard = {"operation": None, "items": []}
        self.is_loading = False
        self.current_path = "/"
        self.root_access = False
        
    def show(self):
        """Show the file explorer dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Y1 Device File Explorer")
        self.dialog.geometry("800x600")
        self.dialog.resizable(True, True)
        
        # Apply theme colors to dialog
        if hasattr(self.parent, 'apply_dialog_theme'):
            self.parent.apply_dialog_theme(self.dialog)
        
        # Center the dialog
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Setup UI
        self.setup_ui()
        
        # Check root access and start loading
        self.check_root_access()
        
    def setup_ui(self):
        """Setup the file explorer UI"""
        # Main frame
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # Navigation buttons
        ttk.Button(toolbar, text="Up", command=self.go_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Home", command=self.go_home).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Root", command=self.go_root).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_current).pack(side=tk.LEFT, padx=(0, 5))
        
        # Path display
        ttk.Label(toolbar, text="Path:").pack(side=tk.LEFT, padx=(20, 5))
        self.path_var = tk.StringVar(value="/")
        path_entry = ttk.Entry(toolbar, textvariable=self.path_var, width=50)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        path_entry.bind('<Return>', self.navigate_to_path)
        
        # File operations toolbar
        file_toolbar = ttk.Frame(main_frame)
        file_toolbar.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_toolbar, text="Copy", command=self.copy_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="Cut", command=self.cut_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="Paste", command=self.paste_items).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="Delete", command=self.delete_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="Rename", command=self.rename_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="New Folder", command=self.create_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="New File", command=self.create_file).pack(side=tk.LEFT, padx=(0, 5))
        
        # Progress bar
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        # Treeview with scrollbars
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        self.tree = ttk.Treeview(tree_frame, columns=("size", "permissions", "owner", "date"), show="tree headings")
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("permissions", text="Permissions")
        self.tree.heading("owner", text="Owner")
        self.tree.heading("date", text="Modified")
        
        # Configure column widths
        self.tree.column("#0", width=800, minwidth=200)
        self.tree.column("size", width=100, minwidth=80)
        self.tree.column("permissions", width=100, minwidth=80)
        self.tree.column("owner", width=100, minwidth=80)
        self.tree.column("date", width=150, minwidth=120)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.tree.bind('<Double-1>', self.on_item_double_click)
        self.tree.bind('<Return>', self.on_item_double_click)
        self.tree.bind('<Delete>', lambda e: self.delete_selected())
        self.tree.bind('<F2>', lambda e: self.rename_selected())
        self.tree.bind('<F5>', lambda e: self.refresh_current())
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, pady=(5, 0))
        
        # Context menu
        self.setup_context_menu()
        
    def setup_context_menu(self):
        """Setup right-click context menu"""
        if self.dialog and self.tree:
            self.context_menu = tk.Menu(self.dialog, tearoff=0)
            self.context_menu.add_command(label="Open", command=self.open_selected)
            self.context_menu.add_command(label="Open in New Window", command=self.open_in_new_window)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Copy", command=self.copy_selected)
            self.context_menu.add_command(label="Cut", command=self.cut_selected)
            self.context_menu.add_command(label="Paste", command=self.paste_items)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Delete", command=self.delete_selected)
            self.context_menu.add_command(label="Rename", command=self.rename_selected)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Properties", command=self.show_properties)
            
            self.tree.bind("<Button-3>", self.show_context_menu)
        
    def show_context_menu(self, event):
        """Show context menu at mouse position"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
            
    def check_root_access(self):
        """Check if we have root access to the device"""
        if self.progress_var:
            self.progress_var.set("Checking root access...")
        if self.progress_bar:
            self.progress_bar.start()
        
        def check_root():
            try:
                # Try to remount system as read-write
                success, stdout, stderr = self.run_adb_command("shell su -c 'mount -o rw,remount /system'")
                if success:
                    self.root_access = True
                    if self.progress_var:
                        self.progress_var.set("Root access granted")
                else:
                    if self.progress_var:
                        self.progress_var.set("Limited access - some operations may be restricted")
                    self.root_access = False
                
                if self.progress_bar:
                    self.progress_bar.stop()
                self.load_directory("/")
                
            except Exception as e:
                if self.progress_var:
                    self.progress_var.set(f"Error checking root access: {e}")
                if self.progress_bar:
                    self.progress_bar.stop()
                self.root_access = False
                self.load_directory("/")
        
        threading.Thread(target=check_root, daemon=True).start()
        
    def run_adb_command(self, command, timeout=30):
        """Run ADB command and return (success, stdout, stderr)"""
        try:
            if platform.system() == "Windows":
                full_command = f'"{self.adb_path}" {command}'
                result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=timeout)
            else:
                result = subprocess.run([self.adb_path] + command.split(), capture_output=True, text=True, timeout=timeout)
            
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
            
    def load_directory(self, path):
        """Load directory contents into treeview"""
        if self.is_loading or not self.tree or not self.path_var or not self.progress_var or not self.progress_bar:
            return
            
        self.is_loading = True
        self.current_path = path
        if self.path_var:
            self.path_var.set(path)
        if self.progress_var:
            self.progress_var.set(f"Loading {path}...")
        if self.progress_bar:
            self.progress_bar.start()
        
        def load_thread():
            try:
                # Clear current items
                if self.tree:
                    self.tree.delete(*self.tree.get_children())
                
                # Get directory listing with detailed info
                success, stdout, stderr = self.run_adb_command(f"shell ls -la '{path}'")
                if not success:
                    if self.progress_var:
                        self.progress_var.set(f"Error loading directory: {stderr}")
                    return
                
                lines = stdout.strip().split('\n')
                items = []
                
                for line in lines:
                    if line.startswith('total'):
                        continue
                    
                    # Parse ls -la output
                    parts = line.split()
                    if len(parts) >= 9:
                        permissions = parts[0]
                        owner = parts[2]
                        group = parts[3]
                        size = parts[4]
                        date_parts = parts[5:8]
                        name = ' '.join(parts[8:])
                        
                        # Skip . and .. entries
                        if name in ['.', '..']:
                            continue
                            
                        # Determine if it's a directory
                        is_dir = permissions.startswith('d')
                        
                        items.append({
                            'name': name,
                            'permissions': permissions,
                            'owner': f"{owner}:{group}",
                            'size': size if not is_dir else '',
                            'date': ' '.join(date_parts),
                            'is_dir': is_dir
                        })
                
                # Sort items (directories first, then files)
                items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
                
                # Add items to treeview
                if self.tree:
                    for item in items:
                        icon = "??" if item['is_dir'] else "??"
                        values = (item['size'], item['permissions'], item['owner'], item['date'])
                        self.tree.insert("", "end", text=f"{icon} {item['name']}", values=values)
                
                if self.progress_var:
                    self.progress_var.set(f"Loaded {len(items)} items")
                if self.status_var:
                    self.status_var.set(f"Path: {path} | Items: {len(items)}")
                
            except Exception as e:
                if self.progress_var:
                    self.progress_var.set(f"Error: {e}")
            finally:
                if self.progress_bar:
                    self.progress_bar.stop()
                self.is_loading = False
        
        threading.Thread(target=load_thread, daemon=True).start()
        
    def on_item_double_click(self, event):
        """Handle double-click on treeview item"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = self.tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]  # Remove icon
        full_path = os.path.join(self.current_path, name).replace('\\', '/')
        
        # Check if it's a directory
        if item['text'].startswith('??'):
            self.load_directory(full_path)
        else:
            self.open_selected()
            
    def open_selected(self):
        """Open selected file"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to open.")
            return
            
        item = self.tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]
        full_path = os.path.join(self.current_path, name).replace('\\', '/')
        
        if item['text'].startswith('??'):
            self.load_directory(full_path)
        else:
            # For files, we could implement file viewing/editing
            messagebox.showinfo("File Open", f"Opening file: {full_path}\n\nFile viewing/editing not yet implemented.")
            
    def open_in_new_window(self):
        """Open selected item in new explorer window"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = self.tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]
        full_path = os.path.join(self.current_path, name).replace('\\', '/')
        
        if item['text'].startswith('??'):
            new_explorer = FileExplorerDialog(self.parent, self.adb_path)
            new_explorer.show()
            new_explorer.load_directory(full_path)
            
    def go_up(self):
        """Navigate to parent directory"""
        parent = os.path.dirname(self.current_path.rstrip('/'))
        if parent and parent != self.current_path:
            self.load_directory(parent)
            
    def go_home(self):
        """Navigate to home directory"""
        self.load_directory("/data/data")
        
    def go_root(self):
        """Navigate to root directory"""
        self.load_directory("/")
        
    def navigate_to_path(self, event=None):
        """Navigate to path entered in path bar"""
        path = self.path_var.get().strip()
        if path and path != self.current_path:
            self.load_directory(path)
            
    def refresh_current(self):
        """Refresh current directory"""
        self.load_directory(self.current_path)
        
    def get_selected_items(self):
        """Get list of selected items with full paths"""
        selection = self.tree.selection()
        items = []
        for item_id in selection:
            item = self.tree.item(item_id)
            name = item['text'].split(' ', 1)[1]
            full_path = os.path.join(self.current_path, name).replace('\\', '/')
            items.append({
                'name': name,
                'path': full_path,
                'is_dir': item['text'].startswith('??')
            })
        return items
        
    def copy_selected(self):
        """Copy selected items to clipboard"""
        items = self.get_selected_items()
        if not items:
            messagebox.showwarning("No Selection", "Please select items to copy.")
            return
            
        self.clipboard = {"operation": "copy", "items": items}
        self.status_var.set(f"Copied {len(items)} item(s) to clipboard")
        
    def cut_selected(self):
        """Cut selected items to clipboard"""
        items = self.get_selected_items()
        if not items:
            messagebox.showwarning("No Selection", "Please select items to cut.")
            return
            
        self.clipboard = {"operation": "cut", "items": items}
        self.status_var.set(f"Cut {len(items)} item(s) to clipboard")
        
    def paste_items(self):
        """Paste items from clipboard"""
        if not self.clipboard["items"]:
            messagebox.showwarning("Empty Clipboard", "No items in clipboard to paste.")
            return
            
        operation = self.clipboard["operation"]
        items = self.clipboard["items"]
        
        def paste_thread():
            self.progress_var.set(f"{operation.title()}ing {len(items)} item(s)...")
            self.progress_bar.start()
            
            try:
                for item in items:
                    source_path = item['path']
                    dest_path = os.path.join(self.current_path, item['name']).replace('\\', '/')
                    
                    if operation == "copy":
                        if item['is_dir']:
                            success, stdout, stderr = self.run_adb_command(f"shell cp -r '{source_path}' '{dest_path}'")
                        else:
                            success, stdout, stderr = self.run_adb_command(f"shell cp '{source_path}' '{dest_path}'")
                    else:  # cut
                        success, stdout, stderr = self.run_adb_command(f"shell mv '{source_path}' '{dest_path}'")
                        
                    if not success:
                        self.progress_var.set(f"Error {operation}ing {item['name']}: {stderr}")
                        return
                        
                # Clear clipboard after cut operation
                if operation == "cut":
                    self.clipboard = {"operation": None, "items": []}
                    
                self.progress_var.set(f"Successfully {operation}ed {len(items)} item(s)")
                self.refresh_current()
                
            except Exception as e:
                self.progress_var.set(f"Error: {e}")
            finally:
                self.progress_bar.stop()
                
        threading.Thread(target=paste_thread, daemon=True).start()
        
    def delete_selected(self):
        """Delete selected items"""
        items = self.get_selected_items()
        if not items:
            messagebox.showwarning("No Selection", "Please select items to delete.")
            return
            
        # Confirm deletion
        names = [item['name'] for item in items]
        result = messagebox.askyesno("Confirm Delete", 
                                   f"Are you sure you want to delete {len(items)} item(s)?\n\n" + 
                                   "\n".join(names[:5]) + 
                                   ("\n..." if len(names) > 5 else ""))
        if not result:
            return
            
        def delete_thread():
            self.progress_var.set(f"Deleting {len(items)} item(s)...")
            self.progress_bar.start()
            
            try:
                for item in items:
                    if item['is_dir']:
                        success, stdout, stderr = self.run_adb_command(f"shell rm -rf '{item['path']}'")
                    else:
                        success, stdout, stderr = self.run_adb_command(f"shell rm '{item['path']}'")
                        
                    if not success:
                        self.progress_var.set(f"Error deleting {item['name']}: {stderr}")
                        return
                        
                self.progress_var.set(f"Successfully deleted {len(items)} item(s)")
                self.refresh_current()
                
            except Exception as e:
                self.progress_var.set(f"Error: {e}")
            finally:
                self.progress_bar.stop()
                
        threading.Thread(target=delete_thread, daemon=True).start()
        
    def rename_selected(self):
        """Rename selected item"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to rename.")
            return
            
        if len(selection) > 1:
            messagebox.showwarning("Multiple Selection", "Please select only one item to rename.")
            return
            
        item = self.tree.item(selection[0])
        old_name = item['text'].split(' ', 1)[1]
        old_path = os.path.join(self.current_path, old_name).replace('\\', '/')
        
        new_name = simpledialog.askstring("Rename", f"Enter new name for '{old_name}':", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return
            
        new_path = os.path.join(self.current_path, new_name).replace('\\', '/')
        
        def rename_thread():
            self.progress_var.set(f"Renaming '{old_name}' to '{new_name}'...")
            self.progress_bar.start()
            
            try:
                success, stdout, stderr = self.run_adb_command(f"shell mv '{old_path}' '{new_path}'")
                if success:
                    self.progress_var.set(f"Successfully renamed '{old_name}' to '{new_name}'")
                    self.refresh_current()
                else:
                    self.progress_var.set(f"Error renaming: {stderr}")
                    
            except Exception as e:
                self.progress_var.set(f"Error: {e}")
            finally:
                self.progress_bar.stop()
                
        threading.Thread(target=rename_thread, daemon=True).start()
        
    def create_folder(self):
        """Create new folder"""
        folder_name = simpledialog.askstring("New Folder", "Enter folder name:")
        if not folder_name:
            return
            
        folder_path = os.path.join(self.current_path, folder_name).replace('\\', '/')
        
        def create_thread():
            self.progress_var.set(f"Creating folder '{folder_name}'...")
            self.progress_bar.start()
            
            try:
                success, stdout, stderr = self.run_adb_command(f"shell mkdir '{folder_path}'")
                if success:
                    self.progress_var.set(f"Successfully created folder '{folder_name}'")
                    self.refresh_current()
                else:
                    self.progress_var.set(f"Error creating folder: {stderr}")
                    
            except Exception as e:
                self.progress_var.set(f"Error: {e}")
            finally:
                self.progress_bar.stop()
                
        threading.Thread(target=create_thread, daemon=True).start()
        
    def create_file(self):
        """Create new file"""
        file_name = simpledialog.askstring("New File", "Enter file name:")
        if not file_name:
            return
            
        file_path = os.path.join(self.current_path, file_name).replace('\\', '/')
        
        def create_thread():
            self.progress_var.set(f"Creating file '{file_name}'...")
            self.progress_bar.start()
            
            try:
                success, stdout, stderr = self.run_adb_command(f"shell touch '{file_path}'")
                if success:
                    self.progress_var.set(f"Successfully created file '{file_name}'")
                    self.refresh_current()
                else:
                    self.progress_var.set(f"Error creating file: {stderr}")
                    
            except Exception as e:
                self.progress_var.set(f"Error: {e}")
            finally:
                self.progress_bar.stop()
                
        threading.Thread(target=create_thread, daemon=True).start()
        
    def show_properties(self):
        """Show properties of selected item"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to view properties.")
            return
            
        if len(selection) > 1:
            messagebox.showwarning("Multiple Selection", "Please select only one item to view properties.")
            return
            
        item = self.tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]
        full_path = os.path.join(self.current_path, name).replace('\\', '/')
        
        def get_properties():
            self.progress_var.set("Getting properties...")
            self.progress_bar.start()
            
            try:
                # Get detailed file info
                success, stdout, stderr = self.run_adb_command(f"shell ls -la '{full_path}'")
                if success:
                    lines = stdout.strip().split('\n')
                    if lines:
                        parts = lines[0].split()
                        if len(parts) >= 9:
                            permissions = parts[0]
                            owner = parts[2]
                            group = parts[3]
                            size = parts[4]
                            date = ' '.join(parts[5:8])
                            
                            # Get additional info
                            success2, stdout2, stderr2 = self.run_adb_command(f"shell stat '{full_path}'")
                            stat_info = stdout2 if success2 else ""
                            
                            # Show properties dialog
                            self.show_properties_dialog(name, full_path, permissions, owner, group, size, date, stat_info)
                            
            except Exception as e:
                self.progress_var.set(f"Error getting properties: {e}")
            finally:
                self.progress_bar.stop()
                
        threading.Thread(target=get_properties, daemon=True).start()
        
    def show_properties_dialog(self, name, path, permissions, owner, group, size, date, stat_info):
        """Show properties dialog with file information"""
        dialog = tk.Toplevel(self.dialog)
        dialog.title(f"Properties - {name}")
        dialog.geometry("500x400")
        dialog.transient(self.dialog)
        dialog.grab_set()
        
        # Apply theme colors to dialog
        if hasattr(self.parent, 'apply_dialog_theme'):
            self.parent.apply_dialog_theme(dialog)
        
        # Create text widget with properties
        text_widget = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Apply theme colors to text widget
        if hasattr(self.parent, 'bg_color') and hasattr(self.parent, 'fg_color'):
            text_widget.configure(bg=self.parent.bg_color, fg=self.parent.fg_color)
        
        # Add properties to text widget
        properties_text = f"""Name: {name}
Path: {path}
Permissions: {permissions}
Owner: {owner}
Group: {group}
Size: {size}
Date: {date}

Additional Info:
{stat_info}"""
        
        text_widget.insert(tk.END, properties_text)
        text_widget.config(state=tk.DISABLED)
        
        # Add close button
        close_button = ttk.Button(dialog, text="Close", command=dialog.destroy)
        close_button.pack(pady=10)

if __name__ == "__main__":
    app = Y1HelperApp()
    app.mainloop()































