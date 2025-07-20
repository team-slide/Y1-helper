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

def debug_print(message):
    """Print debug messages with timestamp"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[DEBUG {timestamp}] {message}")

class Y1HelperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        debug_print("Initializing Y1HelperApp")
        
        # Version information
        self.version = "0.5.0"
        
        # Write version.txt file
        self.write_version_file()
        
        self.title(f"Y1 Helper v{self.version}")
        self.geometry("452x661")  # Increased by 32px width and 32px height
        self.resizable(False, False)
        
        # Ensure window gets focus and appears in front
        self.lift()  # Bring window to front
        self.attributes('-topmost', True)  # Temporarily make topmost
        self.after(100, lambda: self.attributes('-topmost', False))  # Remove topmost after 100ms
        self.focus_force()  # Force focus to this window
        
        # Center window on screen
        self.update_idletasks()  # Update window info
        x = (self.winfo_screenwidth() // 2) - (452 // 2)
        y = (self.winfo_screenheight() // 2) - (661 // 2)
        self.geometry(f"452x661+{x}+{y}")
        
        # Detect Windows 11 theme
        self.setup_windows_11_theme()
        
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
        self.prepare_device_visible = False  # Track if Prepare Device menu item is visible
        self.device_prepared = None  # Track if device has stock launcher installed
        self.prepare_prompt_refused = False  # Track if user refused the initial prepare prompt
        self.prepare_prompt_shown = False  # Track if prepare prompt has been shown for current connection
        
        # Essential UI variables
        self.status_var = tk.StringVar(value="Ready")
        self.scroll_wheel_mode_var = tk.BooleanVar()  # Renamed from launcher_var
        self.disable_dpad_swap_var = tk.BooleanVar()  # New variable for D-pad swap control
        self.rgb_profile_var = tk.StringVar(value="BGRA8888")
        
        # Add input pacing: minimum delay between input events (in seconds)
        self.input_pacing_interval = 0.1  # 100ms
        self.last_input_time = 0
        
        # Scroll cursor variables
        self.scroll_cursor_active = False
        self.scroll_cursor_timer = None
        self.scroll_cursor_duration = 25  # Very brief cursor display (25ms) - reduced for better responsiveness
        
        # Performance optimization variables
        self.framebuffer_refresh_interval = 4.0  # Refresh every 4 seconds
        self.last_framebuffer_refresh = 0
        self.unified_check_interval = 10  # Check device and refresh apps every 10 seconds
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
        
        # Input mode persistence
        self.manual_mode_override = False  # Track if user manually changed mode
        self.last_manual_mode_change = time.time()
        
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
            # Hide controls frame and disable input bindings when no device is connected
            self.hide_controls_frame()
            self.disable_input_bindings()
        else:
            # Device is connected, show controls
            self.show_controls_frame()
            self.enable_input_bindings()
        
        # Set device to stay awake while charging
        self.set_device_stay_awake()
        
        # Detect current app and set launcher control (and start periodic check) only if device is connected
        if self.device_connected:
            self.detect_current_app()
        
        # Start screen capture immediately
        self.start_screen_capture()
        debug_print("Y1HelperApp initialization complete")
    
    def write_version_file(self):
        """Write version information to version.txt file"""
        try:
            version_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")
            with open(version_file_path, 'w', encoding='utf-8') as f:
                f.write(f"Y1 Helper v{self.version}\n")
                f.write(f"Build Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
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
        """Get ADB executable path without subdirectories"""
        debug_print("Getting ADB path")
        if platform.system() == "Windows":
            adb_path = "adb.exe"
        else:
            adb_path = "adb"
        
        # Check if ADB exists in current directory
        if os.path.exists(adb_path):
            debug_print(f"Found ADB at: {os.path.abspath(adb_path)}")
            return adb_path
        
        # Fallback to platform-tools if not in current directory
        fallback_path = os.path.join("platform-tools", adb_path)
        if os.path.exists(fallback_path):
            debug_print(f"Found ADB at fallback path: {os.path.abspath(fallback_path)}")
            return fallback_path
        
        debug_print(f"ADB not found at {adb_path} or {fallback_path}")
        return adb_path  # Return the expected path anyway
    
    def setup_ui(self):
        # Main frame with modern styling
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Screen viewer frame with modern styling
        screen_frame = ttk.LabelFrame(main_frame, text="Mouse Input Panel (480x360)", padding=5)
        screen_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Create canvas for screen display (scaled down to 75%) with modern styling
        self.screen_canvas = tk.Canvas(screen_frame, width=self.display_width, height=self.display_height, 
                                     bg='black', cursor='hand2', highlightthickness=0, bd=0,
                                     relief="flat")
        self.screen_canvas.pack()
        self.screen_canvas.config(width=self.display_width, height=self.display_height)
        
        # Create controls display frame with modern styling
        self.controls_frame = ttk.LabelFrame(screen_frame, text="Controls", padding=3)
        self.controls_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Controls display label with compact font
        self.controls_label = ttk.Label(self.controls_frame, text="", justify=tk.LEFT, 
                                       font=("Segoe UI", 8))
        self.controls_label.pack(anchor="w")
        
        # Mode selection frame with reduced padding
        mode_frame = ttk.Frame(self.controls_frame)
        mode_frame.pack(fill=tk.X, pady=(3, 0))
        
        # Input Mode toggle button with modern styling
        self.input_mode_btn = ttk.Button(
            mode_frame,
            text="Touch Screen Mode",
            command=self.toggle_scroll_wheel_mode,
            style="TButton"
        )
        self.input_mode_btn.pack(side=tk.LEFT, anchor="w")
        
        # Screenshot button with modern styling
        self.screenshot_btn = ttk.Button(
            mode_frame,
            text="📸 Screenshot",
            command=self.take_screenshot,
            style="TButton"
        )
        self.screenshot_btn.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
        
        # Navigation buttons
        self.home_btn = ttk.Button(
            mode_frame,
            text="🏠 Home",
            command=self.go_home,
            style="TButton"
        )
        self.home_btn.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
        
        self.back_btn = ttk.Button(
            mode_frame,
            text="⬅ Back",
            command=self.send_back_key,
            style="TButton"
        )
        self.back_btn.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
        
        # Additional navigation buttons
        self.recent_btn = ttk.Button(
            mode_frame,
            text="📱 Recent",
            command=self.show_recent_apps,
            style="TButton"
        )
        self.recent_btn.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
        
        self.menu_btn = ttk.Button(
            mode_frame,
            text="☰ Menu",
            command=self.nav_center,
            style="TButton"
        )
        self.menu_btn.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
        
        # Disable D-pad swap checkbox with modern styling
        self.disable_swap_checkbox = ttk.Checkbutton(
            mode_frame,
            text="Disable D-pad Swap",
            variable=self.disable_dpad_swap_var,
            command=self.update_controls_display,
            style="TCheckbutton"
        )
        self.disable_swap_checkbox.pack(side=tk.LEFT, padx=(10, 0), anchor="w")
        self.disable_swap_checkbox.pack_forget()  # Hidden by default
        
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
            "When checked, disables the D-pad swap in Scroll Wheel Mode. "
            "Use this for half-optimised Y1 apps that still need work and expect normal D-pad behavior."
        ))
        
        # Status bar at bottom with modern styling
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
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
            if self.disable_dpad_swap_var.get():
                # Disable D-pad swap mode - show normal D-pad controls
                controls_text = (
                    "Scroll Wheel Mode (D-pad Swap Disabled):\n"
                    "Touch: Left Click | Back: Right Click\n"
                    "D-pad: W/A/S/D or Arrow Keys\n"
                    "Enter: Wheel Click, Enter, E\n"
                    "Toggle: Alt"
                )
            else:
                # Normal scroll wheel mode - show scroll wheel mapping
                controls_text = (
                    "Scroll Wheel Mode:\n"
                    "Touch: Left Click | Back: Right Click\n"
                    "Scroll: W/S or Up/Down Arrows sends DPAD_LEFT/DPAD_RIGHT\n"
                    "D-pad: A/D or Left/Right Arrows sends DPAD_UP/DPAD_DOWN\n"
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
        debug_print("Controls display updated")
    
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
        self.prepare_device_menu_item = device_menu.add_command(label="Prepare Device", command=self.prepare_device)
        device_menu.add_command(label="Launch Settings", command=self.launch_settings)
        device_menu.add_command(label="Go Home", command=self.go_home)
        self.device_menu = device_menu
        self.apps_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Apps", menu=self.apps_menu)
        self.apps_menu.add_command(label="Install APK...", command=self.install_apk)
        self.apps_menu.add_separator()
        self.refresh_apps()  # Populate on startup
        
        # Debug menu (hidden by default, shown with Ctrl+D)
        self.debug_menu = Menu(menubar, tearoff=0)
        self.debug_menu.add_command(label="Change Update Branch...", command=self.change_update_branch)
        self.debug_menu.add_command(label="Show Current Branch", command=self.show_current_branch)
        self.debug_menu.add_separator()
        self.debug_menu.add_command(label="Run Updater", command=self.run_updater)
        
        self.update_device_menu()
        
        # Apply theme colors to menus
        self.apply_menu_colors()
    
    def update_device_menu(self):
        """Update dynamic items in the Device menu (Nova Launcher, KeyCodeDisp, other launchers)"""
        # Remove all items after the static ones (up to and including Go Home)
        static_count = 3  # Prepare Device, Launch Settings, Go Home
        total_items = self.device_menu.index('end')
        if total_items is not None and total_items > static_count:
            for i in range(total_items, static_count, -1):
                self.device_menu.delete(i)
        # Only add dynamic items if device is connected
        if not getattr(self, 'device_connected', False):
            return
        # Get installed packages
        success, stdout, stderr = self.run_adb_command("shell pm list packages -3 -f")
        nova_installed = False
        keycode_installed = False
        extra_launchers = []
        launcher_pkgs = [
            ("com.teslacoilsw.launcher", "Open Nova Launcher"),
            ("com.android.launcher", "Open Android Launcher"),
            ("com.lge.launcher2", "Open LG Launcher"),
            ("com.sec.android.app.launcher", "Open Samsung Launcher"),
            ("com.miui.home", "Open MIUI Launcher")
        ]
        keycode_pkg = "jp.ne.neko.freewing.KeyCodeDisp"
        if success:
            for line in stdout.strip().split('\n'):
                if line.startswith('package:'):
                    if '=' in line:
                        package_name = line.split('=')[1]
                    else:
                        package_name = line[len('package:'):]
                    if package_name == "com.teslacoilsw.launcher":
                        nova_installed = True
                    if package_name == keycode_pkg:
                        keycode_installed = True
                    for pkg, label in launcher_pkgs:
                        if package_name == pkg and pkg != "com.teslacoilsw.launcher":
                            extra_launchers.append((pkg, label))
        self.device_menu.add_separator()
        if nova_installed:
            self.device_menu.add_command(label="Open Nova Launcher", command=self.open_nova_launcher)
        if keycode_installed:
            self.device_menu.add_command(label="View Input Keycodes", command=self.open_keycode_disp)
        for pkg, label in extra_launchers:
            self.device_menu.add_command(label=label, command=lambda p=pkg: self.open_launcher(p))
        self.device_menu.add_separator()
        self.device_menu.add_command(label="ADB Shell", command=self.open_adb_shell)
        self.device_menu.add_command(label="Device Info", command=self.show_device_info)
        self.device_menu.add_command(label="Change Device Language", command=self.change_device_language)
        self.device_menu.add_separator()
        self.device_menu.add_command(label="File Explorer", command=self.open_file_explorer)
        self.device_menu.add_separator()
        self.device_menu.add_command(label="Exit", command=self.quit)
        
        # Apply theme colors to updated device menu
        if hasattr(self, 'apply_menu_colors'):
            self.apply_menu_colors()
    
    def refresh_apps(self):
        """Refresh list of installed apps (Apps menu only)"""
        debug_print("Refreshing apps list")
        self.apps_menu.delete(0, tk.END)
        self.apps_menu.add_command(label="Install APK...", command=self.install_apk)
        self.apps_menu.add_separator()
        success, stdout, stderr = self.run_adb_command(
            "shell pm list packages -3 -f")
        apps = []
        launcher_pkgs = [
            "com.teslacoilsw.launcher",
            "com.android.launcher",
            "com.lge.launcher2",
            "com.sec.android.app.launcher",
            "com.miui.home",
            "com.innioasis.y1",
            "com.ayst.factorytest",
            "jp.ne.neko.freewing.KeyCodeDisp"
        ]
        if success:
            debug_print(f"Found {len(stdout.strip().split('\n'))} package lines")
            for line in stdout.strip().split('\n'):
                if line.startswith('package:'):
                    if '=' in line:
                        package_name = line.split('=')[1]
                    else:
                        package_name = line[len('package:'):]
                    if package_name in launcher_pkgs:
                        debug_print(f"Skipping launcher package: {package_name}")
                        continue
                    apps.append(package_name)
        apps = [a for a in apps if a and a.strip()]
        debug_print(f"Found {len(apps)} user apps")
        if not apps:
            self.apps_menu.add_command(label="No user apps installed", state="disabled")
            debug_print("No user apps found")
        else:
            for app in sorted(apps):
                app_menu = Menu(self.apps_menu, tearoff=0)
                app_menu.add_command(label="Launch", command=lambda a=app: self.launch_app(a))
                app_menu.add_command(label="Uninstall", command=lambda a=app: self.uninstall_app(a))
                self.apps_menu.add_cascade(label=app, menu=app_menu)
                
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
            debug_print(f"Added {len(apps)} apps to menu")
    
    def unified_device_check(self):
        """Unified method to check device connection and refresh app list"""
        debug_print("Performing unified device check")
        try:
            adb_path = self.get_adb_path()
            
            # Check device connection
            result = subprocess.run([adb_path, "devices"], 
                                  capture_output=True, text=True, timeout=5)
            debug_print(f"ADB devices output: {result.stdout.strip()}")
            
            if "device" in result.stdout and "List of devices" in result.stdout:
                # Device is connected
                if not self.device_connected:
                    # Device just reconnected
                    self.device_connected = True
                    self.status_var.set("Device connected")
                    debug_print("Device reconnected")
                    
                    # Show controls frame and enable input bindings when device connects
                    self.show_controls_frame()
                    self.enable_input_bindings()
                    
                    # Set device to stay awake
                    self.set_device_stay_awake()
                    
                    # Check if device is prepared (has stock launcher)
                    if self.check_device_prepared() is False and not self.prepare_prompt_shown and self.device_prepared is not None:
                        # Only show prompt if we are certain device is connected and not prepared
                        self.prepare_prompt_shown = True
                        debug_print("Showing unprepared device prompt")
                        self.after(1000, self.show_unprepared_device_prompt)  # Delay to let UI settle
                
                # Always refresh apps when device is connected
                self.refresh_apps()
                debug_print("Apps refreshed")
                
            else:
                # Device is not connected
                if self.device_connected:
                    # Device just disconnected
                    self.device_connected = False
                    self.status_var.set("Device disconnected - Please reconnect")
                    debug_print("Device disconnected")
                    
                    # Hide controls frame and disable input bindings when device disconnects
                    self.hide_controls_frame()
                    self.disable_input_bindings()
                    
                    self.hide_prepare_device_menu()
                    self.prepare_prompt_refused = False
                    self.prepare_prompt_shown = False
                else:
                    self.status_var.set("No ADB device found")
                    self.device_connected = False
                    debug_print("No ADB device found")
                    
                    # Hide controls frame and disable input bindings when no device is found
                    self.hide_controls_frame()
                    self.disable_input_bindings()
                    
        except Exception as e:
            debug_print(f"Unified device check failed: {e}")
            if self.device_connected:
                self.device_connected = False
                self.status_var.set("Device disconnected - Please reconnect")
                debug_print("Device disconnected due to error")
                
                # Hide controls frame and disable input bindings when device disconnects due to error
                self.hide_controls_frame()
                self.disable_input_bindings()
                
                self.hide_prepare_device_menu()
                self.prepare_prompt_refused = False
                self.prepare_prompt_shown = False
            else:
                self.status_var.set(f"ADB Error: {str(e)}")
                self.device_connected = False
    
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
                
                # Hide prepare device menu for Y1 apps
                if self._should_show_launcher_toggle(detected_package):
                    self.hide_prepare_device_menu()
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
    
    def hide_prepare_device_menu(self):
        """Hide the Prepare Device menu item"""
        if hasattr(self, 'device_menu') and self.prepare_device_visible:
            self.device_menu.entryconfig("Prepare Device", state="disabled")
            self.prepare_device_visible = False
    
    def show_prepare_device_menu(self):
        """Show the Prepare Device menu item"""
        if hasattr(self, 'device_menu') and not self.prepare_device_visible and self.device_connected and self.prepare_prompt_refused:
            self.device_menu.entryconfig("Prepare Device", state="normal")
            self.prepare_device_visible = True
    
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
            self.prepare_device()
        else:
            # User refused the prompt - show Prepare Device menu option
            self.prepare_prompt_refused = True
            self.show_prepare_device_menu()
    
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
        """Optimized screen capture loop with reduced refresh rate"""
        debug_print("Starting optimized screen capture loop")
        import tempfile
        import os
        
        temp_dir = tempfile.gettempdir()
        fb_temp_path = os.path.join(temp_dir, "y1_fb0.tmp")
        debug_print(f"Using temp file: {fb_temp_path}")
        placeholder_shown = False
        
        while self.is_capturing:
            try:
                current_time = time.time()
                
                # Periodically check device connection status (less frequent)
                if current_time - self.last_unified_check > self.unified_check_interval:
                    debug_print("Performing periodic connection check")
                    self.unified_device_check()
                    self.last_unified_check = current_time
                
                # Check if device is connected
                if not self.device_connected:
                    if not placeholder_shown:
                        debug_print("Device disconnected, showing ready placeholder")
                        self.show_ready_placeholder()
                        placeholder_shown = True
                        self.status_var.set("Device disconnected - Please reconnect")
                        # Disable input bindings when device is disconnected
                        self.disable_input_bindings()
                    time.sleep(2)  # Check less frequently when disconnected
                    continue
                
                # Reset placeholder flag when device is connected
                if placeholder_shown:
                    placeholder_shown = False
                    debug_print("Device reconnected, hiding placeholder")
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
                    debug_print("Pulling framebuffer from device (optimized refresh)")
                    success, stdout, stderr = self.run_adb_command(f"pull /dev/graphics/fb0 \"{fb_temp_path}\"")
                    if success:
                        if os.path.exists(fb_temp_path):
                            debug_print("Framebuffer pulled successfully, processing")
                            self.process_framebuffer(fb_temp_path)
                            self.last_framebuffer_refresh = current_time
                            self.force_refresh_requested = False
                        else:
                            debug_print("Framebuffer pull succeeded but file doesn't exist, showing ready.png")
                            self.show_ready_placeholder()
                            self.last_framebuffer_refresh = current_time
                            self.force_refresh_requested = False
                    else:
                        debug_print("Framebuffer pull failed - device disconnected")
                        # If framebuffer pull fails, device is disconnected
                        if not placeholder_shown:
                            self.device_connected = False
                            debug_print("Device appears disconnected, showing ready placeholder")
                            self.show_ready_placeholder()
                            placeholder_shown = True
                            self.status_var.set("Device disconnected - Please reconnect")
                        time.sleep(1)
                else:
                    # Sleep longer when not refreshing to reduce CPU usage
                    time.sleep(0.5)
                    
            except Exception as e:
                debug_print(f"Capture loop error: {e}")
                if not placeholder_shown:
                    self.device_connected = False
                    self.show_ready_placeholder()
                    placeholder_shown = True
                    self.status_var.set("Device disconnected - Please reconnect")
                time.sleep(1)
    
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
    
    def install_apk(self):
        """Install APK file"""
        file_path = filedialog.askopenfilename(
            title="Select APK file",
            filetypes=[("APK files", "*.apk"), ("All files", "*.*")]
        )
        if file_path:
            self.status_var.set("Installing APK...")
            
            # Convert to absolute path using platform-appropriate methods
            import os
            import platform
            file_path = os.path.abspath(file_path)
            
            # Use the full path in the ADB command
            success, stdout, stderr = self.run_adb_command(f"install -r \"{file_path}\"")
            
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
    
    def prepare_device(self):
        """Install stock Y1 launcher from 2.1.9 update for development, plus Nova Launcher and KeyCodeDisp if available"""
        import os
        from tkinter import messagebox
        # Show friendly preparation dialog
        prep_msg = (
            "Preparing your Y1 device for development!\n\n"
            "Here's what will happen:\n"
            "• The device will be set to Android 4.2.2, matching your PC's language and region.\n"
            "• KeyCodeDisp will be installed to help you understand all available input events.\n"
            "• Nova Launcher will be installed so you can launch it from the utility if needed.\n"
            "• The Y1 launcher (com.innioasis.y1) will be set as the default home app.\n\n"
            "This ensures your device is ready for Y1 app development and testing!"
        )
        messagebox.showinfo("Preparing Device", prep_msg)
        # Check if the APKs exist
        stock_launcher_path = "com.innioasis.y1_2.1.9.apk"
        nova_launcher_path = "novalauncher.apk"
        keycodedisp_path = "keycodedisp.apk"
        missing = []
        if not os.path.exists(stock_launcher_path):
            missing.append(stock_launcher_path)
        if not os.path.exists(nova_launcher_path):
            missing.append(nova_launcher_path)
        if not os.path.exists(keycodedisp_path):
            missing.append(keycodedisp_path)
        if missing:
            self.status_var.set(f"Missing APK(s): {', '.join(missing)}")
            messagebox.showerror("Missing APK(s)", f"The following APK(s) are required for preparation but not found:\n\n{chr(10).join(missing)}\n\nPlease add them to the workspace directory.")
            return
        self.status_var.set("Preparing device - Installing stock launcher, Nova Launcher, and KeyCodeDisp...")
        # Install stock launcher
        abs_path = os.path.abspath(stock_launcher_path)
        success, stdout, stderr = self.run_adb_command(f"install -r \"{abs_path}\"", timeout=60)
        if not success:
            self.status_var.set(f"Failed to install stock launcher: {stderr}")
            messagebox.showerror("Install Error", f"Failed to install stock launcher:\n\n{stderr}")
            return
        # Install Nova Launcher
        abs_nova = os.path.abspath(nova_launcher_path)
        success, stdout, stderr = self.run_adb_command(f"install -r \"{abs_nova}\"", timeout=60)
        if not success:
            self.status_var.set(f"Failed to install Nova Launcher: {stderr}")
            messagebox.showerror("Install Error", f"Failed to install Nova Launcher:\n\n{stderr}")
            return
        # Install KeyCodeDisp
        abs_keycode = os.path.abspath(keycodedisp_path)
        success, stdout, stderr = self.run_adb_command(f"install -r \"{abs_keycode}\"", timeout=60)
        if not success:
            self.status_var.set(f"Failed to install KeyCodeDisp: {stderr}")
            messagebox.showerror("Install Error", f"Failed to install KeyCodeDisp:\n\n{stderr}")
            return
        self.status_var.set("All launchers and KeyCodeDisp installed. Launching stock launcher...")
        # Disable factory test package if present
        self.run_adb_command("shell pm disable-user --user 0 com.ayst.factorytest")
        # Launch the stock launcher
        launch_success, launch_stdout, launch_stderr = self.run_adb_command(
            "shell monkey -p com.innioasis.y1 -c android.intent.category.LAUNCHER 1")
        # Set Y1 launcher as default home app
        self.run_adb_command("shell cmd package set-home-activity com.innioasis.y1/.ui.LauncherActivity")
        if not launch_success:
            self.status_var.set("Launcher installed, but failed to launch.")
            print(f"Warning: Failed to launch stock launcher: {launch_stderr}")
        else:
            self.status_var.set("Launcher launched - Opening language settings...")
            self.after(2000, self.change_device_language)
        messagebox.showinfo("Device Prepared", "✓ Stock Y1 launcher (2.1.9), Nova Launcher, and KeyCodeDisp installed\n✓ Stock launcher set as default home\n✓ Language settings opened\n\nDevice is ready for Y1 development!")
    
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
        self.status_var.set(f"Uninstalling {package_name}...")
        success, stdout, stderr = self.run_adb_command(f"uninstall {package_name}")
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
        # Y1 scroll wheel mapping: counterclockwise = Dpad Left (up), clockwise = Dpad Right (down)
        if self.control_launcher and self.scroll_wheel_mode_var.get():
            if self.disable_dpad_swap_var.get():
                # D-pad swap disabled - normal behavior
                if direction > 0:
                    keycode = 19  # KEYCODE_DPAD_UP
                    dir_str = "up"
                else:
                    keycode = 20  # KEYCODE_DPAD_DOWN
                    dir_str = "down"
                debug_print(f"Scroll wheel mode (swap disabled): sending D-pad {dir_str}")
            else:
                # D-pad swap enabled - Y1 scroll wheel behavior
                if direction > 0:
                    keycode = 21  # KEYCODE_DPAD_LEFT
                    dir_str = "left"
                else:
                    keycode = 22  # KEYCODE_DPAD_RIGHT
                    dir_str = "right"
                debug_print(f"Scroll wheel mode (swap enabled): sending D-pad {dir_str}")
        else:
            if direction > 0:
                keycode = 19  # KEYCODE_DPAD_UP
                dir_str = "up"
            else:
                keycode = 20  # KEYCODE_DPAD_DOWN
                dir_str = "down"
            debug_print(f"Touch screen mode: sending D-pad {dir_str}")
        
        # Send input immediately (framebuffer refresh is now non-blocking)
        success, stdout, stderr = self.run_adb_command(f"shell input keyevent {keycode}")
        if success:
            self.status_var.set(f"D-pad {dir_str} pressed")
            debug_print(f"D-pad {dir_str} sent successfully")
            # Request framebuffer refresh after sending input (non-blocking)
            self.after(50, self.force_framebuffer_refresh)
        else:
            self.status_var.set(f"D-pad {dir_str} failed: {stderr}")
            debug_print(f"D-pad {dir_str} failed: {stderr}")
    
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
        
        # Send input immediately (framebuffer refresh is now non-blocking)
        success, stdout, stderr = self.run_adb_command(f"shell input keyevent {keycode}")
        if success:
            self.status_var.set(f"Mouse wheel click: {action} pressed")
            debug_print(f"Mouse wheel click ({action}) sent successfully")
            # Request framebuffer refresh after sending input (non-blocking)
            self.after(50, self.force_framebuffer_refresh)
        else:
            self.status_var.set(f"Mouse wheel click failed: {stderr}")
            debug_print(f"Mouse wheel click failed: {stderr}")
    
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
                if not self.disable_dpad_swap_var.get():
                    # D-pad swap enabled - Y1 scroll wheel behavior
                    if keycode == 19:
                        keycode = 21
                        direction = 'left'
                        debug_print("Scroll wheel mode: remapping up -> left")
                    elif keycode == 20:
                        keycode = 22
                        direction = 'right'
                        debug_print("Scroll wheel mode: remapping down -> right")
                else:
                    debug_print("Scroll wheel mode: D-pad swap disabled, using normal mapping")
                
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
        
        # Send input immediately (framebuffer refresh is now non-blocking)
        success, stdout, stderr = self.run_adb_command(f"shell input keyevent {keycode}")
        if success:
            self.status_var.set(f"Key {direction} pressed")
            debug_print(f"Key {direction} sent successfully")
            # Request framebuffer refresh after sending input (non-blocking)
            self.after(50, self.force_framebuffer_refresh)
            self.after(1500, lambda: self.status_var.set("Ready"))
        else:
            self.status_var.set(f"Key {direction} failed: {stderr}")
            debug_print(f"Key {direction} failed: {stderr}")
    
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
            if os.path.exists("branch.txt"):
                with open("branch.txt", 'r', encoding='utf-8') as f:
                    current_branch = f.read().strip() or "master"
            
            # Show dialog to change branch
            new_branch = simpledialog.askstring(
                "Change Update Branch",
                f"Enter the branch name for updates:\n\nCurrent branch: {current_branch}",
                initialvalue=current_branch
            )
            
            if new_branch and new_branch.strip():
                new_branch = new_branch.strip()
                with open("branch.txt", 'w', encoding='utf-8') as f:
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
            if os.path.exists("branch.txt"):
                with open("branch.txt", 'r', encoding='utf-8') as f:
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
            subprocess.Popen([sys.executable, "y1_updater.py"])
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
    debug_print("Application exited") 