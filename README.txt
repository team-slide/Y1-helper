FEATURES:
- Delayed screen capture from Y1 device (visual aid for touch input targeting)
- Touch screen simulation for third-party apps
- Mouse and keyboard input mapping
- App management (install, launch, uninstall)
- Prepare Device: Install stock Y1 launcher (2.1.9) to restore standard functionality to ADB-enabled factory test firmware
- Fix Launcher Controls mode for better navigation
- ADB shell access and device information

USAGE:
1. Connect your Y1 device via USB
2. Enable USB debugging on the device
3. Run "Y1 Helper.exe"
4. (Optional) Use Device > Flash device and follow the on-screen instructions to install the ATA Firmware
5. (Optional) Use Device > Prepare Device to install stock launcher for development
6. Use the delayed screen capture to guide your mouse clicks and keyboard inputs

INPUT MODES:
- Stock Launcher Mode: Mouse input sends D-pad navigation commands
- Third-Party App Mode: Mouse input simulates touch screen taps for testing apps ported from touch screen Android devices

CONTROLS:
- Left Click: Touch screen tap (in third-party apps) or Enter (in launcher mode)
- Right Click: Back button
- Scroll Wheel: D-pad navigation
- Wheel Click: Center/Enter
- Keyboard shortcuts: W/A/S/D for navigation, Space for play/pause, etc.

APPLICATION TESTING:
When running third-party apps that haven't been fully optimized for the Y1's physical controls, mouse input is converted to touch screen simulation. The delayed screen capture provides a visual reference to help you target touch inputs accurately, making it easier to test and interact with apps originally designed for touch screen Android devices during the porting process.

For more information, see the README.md file in the source directory.

TROUBLESHOOTING:
- If the device is not detected, check USB debugging is enabled
- Make sure you have the correct USB drivers installed
- Try a different USB cable or port
- Restart the application if needed

Version: 1.0
Build Date: 2024 
