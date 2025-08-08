# Wireless ADB Feature

Y1 Helper now includes a wireless ADB feature that allows you to connect to your device over WiFi instead of USB.

## How to Use Wireless ADB

### Prerequisites
- Your device must be connected via USB initially
- Your device and computer must be on the same WiFi network
- USB debugging must be enabled on your device

### Steps to Enable Wireless ADB

1. **Connect via USB First**
   - Connect your device to your computer via USB cable
   - Ensure Y1 Helper detects the device (status shows "Device Connected")

2. **Enable Wireless ADB**
   - Click the "Wireless ADB" button in Y1 Helper
   - Enter your device's IP address when prompted
   - Enter the wireless ADB port (default: 5555)
   - Click OK

3. **Disconnect USB**
   - Once the wireless connection is established, you can disconnect the USB cable
   - Y1 Helper will continue to work wirelessly

### Alternative: Auto-Detect IP

1. **Right-click the Wireless ADB button**
2. **Select "Auto-detect IP"**
3. **Follow the prompts**

This will automatically detect your device's IP address and connect wirelessly.

### Managing Wireless ADB

- **Right-click the Wireless ADB button** for additional options:
  - Enable/Disable Wireless ADB
  - Auto-detect IP
  - View current connection status

- **Status Display**: The status bar will show "Wireless ADB Enabled" when connected wirelessly

- **Button Text**: The button text will update to show the connected IP address (e.g., "Wireless ADB (192.168.1.100)")

### Troubleshooting

**Connection Failed**
- Ensure your device and computer are on the same WiFi network
- Check that the IP address is correct
- Verify that USB debugging is enabled
- Try reconnecting via USB first

**Device Not Found**
- Make sure your device is connected via USB initially
- Check that ADB is working with USB connection first

**Performance Issues**
- Wireless ADB may be slower than USB connection
- Some operations may take longer over WiFi
- Consider using USB for large file transfers or firmware flashing

### Technical Details

- **Default Port**: 5555 (can be changed if needed)
- **Protocol**: TCP/IP over WiFi
- **Security**: Uses the same ADB authentication as USB connections
- **Compatibility**: Works with all Android devices that support ADB

### Benefits

- **No USB Cable Required**: Use Y1 Helper without being tethered to your computer
- **Remote Access**: Control your device from across the room
- **Convenience**: Easy switching between USB and wireless modes
- **Same Functionality**: All Y1 Helper features work the same over wireless ADB

### Limitations

- **Network Dependent**: Requires stable WiFi connection
- **Slower Speed**: Wireless connection is slower than USB
- **Initial Setup**: Requires USB connection to enable wireless mode
- **Range**: Limited by WiFi range and signal strength

## Support

If you encounter issues with wireless ADB:
1. Try reconnecting via USB first
2. Check your WiFi connection
3. Verify the device IP address
4. Restart Y1 Helper if needed

The wireless ADB feature enhances Y1 Helper's usability by providing cable-free device management while maintaining all existing functionality.


