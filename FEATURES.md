# Y1 Helper - Complete Feature Overview

## 🎯 Core Features Implemented

### ✅ Screen Capture & Display
- **Live screen mirroring** in application window (laggy and intended mainly to help you land touch input accurately via the remote control tool, while observing the device display)
- **Note:** The preview on your PC is subject to delay and may run slowly, especially on screens that don't refresh a lot of pixels at once. For real-time feedback, always observe the device's own screen directly.
- **Scrollable canvas** for larger displays

### ✅ App Management
- **Launch Android Settings** with single click
- **"Go Home" functionality** returns to launcher
- **Hide system app** (`com.innioasis.y1`) from app list
- **Browse user-installed apps** via menu system
- **APK installation** via file dialog or drag & drop
- **App launching** with automatic launcher mode toggle

### ✅ Input Mapping System
- **Left Click**: Touch input at exact X/Y coordinates
- **Right Click**: Android Back button (KEYCODE_BACK)
- **Mouse Wheel Click**: D-pad Center (Enter/OK button)
- **Mouse Wheel**: 
  - Normal mode: D-pad Up/Down
  - Launcher mode: D-pad Left/Right (inverted)
- **Keyboard Controls**:
  - `W/Up Arrow`: D-pad Up
  - `S/Down Arrow`: D-pad Down  
  - `A`: D-pad Left
  - `D`: D-pad Right
  - `Enter`: D-pad Center (OK button)
  - `Space`: Play/Pause
  - `Page Up`: Next track
  - `Page Down`: Previous track
  - `Alt`: Toggle launcher control mode

### ✅ Launcher Control Mode
- **Automatic activation** when "Go Home" is selected
- **Automatic deactivation** when launching apps
- **Manual toggle** with Alt key
- **Inverted mouse wheel** behavior (Up/Down ↔ Left/Right)

### ✅ Developer Tools
- **ADB Shell access** in new console window
- **Device information** display
- **Status bar** with real-time feedback
- **Coordinate display** for precise input mapping
- **Error handling** and user feedback

## 📁 Project Files

### Core Application
- `y1_helper.py` - Main application (800+ lines)
- `remote_y1.py` - Original simple version (18 lines)

### Configuration & Setup
- `requirements.txt` - Python dependencies (Pillow)
- `config.json` - Advanced configuration options
- `README.md` - Comprehensive documentation

### Launch Scripts
- `run_y1_helper.bat` - Windows batch file
- `run_y1_helper.sh` - Linux/Mac shell script

### External Dependencies
- `platform-tools/` - ADB tools directory (user-provided)

## 🔧 Technical Implementation

### Architecture
- **Tkinter GUI** with modern ttk widgets
- **Multi-threaded** screen capture
- **Event-driven** input handling
- **Modular design** with separate UI and logic components

### ADB Integration
- **Direct command execution** via subprocess
- **Timeout handling** for device communication
- **Error reporting** and status updates
- **Device detection** and connection validation

### Input Processing
- **Real-time coordinate mapping** (PC → Android)
- **Keycode translation** for hardware buttons
- **Mode switching** for launcher vs app control
- **Event binding** for mouse and keyboard

### Screen Capture
- **Framebuffer reading** via ADB pull
- **RGBA8888 format** processing
- **PIL/Pillow** image conversion
- **Thread-safe** canvas updates

## 🎮 Input Mapping Reference

| PC Input | Android Action | Keycode | Mode |
|----------|----------------|---------|------|
| Left Click | Touch at (x,y) | N/A | All |
| Right Click | Back | 4 | All |
| Mouse Wheel Click | D-pad Center | 23 | All |
| Mouse Wheel Up | D-pad Up/Left | 19/21 | Normal/Launcher |
| Mouse Wheel Down | D-pad Down/Right | 20/22 | Normal/Launcher |
| W/Up Arrow | D-pad Up | 19 | All |
| S/Down Arrow | D-pad Down | 20 | All |
| A | D-pad Left | 21 | All |
| D | D-pad Right | 22 | All |
| Enter | D-pad Center | 23 | All |
| Space | Play/Pause | 85 | All |
| Page Up | Next Track | 87 | All |
| Page Down | Previous Track | 88 | All |
| Alt | Toggle Mode | N/A | All |

## 🚀 Usage Workflow

1. **Setup**: Install dependencies, enable USB debugging
2. **Connect**: Plug in Y1 device and authorize ADB
3. **Launch**: Run application via script or Python
4. **Capture**: Start screen capture to see device
5. **Navigate**: Use mouse/keyboard for device control
6. **Install**: Add APKs via file dialog
7. **Develop**: Test apps with full input mapping

## 🎯 Target Device Specifications

- **Platform**: MediaTek MT6572
- **OS**: Android 4.2.2 (API Level 17)
- **Display**: 480x360px, no touch screen
- **Input**: Hardware buttons only
  - D-pad (5-way navigation)
  - Back button
  - Media controls (Play/Pause, Previous/Next)

## 🔍 Advanced Features

- **Configurable settings** via JSON file
- **Cross-platform** compatibility (Windows/Linux/Mac)
- **Error recovery** and connection management
- **Real-time status** updates
- **Developer-friendly** interface
- **Extensible architecture** for future enhancements

This tool provides a complete development environment for the Innioasis Y1 device, enabling developers to overcome the device's limited input capabilities and develop/test Android applications effectively. 
