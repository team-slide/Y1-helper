import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Menu, simpledialog
import subprocess
import threading
import time
import os
import struct
from PIL import Image, ImageTk
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

# Add this near the top, after imports
base_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(base_dir, 'assets')

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

def debug_print(message):
    """Print debug messages with timestamp"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[DEBUG {timestamp}] {message}")

# Patch debug_print to suppress output if flashing is active and not flashing-related
if not hasattr(builtins, '_original_debug_print'):
    builtins._original_debug_print = debug_print
    def debug_print(message):
        import inspect
        frame = inspect.currentframe().f_back
        self_obj = frame.f_locals.get('self', None)
        if self_obj and hasattr(self_obj, 'is_flashing_firmware') and getattr(self_obj, 'is_flashing_firmware', False):
            # Allow only if called from _flash_with_modal or _download_and_flash_selected_firmware
            stack = inspect.stack()
            allowed = any(
                fn.function in ('_flash_with_modal', '_download_and_flash_selected_firmware')
                for fn in stack
            )
            if not allowed:
                return
        builtins._original_debug_print(message)
    globals()['debug_print'] = debug_print

class Y1HelperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        debug_print("Initializing Y1HelperApp")
        
        # Base directory (for config file access)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check for and apply launcher updates
        launcher_updated = check_and_update_launcher()
        if launcher_updated:
            debug_print("Launcher was updated during startup")
        
        # Version information
        self.version = "0.6.1"
        
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
        # Clear assets/rom on launch
        rom_dir = os.path.join(assets_dir, "rom")
        if os.path.exists(rom_dir):
            for f in os.listdir(rom_dir):
                try:
                    os.remove(os.path.join(rom_dir, f))
                except Exception as e:
                    debug_print(f"Failed to remove {f} from rom/: {e}")
        else:
            os.makedirs(rom_dir, exist_ok=True)
        
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
        
        self.title(f"Y1 Helper v{self.version}")
        self.geometry("520x720")  # Increased width and height for better button spacing
        self.resizable(False, False)
        
        # Ensure window gets focus and appears in front
        self.lift()  # Bring window to front
        self.attributes('-topmost', True)  # Temporarily make topmost
        self.after(100, lambda: self.attributes('-topmost', False))  # Remove topmost after 100ms
        self.focus_force()  # Force focus to this window
        
        # Center window on screen
        self.update_idletasks()  # Update window info
        x = (self.winfo_screenwidth() // 2) - (520 // 2)
        y = (self.winfo_screenheight() // 2) - (720 // 2)
        self.geometry(f"520x720+{x}+{y}")
        
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
        self.firmware_manifest_url = "https://raw.githubusercontent.com/team-slide/slidia/main/slidia_manifest.xml"
        self.prepare_prompt_refused = False  # Track if user refused the initial prepare prompt
        self.prepare_prompt_shown = False  # Track if prepare prompt has been shown for current connection
        
        # Essential UI variables
        self.status_var = tk.StringVar(value="Ready")
        self.scroll_wheel_mode_var = tk.BooleanVar()  # Renamed from launcher_var
        self.disable_dpad_swap_var = tk.BooleanVar()  # Variable for D-pad swap control (now "Invert Scroll Direction")
        self.y1_launcher_detected = False  # Track if com.innioasis.y1 is detected
        self.rgb_profile_var = tk.StringVar(value="BGRA8888")
        
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
        """Parse the manifest XML to find app options"""
        try:
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
                    app_options.append({
                        'name': name,
                        'repo': repo,
                        'url': url,
                        'handler': handler
                    })
            
            debug_print(f"Found {len(app_options)} app options")
            return app_options
            
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
                listbox.insert(tk.END, f"★ {clean_name} (Latest)")
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
        
        # Wait for dialog to close
        dialog.wait_window()
        return selected_app
    
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
        """Download config.zip from GitHub and unpack config.ini to root directory"""
        try:
            config_url = "https://github.com/team-slide/Y1-helper/raw/refs/heads/master/config.zip"
            config_zip_path = os.path.join(self.base_dir, "config.zip")
            config_ini_path = os.path.join(self.base_dir, "config.ini")
            
            debug_print("Downloading config.zip...")
            
            # Download config.zip
            urllib.request.urlretrieve(config_url, config_zip_path)
            
            # Extract config.ini from the zip
            with zipfile.ZipFile(config_zip_path, 'r') as zip_ref:
                zip_ref.extract("config.ini", self.base_dir)
            
            # Clean up the zip file
            os.remove(config_zip_path)
            
            debug_print("Config.ini extracted successfully")
            
        except Exception as e:
            debug_print(f"Failed to download/unpack config.zip: {e}")
            # Continue without config.ini if download fails
    
    def get_random_api_key(self):
        """Get a random API key from config.ini for rate limit prevention - supports up to 1000+ tokens"""
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                return None
            
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Get all API keys from the config - support key_0 to key_1000+
            api_keys = []
            if 'api_keys' in config:
                # First try numbered keys (key_0, key_1, key_2, ..., key_1000+)
                for i in range(1001):  # Support up to key_1000
                    key_name = f'key_{i}'
                    if key_name in config['api_keys']:
                        value = config['api_keys'][key_name].strip()
                        if value:  # Only add non-empty keys
                            api_keys.append(value)
                
                # Also check for any other keys in the section
                for key, value in config['api_keys'].items():
                    if not key.startswith('key_') and value.strip():  # Non-numbered keys
                        api_keys.append(value.strip())
            
            # If no API keys found, try legacy github.token
            if not api_keys and 'github' in config and 'token' in config['github']:
                token = config['github']['token'].strip()
                if token:
                    api_keys.append(token)
            
            if api_keys:
                # Return a random key
                import random
                selected_key = random.choice(api_keys)
                debug_print(f"Selected API key from {len(api_keys)} available tokens")
                return selected_key
            
            debug_print("No API keys found in config.ini")
            return None
            
        except Exception as e:
            debug_print(f"Error getting API key: {e}")
            return None
    
    def add_api_key_to_config(self, new_key):
        """Add a new API key to config.ini - supports up to 1000+ tokens"""
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
            
            # Find next available key number (start from 0, support up to 1000+)
            key_number = 0
            while f'key_{key_number}' in config['api_keys'] and key_number <= 1000:
                key_number += 1
            
            # Add the new key
            config['api_keys'][f'key_{key_number}'] = new_key
            
            # Write back to file
            with open(config_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            debug_print(f"Added new API key (key_{key_number}) to config.ini - total tokens: {len(config['api_keys'])}")
            
        except Exception as e:
            debug_print(f"Error adding API key to config: {e}")
    
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
    
    def download_app(self, app_info):
        """Download app from GitHub releases with progress"""
        progress_dialog = None
        try:
            # Create progress dialog
            progress_dialog = self.create_progress_dialog("Downloading App")
            progress_dialog.progress_bar.start()
            
            def update_progress(message):
                try:
                    if progress_dialog and hasattr(progress_dialog, 'status_label'):
                        progress_dialog.status_label.config(text=message)
                        progress_dialog.update()
                    debug_print(f"App Download Progress: {message}")
                except Exception as e:
                    debug_print(f"Progress update failed: {e}")
            
            update_progress("Connecting to GitHub...")
            
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
                        with urllib.request.urlopen(urllib.request.Request(api_url, headers=headers)) as response:
                            release_data = json.loads(response.read().decode('utf-8'))
                            debug_print(f"Latest release data: {release_data.get('tag_name', 'unknown')} - {len(release_data.get('assets', []))} assets")
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            debug_print(f"Latest endpoint failed (404), trying first release...")
                            api_url = f"https://api.github.com/repos/{repo_path}/releases"
                            with urllib.request.urlopen(urllib.request.Request(api_url, headers=headers)) as response:
                                releases = json.loads(response.read().decode('utf-8'))
                                if releases:
                                    release_data = releases[0]
                                    debug_print(f"First release data: {release_data.get('tag_name', 'unknown')} - {len(release_data.get('assets', []))} assets")
                                else:
                                    raise Exception(f"No releases found for {repo_path}")
                        else:
                            raise Exception(f"GitHub API error: {e.code} - {e.reason}")
                elif '/releases/' in repo_url or repo_url.rstrip('/').endswith('/releases'):
                    # Handle /releases/ or /releases
                    repo_path = repo_url.replace('https://github.com/', '').split('/releases')[0]
                    debug_print(f"Parsed repo path: {repo_path}")
                    update_progress(f"Fetching latest release from {repo_path}...")
                    api_url = f"https://api.github.com/repos/{repo_path}/releases"
                    try:
                        with urllib.request.urlopen(urllib.request.Request(api_url, headers=headers)) as response:
                            releases = json.loads(response.read().decode('utf-8'))
                            if releases:
                                release_data = releases[0]
                                debug_print(f"First release data: {release_data.get('tag_name', 'unknown')} - {len(release_data.get('assets', []))} assets")
                            else:
                                raise Exception(f"No releases found for {repo_path}")
                    except urllib.error.HTTPError as e:
                        raise Exception(f"GitHub API error: {e.code} - {e.reason}")
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
            
            with urllib.request.urlopen(download_url) as response:
                # Get file size for progress
                file_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(download_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)  # 8KB chunks
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
            return None
        finally:
            # Always clean up progress dialog
            if progress_dialog:
                try:
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
                    if progress_dialog and hasattr(progress_dialog, 'status_label'):
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
            if hasattr(self, 'context_menu'):
                self.context_menu.configure(**menu_config)
            
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
            text="🕐 Set Time",
            command=self.sync_device_time,
            style="TButton"
        )
        self.set_time_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Install Firmware button with modern styling
        self.install_firmware_btn = ttk.Button(
            row1_frame,
            text="⚡ Install Firmware",
            command=self.install_firmware,
            style="TButton"
        )
        self.install_firmware_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Screenshot button with modern styling
        self.screenshot_btn = ttk.Button(
            row1_frame,
            text="📸 Screenshot",
            command=self.take_screenshot,
            style="TButton"
        )
        self.screenshot_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Row 2 - Navigation controls
        row2_frame = ttk.Frame(main_controls_frame)
        row2_frame.pack(fill=tk.X, pady=(6, 0))
        
        # Navigation buttons
        self.home_btn = ttk.Button(
            row2_frame,
            text="🏠 Home",
            command=self.go_home,
            style="TButton"
        )
        self.home_btn.pack(side=tk.LEFT, anchor="w")
        
        self.back_btn = ttk.Button(
            row2_frame,
            text="⬅ Back",
            command=self.send_back_key,
            style="TButton"
        )
        self.back_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        # Additional navigation buttons
        self.recent_btn = ttk.Button(
            row2_frame,
            text="📱 Recent",
            command=self.show_recent_apps,
            style="TButton"
        )
        self.recent_btn.pack(side=tk.LEFT, padx=(12, 0), anchor="w")
        
        self.menu_btn = ttk.Button(
            row2_frame,
            text="☰ Menu",
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
            text="▲",
            command=self.nav_up,
            style="TButton",
            width=3
        )
        self.dpad_up_btn.pack()
        
        # Middle row with left, center, right buttons
        middle_row = ttk.Frame(dpad_buttons_frame)
        middle_row.pack()
        
        self.dpad_left_btn = ttk.Button(
            middle_row,
            text="◀",
            command=self.nav_left,
            style="TButton",
            width=3
        )
        self.dpad_left_btn.pack(side=tk.LEFT)
        
        self.dpad_center_btn = ttk.Button(
            middle_row,
            text="●",
            command=self.nav_center,
            style="TButton",
            width=3
        )
        self.dpad_center_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        self.dpad_right_btn = ttk.Button(
            middle_row,
            text="▶",
            command=self.nav_right,
            style="TButton",
            width=3
        )
        self.dpad_right_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        # Down button
        self.dpad_down_btn = ttk.Button(
            dpad_buttons_frame,
            text="▼",
            command=self.nav_down,
            style="TButton",
            width=3
        )
        self.dpad_down_btn.pack()
        
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
        self.context_menu = Menu(self, tearoff=0, 
                                bg=self.menu_bg if hasattr(self, 'menu_bg') else "#ffffff",
                                fg=self.menu_fg if hasattr(self, 'menu_fg') else "#000000",
                                activebackground=self.menu_select_bg if hasattr(self, 'menu_select_bg') else "#0078d4",
                                activeforeground=self.menu_select_fg if hasattr(self, 'menu_select_fg') else "#ffffff",
                                relief="flat", bd=0)
        self.context_menu.add_command(label="Go Home", command=self.go_home)
        self.context_menu.add_command(label="Open Settings", command=self.launch_settings)
        self.context_menu.add_command(label="Recent Apps", command=self.show_recent_apps)
        
        # Apply theme colors to context menu
        if hasattr(self, 'apply_menu_colors'):
            self.apply_menu_colors()
        
        # Initially hide controls frame until device is connected
        self.hide_controls_frame()
        
        # Flag to track if input should be disabled (when showing ready.png)
        self.input_disabled = True
        
        # Mouse wheel bindings for Linux
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
        self.context_menu = Menu(self, tearoff=0, 
                                bg=self.menu_bg if hasattr(self, 'menu_bg') else "#ffffff",
                                fg=self.menu_fg if hasattr(self, 'menu_fg') else "#000000",
                                activebackground=self.menu_select_bg if hasattr(self, 'menu_select_bg') else "#0078d4",
                                activeforeground=self.menu_select_fg if hasattr(self, 'menu_select_fg') else "#ffffff",
                                relief="flat", bd=0)
        self.context_menu.add_command(label="Go Home", command=self.go_home)
        self.context_menu.add_command(label="Open Settings", command=self.launch_settings)
        self.context_menu.add_command(label="Recent Apps", command=self.show_recent_apps)
        
        # Apply theme colors to context menu
        if hasattr(self, 'apply_menu_colors'):
            self.apply_menu_colors()
        
        # Controls are always visible regardless of device connection
    
    def hide_controls_frame(self):
        """Hide the controls frame when no device is connected"""
        if hasattr(self, 'controls_frame'):
            self.controls_frame.pack_forget()
            debug_print("Controls frame hidden - no device connected")
    
    def show_controls_frame(self):
        """Show the controls frame when device is connected"""
        if hasattr(self, 'controls_frame'):
            self.controls_frame.pack(fill=tk.X, pady=(5, 0))
            debug_print("Controls frame shown - device connected")
    
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
        device_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Device", menu=device_menu)
        self.device_menu = device_menu
        
        # Add standard device menu items
        self.device_menu.add_command(label="Device Info", command=self.show_device_info)
        self.device_menu.add_command(label="ADB Shell", command=self.open_adb_shell)
        self.device_menu.add_command(label="File Explorer", command=self.open_file_explorer)
        self.device_menu.add_command(label="Take Screenshot", command=self.take_screenshot)
        self.device_menu.add_command(label="Recent Apps", command=self.show_recent_apps)
        self.device_menu.add_command(label="Change Device Language", command=self.change_device_language)
        self.device_menu.add_command(label="Sync Device Time", command=self.sync_device_time)
        self.device_menu.add_separator()
        self.device_menu.add_command(label="Install Firmware", command=self.install_firmware)
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
        
        # Apply theme colors
        self.apply_menu_colors()
    

    
    def refresh_apps(self):
        """Refresh list of installed apps (Apps menu only)"""
        debug_print("Refreshing apps list")
        self.apps_menu.delete(0, tk.END)
        self.apps_menu.add_command(label="Browse APKs...", command=self.browse_apks)
        self.apps_menu.add_command(label="Install Apps", command=self.install_apps)
        self.apps_menu.add_separator()
        
        # Get user-installed apps
        success_user, stdout_user, stderr_user = self.run_adb_command(
            "shell pm list packages -3 -f")
        user_apps = []
        
        # Get system apps
        success_system, stdout_system, stderr_system = self.run_adb_command(
            "shell pm list packages -s -f")
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
    
    def unified_device_check(self):
        """Unified method to check device connection and refresh app list with enhanced robustness"""
        # Use thread lock to prevent race conditions
        with self.device_connection_lock:
            try:
                adb_path = self.get_adb_path()
                current_time = time.time()
                
                # Check device connection with more robust parsing
                result = subprocess.run([adb_path, "devices"], 
                                      capture_output=True, text=True, timeout=3)
                
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
                            
                            # Always refresh apps when device is connected and validated
                            self.refresh_apps()
                        else:
                            # Device detected but not responsive
                            self.device_check_failures += 1
                            
                            if self.device_check_failures >= self.max_device_check_failures:
                                if self.device_connected:
                                    self.device_connected = False
                                    self.status_var.set("Device disconnected - not responsive")
                                    
                                    # Hide controls frame and disable input bindings
                                    self.hide_controls_frame()
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
                        
                        # Refresh apps even if validation was skipped
                        self.refresh_apps()
                        
                else:
                    # No device found
                    self.device_check_failures += 1
                    
                    if self.device_connected or self.device_check_failures >= self.max_device_check_failures:
                        self.device_connected = False
                        self.status_var.set("First time? Install a Firmware from the Device Menu.")
                        
                        # Hide controls frame and disable input bindings
                        self.hide_controls_frame()
                        self.disable_input_bindings()
                    
                self.last_device_check_time = current_time
                    
            except Exception as e:
                self.device_check_failures += 1
                
                if self.device_connected or self.device_check_failures >= self.max_device_check_failures:
                    self.device_connected = False
                    self.status_var.set("First time? Install a Firmware from the Device Menu.")
                    
                    # Hide controls frame and disable input bindings
                    self.hide_controls_frame()
                    self.disable_input_bindings()
        
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
                                   "• Start developing Y1 apps targeting Android API Level 16\n"
                                   "• Test apps on real hardware with the correct display and input setup\n"
                                   "• Use the full Y1 Helper functionality")
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
                        self.show_ready_placeholder()
                        placeholder_shown = True
                        self.status_var.set("First time? Install a Firmware from the Device Menu.")
                        # Disable input bindings when device is disconnected
                        self.disable_input_bindings()
                    time.sleep(1)  # Check less frequently when disconnected
                    continue
                
                # Reset placeholder flag when device is connected
                if placeholder_shown:
                    placeholder_shown = False
                    self.status_var.set("Device connected")
                    # Enable input bindings when device reconnects
                    self.enable_input_bindings()
                
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
                                    self.show_ready_placeholder()
                                    placeholder_shown = True
                                    self.status_var.set("First time? Install a Firmware from the Device Menu.")
                            self.last_framebuffer_refresh = current_time
                            self.force_refresh_requested = False
                    else:
                        # Framebuffer pull failed
                        self.consecutive_framebuffer_failures += 1
                        if self.consecutive_framebuffer_failures >= self.max_framebuffer_failures:
                            if not placeholder_shown:
                                self.show_ready_placeholder()
                                placeholder_shown = True
                                self.status_var.set("First time? Install a Firmware from the Device Menu.")
                        time.sleep(0.5)
                else:
                    # Sleep when not refreshing to reduce CPU usage
                    time.sleep(0.1)
                    
            except Exception as e:
                if not placeholder_shown:
                    self.device_connected = False
                    self.show_ready_placeholder()
                    placeholder_shown = True
                    self.status_var.set("First time? Install a Firmware from the Device Menu.")
                time.sleep(0.5)
    
    def process_framebuffer(self, fb_path):
        """Process framebuffer data and display on canvas (optimized)"""
        try:
            from PIL import Image
            if not os.path.exists(fb_path):
                debug_print("Framebuffer file does not exist")
                self.show_ready_placeholder()
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
                                pixel = (data[i + 1] << 8) | data[i]
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
                        arr = arr.reshape((self.device_height, self.device_width, int(expected_size // (self.device_width * self.device_height))))
                        arr = arr[..., [2, 1, 0, 3]] if arr.shape[2] == 4 else arr[..., [2, 1, 0]]
                        img = Image.fromarray(arr)
                        img_rgb = img.convert('RGB')
                    else:
                        img = Image.frombytes(pil_format, (self.device_width, self.device_height), data[:expected_size])
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
            self.screen_canvas.config(height=self.display_height)
            from PIL import Image, ImageDraw
            pil_img = None
            try:
                pil_img = Image.frombytes('RGB', (self.display_width, self.display_height), photo._PhotoImage__photo.convert('RGB').tobytes())
            except Exception:
                pil_img = None
            if pil_img is not None:
                draw = ImageDraw.Draw(pil_img, 'RGBA')
                nav_height = self.nav_bar_height
                nav_y = self.display_height - nav_height
                draw.rectangle([0, nav_y, self.display_width, self.display_height], fill=(0,0,0,255))
                btn_radius = nav_height // 2 - 2
                spacing = self.display_width // 4
                # Home button (right): left-pointing triangle
                hx = self.display_width - spacing
                hy = nav_y + nav_height // 2
                draw.polygon([
                    (hx+btn_radius, hy),
                    (hx-btn_radius, hy-btn_radius),
                    (hx-btn_radius, hy+btn_radius)
                ], fill=(255,255,255,220))
                # Back button (left): circle
                bx = spacing
                by = nav_y + nav_height // 2
                draw.ellipse([
                    (bx-btn_radius, by-btn_radius),
                    (bx+btn_radius, by+btn_radius)
                ], outline=(255,255,255,220), width=3)
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(pil_img)
            self.current_photo = photo
            self.screen_canvas.delete("all")
            self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=self.current_photo)
        except Exception as e:
            print(f"Display update error: {e}")
    

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
                from PIL import ImageDraw
                draw = ImageDraw.Draw(img)
                
                # Draw a simple "sleeping" icon (moon shape)
                center_x = self.display_width // 2
                center_y = self.display_height // 2
                radius = min(self.display_width, self.display_height) // 4
                
                # Draw a crescent moon
                draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius], 
                           outline=(100, 100, 100), width=3)
                draw.ellipse([center_x - radius//2, center_y - radius//2, center_x + radius//2, center_y + radius//2], 
                           fill=(20, 20, 20), outline=(20, 20, 20))
                
                # Add "Sleeping" text
                try:
                    from PIL import ImageFont
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
            self.screen_canvas.delete("all")
            self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            
            # Store reference
            if hasattr(self, 'current_photo'):
                del self.current_photo
            self.current_photo = photo
            
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
                from PIL import ImageDraw
                draw = ImageDraw.Draw(img)
                
                # Draw a simple "ready" icon (checkmark)
                center_x = self.display_width // 2
                center_y = self.display_height // 2
                size = min(self.display_width, self.display_height) // 6
                
                # Draw a checkmark
                draw.line([center_x - size, center_y, center_x, center_y + size], 
                         fill=(0, 255, 0), width=3)
                draw.line([center_x, center_y + size, center_x + size, center_y - size], 
                         fill=(0, 255, 0), width=3)
                
                # Add "Ready" text
                try:
                    from PIL import ImageFont
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
            self.screen_canvas.delete("all")
            self.screen_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            
            # Store reference
            if hasattr(self, 'current_photo'):
                del self.current_photo
            self.current_photo = photo
            
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
            self.status_var.set("Back button pressed")
            debug_print("BACK key sent successfully")
            # Force framebuffer refresh after sending input
            self.after(100, self.force_framebuffer_refresh)
        else:
            self.status_var.set(f"Back button failed: {stderr}")
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
            
            # Download and parse manifest
            manifest_url = "https://raw.githubusercontent.com/team-slide/slidia/main/slidia_manifest.xml"
            debug_print(f"Downloading manifest from: {manifest_url}")
            
            update_progress("Downloading app manifest...")
            with urllib.request.urlopen(manifest_url) as response:
                manifest_content = response.read().decode('utf-8')
            
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
                messagebox.showerror("No Apps Found", "There are currently no apps available on Slidia Installer. This will change in the future, come back soon!")
                return
            
            # Show app selection dialog
            selected_app = self.show_app_selection_dialog(app_options)
            if not selected_app:
                return
            
            # Download the selected app
            self.status_var.set(f"Downloading {selected_app['name']}...")
            app_path = self.download_app(selected_app)
            
            if not app_path:
                messagebox.showerror("Download Failed", "Failed to download the selected app.")
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
                    user_friendly_error = "App installation failed: No device connected via ADB.\n\nPlease ensure your device is:\n• Connected via USB\n• Has USB debugging enabled\n• Is authorized for ADB connections"
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
                              "• Select your preferred language\n"
                              "• Choose regional settings\n"
                              "• Configure input methods")
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
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            tooltip.geometry(f"+{x}+{y}")
            tooltip.deiconify()
        def leave(event):
            tooltip.withdraw()
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
    
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
                f"Current update branch: {current_branch}\n\nUse Ctrl+D → Change Update Branch to modify this."
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
        
        # Global key handling for all key presses
        self.bind_all("<Key>", self.on_key_press)
        # Global key release handling for cursor control
        self.bind_all("<KeyRelease>", self.on_key_release)
        debug_print("Key bindings set up complete")

    def _destroy_splash(self):
        if hasattr(self, '_splash') and self._splash.winfo_exists():
            self._splash.destroy()

    def show_firmware_progress_modal(self, title="Firmware Flash Progress"):
        import tkinter as tk
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("600x180")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        status_label = ttk.Label(frame, text="", font=("Segoe UI", 11), wraplength=560, justify=tk.CENTER)
        status_label.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        ok_button = ttk.Button(frame, text="OK", command=dialog.destroy, state=tk.DISABLED)
        ok_button.pack(pady=(10, 5))
        return dialog, status_label, ok_button

    def install_firmware(self, local_file=None):
        """Unified firmware flashing: handles both manifest and local file, always uses _download_and_flash_selected_firmware for robust debug and error handling."""
        debug_print(f"install_firmware called with local_file={local_file}")
        if local_file:
            # Treat local file as a firmware_info dict with a 'url' key
            firmware_info = {'url': local_file}
            self._download_and_flash_selected_firmware(firmware_info)
        else:
            manifest_url = "https://raw.githubusercontent.com/team-slide/slidia/main/slidia_manifest.xml"
            debug_print(f"Downloading manifest from: {manifest_url}")
            try:
                with urllib.request.urlopen(manifest_url) as response:
                    manifest_content = response.read().decode('utf-8')
                firmware_options = self.parse_firmware_manifest(manifest_content)
                if not firmware_options:
                    messagebox.showerror("No Firmware Found", "No firmware options found in the manifest.")
                    return
                selected_firmware = self.show_firmware_selection_dialog(firmware_options)
                if not selected_firmware:
                    return
                self._download_and_flash_selected_firmware(selected_firmware)
            except Exception as e:
                debug_print(f"Exception while downloading or parsing manifest: {e}")
                messagebox.showerror("Manifest Error", f"Failed to download or parse manifest: {e}")

    def browse_firmware_file(self):
        from tkinter import messagebox
        import tkinter as tk
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

    def _download_and_flash_selected_firmware(self, firmware_info):
        self.is_flashing_firmware = True
        REQUIRED_FILES = [
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
            "MT6572_Android_scatter.txt"
        ]
        try:
            import threading
            import tkinter as tk
            import requests
            import shutil
            firmware_dir = os.path.join(assets_dir, "rom")
            os.makedirs(firmware_dir, exist_ok=True)
            dialog = tk.Toplevel(self)
            dialog.title("Firmware Flash Progress")
            dialog.geometry("600x200")
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
                            dialog.after(0, status_label.config, {"text": "Downloading rom.zip..."})
                            
                            with requests.get(download_url, stream=True) as response:
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
                                        dialog.after(0, status_label.config, {"text": f"Downloading rom.zip... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
                                        dialog.after(0, progress_bar.step, (len(chunk),))
                                dialog.after(0, lambda: progress_bar.config(value=0))
                            
                            # Extract rom.zip
                            dialog.after(0, status_label.config, {"text": "Extracting rom.zip..."})
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
                                dialog.after(0, status_label.config, {"text": f"Extracted {len(extracted_files)} files from rom.zip"})
                                
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
                                    dialog.after(0, status_label.config, {"text": f"Downloading {name}..."})
                                    with requests.get(download_url, stream=True) as response:
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
                                                dialog.after(0, status_label.config, {"text": f"Downloading {name}... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
                                                dialog.after(0, progress_bar.step, (len(chunk),))
                                        dialog.after(0, lambda: progress_bar.config(value=0))
                                    downloaded_files[name] = dest_path
                    else:
                        # Direct URL to a single file (legacy/local)
                        name = os.path.basename(repo_url)
                        if name.endswith('.img') or name.endswith('.bin'):
                            dest_path = os.path.join(firmware_dir, name)
                            dialog.after(0, status_label.config, {"text": f"Downloading {name}..."})
                            with requests.get(repo_url, stream=True) as response:
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
                                        dialog.after(0, status_label.config, {"text": f"Downloading {name}... {percent:.1f}% ({downloaded // (1024*1024)}MB / {file_size // (1024*1024)}MB)"})
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
                    # Copy missing required files from assets
                    for req_file in REQUIRED_FILES:
                        dest_path = os.path.join(firmware_dir, req_file)
                        if not os.path.exists(dest_path):
                            src_path = os.path.join(assets_dir, req_file)
                            if os.path.exists(src_path):
                                shutil.copy2(src_path, dest_path)
                    dialog.after(0, status_label.config, {"text": "All firmware files prepared. Starting flash..."})
                    dialog.after(0, warn_label.pack_forget)
                    dialog.after(0, status_label.config, {"text": "Please connect your device and wait a few minutes."})
                    time.sleep(1.0)
                    debug_print(f"Starting flash with system.img at: {os.path.join(firmware_dir, 'system.img')}")
                    self._flash_with_modal(dialog, status_label, ok_button, os.path.join(firmware_dir, "system.img"), progress_bar)
                except Exception as e:
                    debug_print(f"Exception in do_download_and_flash: {e}")
                    dialog.after(0, status_label.config, {"text": f"Error: {e}"})
                    dialog.after(0, ok_button.config, {"state": "normal"})
            threading.Thread(target=do_download_and_flash, daemon=True).start()
            dialog.wait_window()
        finally:
            self.is_flashing_firmware = False

    def _flash_with_modal(self, dialog, status_label, ok_button, firmware_path, progress_bar=None):
        import tkinter as tk
        import subprocess
        import threading
        try:
            debug_print("Entered _flash_with_modal")
            flash_tool_path = os.path.join(assets_dir, "flash_tool.exe")
            install_rom_path = os.path.join(assets_dir, "install_rom.xml")
            debug_print(f"Checking for flash_tool.exe at: {flash_tool_path}")
            if not os.path.exists(flash_tool_path):
                debug_print("flash_tool.exe not found!")
                dialog.after(0, status_label.config, {"text": "SP Flash Tool not found in assets directory"})
                dialog.after(0, ok_button.pack)
                dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                return
            debug_print(f"Checking for install_rom.xml at: {install_rom_path}")
            if not os.path.exists(install_rom_path):
                debug_print("install_rom.xml not found!")
                dialog.after(0, status_label.config, {"text": "install_rom.xml not found in assets directory"})
                dialog.after(0, ok_button.pack)
                dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                return
            if progress_bar is None:
                progress_bar = tk.ttk.Progressbar(dialog, mode="determinate", maximum=100)
                progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
            else:
                progress_bar.config(mode="determinate", maximum=100)
            progress_bar.config(value=0)
            dialog.after(0, ok_button.pack_forget)
            command = [flash_tool_path, "-b", "-i", "install_rom.xml"]
            debug_print(f"About to run flash command: {' '.join(command)} (cwd=assets)")
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
                    
                    elapsed = time.time() - start_time
                    if elapsed >= progress_duration:
                        # Progress complete, stop timer
                        dialog.after(0, progress_bar.config, {"value": 100})
                        return
                    
                    # Calculate progress percentage
                    progress_percent = min(int((elapsed / progress_duration) * 100), 99)
                    dialog.after(0, progress_bar.config, {"value": progress_percent})
                    
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
                    universal_newlines=True,
                    bufsize=1
                )
                for line in iter(process.stdout.readline, ''):
                    line = line.rstrip('\r\n')
                    debug_print(f"[FLASH-TOOL RAW] {repr(line)}")
                    print(line)
                    if not line:
                        continue
                    # Only update status label at completion or failure
                    if 'All command exec done!' in line:
                        all_done_seen = True
                        # Cancel progress timer and set to 100%
                        if progress_timer:
                            progress_timer.cancel()
                        dialog.after(0, progress_bar.config, {"value": 100})
                        dialog.after(0, status_label.config, {"text": "Firmware installation complete! This window will close automatically in 3 seconds."})
                        dialog.after(0, ok_button.pack)
                        dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                        debug_print("[UI] Status label updated: Firmware installation complete! This window will close automatically in 3 seconds.")
                        threading.Timer(3.0, lambda: dialog.destroy() if dialog.winfo_exists() else None).start()
                    if all_done_seen and 'Disconnect!' in line:
                        disconnect_seen = True
                        flash_done = True
                    # Improved error handling for BROM/COM failures
                    if ('Connect BROM failed' in line or 'S_COM_PORT_OPEN_FAIL' in line or 'S_BROM_CMD_STARTCMD_FAIL' in line):
                        flash_done = True
                        error_seen = True
                        # Cancel progress timer
                        if progress_timer:
                            progress_timer.cancel()
                        dialog.after(0, status_label.config, {"text": "Flashing failed: Could not connect to device.\n\nPlease check your USB cable, drivers, and ensure the device is in the correct mode (powered off, battery charged, correct USB port). Try a different cable or port if needed."})
                        dialog.after(0, ok_button.pack)
                        dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                        debug_print("[UI] Status label updated: Flashing failed due to BROM/COM port error.")
                    # Only treat as a generic error if 'error' or 'fail' actually appears
                    if 'Download failed' in line or 'error' in line.lower() or 'fail' in line.lower():
                        flash_done = True
                        error_seen = True
                        # Cancel progress timer
                        if progress_timer:
                            progress_timer.cancel()
                        dialog.after(0, status_label.config, {"text": "Firmware installation failed. Try again after pressing the reset button with a paperclip."})
                        dialog.after(0, ok_button.pack)
                        dialog.after(0, ok_button.config, {"state": tk.NORMAL})
                        debug_print("[UI] Status label updated: Firmware installation failed. Try again after pressing the reset button with a paperclip.")
                process.wait()
                if not flash_done and not all_done_seen:
                    # Cancel progress timer
                    if progress_timer:
                        progress_timer.cancel()
                    if error_seen:
                        dialog.after(0, status_label.config, {"text": "Flashing process failed. Please check the above output for details."})
                        debug_print("[UI] Status label updated: Flashing process failed. Please check the above output for details.")
                    else:
                        dialog.after(0, status_label.config, {"text": "Flashing process finished. Please check the above output for results."})
                        debug_print("[UI] Status label updated: Flashing process finished. Please check the above output for results.")
                    dialog.after(0, ok_button.pack)
                    dialog.after(0, ok_button.config, {"state": tk.NORMAL})
            threading.Thread(target=run_flash, daemon=True).start()
        except Exception as e:
            debug_print(f"Exception in _flash_with_modal: {e}")
            dialog.after(0, status_label.config, {"text": f"Error during firmware flashing: {e}"})
            dialog.after(0, ok_button.pack)
            dialog.after(0, ok_button.config, {"state": tk.NORMAL})



    def create_progress_dialog(self, title="Progress"):
        """Create a progress dialog with status and progress bar"""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("400x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (150 // 2)
        dialog.geometry(f"400x150+{x}+{y}")
        
        # Create frame
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Status label
        status_label = ttk.Label(frame, text="Initializing...", font=("Segoe UI", 10))
        status_label.pack(pady=(0, 15))
        
        # Progress bar
        progress_bar = ttk.Progressbar(frame, mode='indeterminate', length=300)
        progress_bar.pack(pady=(0, 10))
        
        # Store references
        dialog.status_label = status_label
        dialog.progress_bar = progress_bar
        
        return dialog

    def parse_firmware_manifest(self, manifest_content):
        """Parse the manifest XML to find firmware options"""
        try:
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
                    firmware_options.append({
                        'name': name,
                        'repo': repo,
                        'url': url,
                        'handler': handler
                    })
            
            debug_print(f"Found {len(firmware_options)} firmware options")
            return firmware_options
            
        except Exception as e:
            debug_print(f"Error parsing manifest: {e}")
            return []

    def show_firmware_selection_dialog(self, firmware_options):
        import tkinter as tk
        from tkinter import filedialog
        dialog = tk.Toplevel(self)
        dialog.title("Select Firmware")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        label = ttk.Label(frame, text="Select a firmware to install:", font=("Segoe UI", 11))
        label.pack(pady=(0, 10))
        listbox = tk.Listbox(frame, font=("Segoe UI", 10))
        listbox.pack(fill=tk.BOTH, expand=True)
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
        ttk.Button(toolbar, text="↑ Up", command=self.go_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="🏠 Home", command=self.go_home).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="📁 Root", command=self.go_root).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="🔄 Refresh", command=self.refresh_current).pack(side=tk.LEFT, padx=(0, 5))
        
        # Path display
        ttk.Label(toolbar, text="Path:").pack(side=tk.LEFT, padx=(20, 5))
        self.path_var = tk.StringVar(value="/")
        path_entry = ttk.Entry(toolbar, textvariable=self.path_var, width=50)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        path_entry.bind('<Return>', self.navigate_to_path)
        
        # File operations toolbar
        file_toolbar = ttk.Frame(main_frame)
        file_toolbar.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_toolbar, text="📋 Copy", command=self.copy_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="✂️ Cut", command=self.cut_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="📌 Paste", command=self.paste_items).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="🗑️ Delete", command=self.delete_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="✏️ Rename", command=self.rename_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="📁 New Folder", command=self.create_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_toolbar, text="📄 New File", command=self.create_file).pack(side=tk.LEFT, padx=(0, 5))
        
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
        self.tree.column("#0", width=300, minwidth=200)
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
                        icon = "📁" if item['is_dir'] else "📄"
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
        if item['text'].startswith('📁'):
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
        
        if item['text'].startswith('📁'):
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
        
        if item['text'].startswith('📁'):
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
                'is_dir': item['text'].startswith('📁')
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
        
        # Create text widget with properties
        text_widget = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        properties_text = f"""Properties for: {name}

Path: {path}
Permissions: {permissions}
Owner: {owner}:{group}
Size: {size}
Modified: {date}

Detailed Information:
{stat_info}

Permissions Breakdown:
{self.parse_permissions(permissions)}
"""
        
        text_widget.insert(tk.END, properties_text)
        text_widget.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
        
    def parse_permissions(self, permissions):
        """Parse and explain file permissions"""
        if len(permissions) != 10:
            return "Invalid permissions format"
            
        perms = permissions[1:]  # Remove file type
        owner = perms[:3]
        group = perms[3:6]
        other = perms[6:9]
        
        def explain_perms(perms):
            result = []
            if perms[0] == 'r': result.append("read")
            if perms[1] == 'w': result.append("write")
            if perms[2] == 'x': result.append("execute")
            return ', '.join(result) if result else "none"
            
        return f"""Owner: {explain_perms(owner)}
Group: {explain_perms(group)}
Others: {explain_perms(other)}"""

if __name__ == "__main__":
    debug_print("Starting Y1 Helper application")
    app = Y1HelperApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    debug_print("Entering main loop")
    app.mainloop()
