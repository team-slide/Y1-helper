import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import glob
import datetime
import json
import requests


def cleanup_old_directory():
    """Clean up .old directory to keep only y1_helper.py files"""
    try:
        old_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.old')
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

def get_old_versions():
    """Get list of available old version directories"""
    # Clean up .old directory first
    cleanup_old_directory()
    
    old_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.old')
    if not os.path.exists(old_dir):
        return []
    
    # Find all version directories (v*.*.*)
    version_dirs = []
    for item in os.listdir(old_dir):
        item_path = os.path.join(old_dir, item)
        if os.path.isdir(item_path) and item.startswith('v'):
            # Check if y1_helper.py exists in this version directory
            y1_helper_path = os.path.join(item_path, 'y1_helper.py')
            if os.path.exists(y1_helper_path):
                version_dirs.append(item)
    
    # Sort versions (simple string sort should work for semantic versions)
    version_dirs.sort(reverse=True)  # Newest first
    return version_dirs


def run_old_version(version_dir):
    """Run y1_helper.py from the specified old version directory"""
    try:
        # Get paths
        root_dir = os.path.dirname(os.path.abspath(__file__))
        old_version_path = os.path.join(root_dir, '.old', version_dir, 'y1_helper.py')
        python_exe = os.path.join(root_dir, 'assets', 'python', 'python.exe')
        
        # Verify files exist
        if not os.path.exists(old_version_path):
            messagebox.showerror("Error", f"y1_helper.py not found in {version_dir}")
            return False
        
        if not os.path.exists(python_exe):
            messagebox.showerror("Error", "Python executable not found at assets/python/python.exe")
            return False
        
        # Set up environment variables to ensure proper path resolution
        env = os.environ.copy()
        env['Y1_HELPER_ROOT'] = root_dir
        env['Y1_HELPER_ASSETS'] = os.path.join(root_dir, 'assets')
        env['Y1_HELPER_OLD_VERSION'] = version_dir
        
        # Run the old version with root directory as working directory
        debug_print(f"Running old version: {old_version_path}")
        debug_print(f"Working directory: {root_dir}")
        debug_print(f"Python executable: {python_exe}")
        debug_print(f"Environment variables set: Y1_HELPER_ROOT={root_dir}")
        
        # Create a simple wrapper script that sets up the environment correctly
        wrapper_script = f'''#!/usr/bin/env python3
import os
import sys

# Set the correct working directory and environment
os.chdir(r"{root_dir}")

# Set environment variables
os.environ['Y1_HELPER_ROOT'] = r"{root_dir}"
os.environ['Y1_HELPER_ASSETS'] = r"{os.path.join(root_dir, 'assets')}"

# Override the base directory variables that the old script expects
base_dir = r"{root_dir}"
assets_dir = r"{os.path.join(root_dir, 'assets')}"

# Import and run the old script
sys.path.insert(0, r"{os.path.dirname(old_version_path)}")

# Execute the old script
exec(open(r"{old_version_path}", 'r', encoding='utf-8').read())
'''
        
        # Write the wrapper script
        wrapper_path = os.path.join(root_dir, f'wrapper_{version_dir}.py')
        with open(wrapper_path, 'w', encoding='utf-8') as f:
            f.write(wrapper_script)
        
        try:
            # Use subprocess to run the wrapper script
            process = subprocess.Popen(
                [python_exe, wrapper_path],
                cwd=root_dir,  # Set working directory to root
                env=env  # Pass environment variables
            )
            
        except Exception as e:
            debug_print(f"Error running wrapper script: {e}")
            # Fallback to running the original script
            process = subprocess.Popen(
                [python_exe, old_version_path],
                cwd=root_dir,  # Set working directory to root
                env=env  # Pass environment variables
            )
        
        debug_print(f"Started old version process with PID: {process.pid}")
        
        # Clean up wrapper file after a delay
        def cleanup_wrapper_file():
            import time
            time.sleep(2)  # Wait a bit for the process to start
            try:
                if os.path.exists(wrapper_path):
                    os.remove(wrapper_path)
                    debug_print(f"Cleaned up wrapper file: {wrapper_path}")
            except Exception as e:
                debug_print(f"Error cleaning up wrapper file: {e}")
        
        # Start cleanup in background
        import threading
        cleanup_thread = threading.Thread(target=cleanup_wrapper_file, daemon=True)
        cleanup_thread.start()
        
        return True
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to run old version: {e}")
        debug_print(f"Exception: {e}")
        return False


def debug_print(message):
    """Print debug messages"""
    print(f"[DEBUG] {message}")

# Rate limiting system for old.py
class RateLimiter:
    def __init__(self):
        self.api_rate_limits = {
            'unauthenticated': {'calls': 0, 'reset_time': datetime.datetime.now() + datetime.timedelta(hours=1)},
            'authenticated': {}  # Will store per-token limits
        }
        self.max_unauthenticated_calls = 40
        self.max_authenticated_calls = 100
        self.rate_limit_exceeded = False
        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        # Load rate limit state from file if it exists
        self.load_rate_limit_state()
    
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
                debug_print("Rate limit state loaded from file")
                
        except Exception as e:
            debug_print(f"Error loading rate limit state: {e}")

# Global rate limiter instance
rate_limiter = RateLimiter()


def show_version_selection_dialog():
    """Show dialog to select old version"""
    # Get available versions
    versions = get_old_versions()
    
    if not versions:
        messagebox.showinfo("No Old Versions", "No old versions found in .old directory.")
        return
    
    # Create selection dialog
    dialog = tk.Toplevel()
    dialog.title("Select Old Version")
    dialog.geometry("400x300")
    dialog.resizable(False, False)
    
    # Center the dialog
    dialog.transient()
    dialog.grab_set()
    
    # Center dialog on screen
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
    y = (dialog.winfo_screenheight() // 2) - (300 // 2)
    dialog.geometry(f"400x300+{x}+{y}")
    
    # Create main frame
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title label
    title_label = ttk.Label(main_frame, text="Select an old version to run:", font=("Arial", 12, "bold"))
    title_label.pack(pady=(0, 10))
    
    # Create listbox with scrollbar
    listbox_frame = ttk.Frame(main_frame)
    listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    listbox = tk.Listbox(listbox_frame, font=("Arial", 10))
    scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=listbox.yview)
    listbox.configure(yscrollcommand=scrollbar.set)
    
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Populate listbox
    for version in versions:
        listbox.insert(tk.END, version)
    
    # Select first item by default
    if versions:
        listbox.selection_set(0)
    
    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))
    
    def on_run():
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a version to run.")
            return
        
        selected_version = listbox.get(selection[0])
        dialog.destroy()
        
        # Confirm before running
        confirm = messagebox.askyesno(
            "Confirm Run",
            f"Run y1_helper.py from version {selected_version}?\n\n"
            f"This will start the old version while keeping the current version intact."
        )
        
        if confirm:
            run_old_version(selected_version)
    
    def on_cancel():
        dialog.destroy()
    
    # Buttons
    run_button = ttk.Button(button_frame, text="Run Selected Version", command=on_run)
    run_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    cancel_button = ttk.Button(button_frame, text="Cancel", command=on_cancel)
    cancel_button.pack(side=tk.RIGHT)
    
    # Double-click to run
    def on_double_click(event):
        on_run()
    
    listbox.bind('<Double-Button-1>', on_double_click)
    
    # Enter key to run
    def on_enter(event):
        on_run()
    
    listbox.bind('<Return>', on_enter)
    
    # Focus on listbox
    listbox.focus_set()


def main():
    """Main function"""
    # Create root window but keep it hidden
    root = tk.Tk()
    root.withdraw()
    
    # Show version selection dialog
    show_version_selection_dialog()
    
    # Start the main loop to handle the dialog
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        # Save rate limit state before exiting
        try:
            rate_limiter.save_rate_limit_state()
            debug_print("Rate limit state saved")
        except Exception as e:
            debug_print(f"Error saving rate limit state: {e}")
        
        # Destroy the root window
        root.destroy()


if __name__ == "__main__":
    main() 