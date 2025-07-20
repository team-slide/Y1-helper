# Y1 Helper

A Python-based Android device management tool for Y1 devices, providing screen mirroring, app management, and device control capabilities.

## Features

- **Screen Mirroring**: Real-time screen capture and display from Android device
- **App Management**: Install, uninstall, and launch applications
- **Device Control**: Touch input, navigation, and system controls
- **Auto-updates**: Built-in updater with GitHub integration
- **Theme Support**: Windows 11 light/dark mode detection
- **Debug Tools**: Built-in debugging and development utilities

## Installation

1. Download the latest release from GitHub
2. Extract to a folder
3. Run `y1_helper.py` or the executable

## Configuration

### GitHub Token Setup (for updates)

The updater requires a GitHub Personal Access Token for API access:

1. Copy `config.ini.example` to `config.ini`
2. Edit `config.ini` and add your GitHub token:
   ```ini
   [github]
   token = your_github_token_here
   ```
3. Create a token at: https://github.com/settings/tokens
   - Required permissions: `repo` (for private repos) or `public_repo` (for public repos)

### Branch Configuration

To use a different update branch:
1. Edit `branch.txt` and set your desired branch name
2. Or use the Debug menu (Ctrl+D) in the application

## Usage

### Basic Controls

- **Mouse Click**: Touch input on device screen
- **Mouse Wheel**: Scroll wheel input (when enabled)
- **Keyboard**: Navigation and media controls
- **Right Click**: Context menu

### Debug Menu (Ctrl+D)

- Change update branch
- Show current branch
- Launch updater
- View version information

### App Management

- **Install APK**: Drag and drop APK files
- **Launch Apps**: Use the Apps menu
- **Uninstall**: Right-click on apps in the menu

## Development

### Version Management

The version is centralized in `y1_helper.py`:
```python
self.version = "0.5.0"
```

This version is automatically written to `version.txt` on startup and used throughout the application.

### File Structure

- `y1_helper.py`: Main application
- `y1_updater.py`: Update system (excluded from git)
- `config.ini`: Configuration file (excluded from git)
- `branch.txt`: Update branch configuration
- `version.txt`: Version information (auto-generated)

### Ignored Files

The following files are excluded from version control:
- `y1_updater.py`: Updater script
- `config.ini`: Configuration with tokens
- `branch.txt`: Branch configuration
- `version.txt`: Auto-generated version file
- `*.exe`: Executables
- `build/`, `dist/`, `python/`: Build artifacts

## Troubleshooting

### ADB Connection Issues

1. Ensure ADB is in the same directory as the application
2. Enable USB debugging on your device
3. Check device connection with `adb devices`

### Update Issues

1. Verify GitHub token in `config.ini`
2. Check internet connection
3. Ensure repository access permissions

### Screen Display Issues

1. Check device resolution settings
2. Verify framebuffer access
3. Restart the application

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
- Create an issue on GitHub
- Check the debug logs in the application
- Review the troubleshooting section above 