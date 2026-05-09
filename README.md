# Cyclades PM Integration for Home Assistant

A custom Home Assistant integration for Cyclades PM (Power Management) series devices. Control and monitor your rack-mounted power distribution units directly from Home Assistant.

![Integration Icon](https://img.shields.io/badge/integration-Cyclades_PM-blue)
![Version](https://img.shields.io/badge/version-1.0.0-green)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)

## Features

- 🔌 **Outlet Control**: Switch individual outlets on/off
- ♻️ **Power Cycling**: One-click power cycle buttons for each outlet
- ⚡ **Current Monitoring**: Real-time current consumption (10-second updates)
- 🌡️ **Temperature Monitoring**: Device temperature tracking (30-second updates)
- 📊 **Peak Values**: Track peak current consumption
- 🔄 **Auto-Discovery**: Automatically detects the number of outlets during setup
- 🏷️ **Custom Naming**: Use meaningful device names for better organization
- 🔐 **Authentication**: Secure login with username/password

## Supported Devices

- Cyclades PM series power distribution units
- Any compatible IPDU (Intelligent Power Distribution Unit) using the Cyclades PM protocol

## Requirements

- Home Assistant 2024.1 or newer
- Serial connection to Cyclades PM device (USB-to-serial adapter or direct serial port)
- Python 3.9 or newer

## Installation

### HACS (Recommended)

_Coming soon - manual installation required for now_

### Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/cyclades_pm` directory to your Home Assistant `custom_components` folder:
   ```
   custom_components/
   └── cyclades_pm/
       ├── __init__.py
       ├── button.py
       ├── config_flow.py
       ├── const.py
       ├── coordinator.py
       ├── manifest.json
       ├── sensor.py
       ├── strings.json
       └── switch.py
   ```
3. Restart Home Assistant
4. Go to **Settings** → **Devices & Services** → **Add Integration**
5. Search for "Cyclades PM"

## Configuration

### Setup Workflow

1. **Add Integration**
   - Navigate to Settings → Devices & Services → Add Integration
   - Search for "Cyclades PM"

2. **Enter Connection Details**
   - **Name**: A friendly name for this device (e.g., "Server Rack PDU Left")
   - **Serial Port**: Select your serial port (e.g., `/dev/ttyUSB0`)
   - **Username**: Admin username (default: `admin`)
   - **Password**: Admin password (default: `pm8`)

3. **Confirmation**
   - Review detected outlets and firmware version
   - Click Submit to complete setup

### Multiple Devices

You can add multiple Cyclades PM devices - just repeat the setup process for each serial port.

## Entities Created

For a device named "Server Rack PDU":

### Switches (Per Outlet)
- `switch.server_rack_pdu_outlet_1`
- `switch.server_rack_pdu_outlet_2`
- ... (one per detected outlet)

### Buttons (Per Outlet)
- `button.server_rack_pdu_cycle_outlet_1`
- `button.server_rack_pdu_cycle_outlet_2`
- ... (one per detected outlet)

### Sensors
- `sensor.server_rack_pdu_temperature` - Current temperature (°C)
- `sensor.server_rack_pdu_current` - Current consumption (A)
- `sensor.server_rack_pdu_peak_current` - Peak current consumption (A)

## Performance & Polling

The integration uses optimized polling intervals to balance responsiveness with serial port efficiency:

| Measurement | Polling Interval | Reason |
|------------|------------------|--------|
| Current | 10 seconds | Fast power monitoring |
| Temperature | 30 seconds | Slower-changing value |
| Outlet States | 5 minutes | Verification/sync only |

## Troubleshooting

### Integration Won't Load

1. Check Home Assistant logs: **Settings** → **System** → **Logs**
2. Look for errors containing `cyclades_pm`
3. Verify all files are in the correct location
4. Ensure `aioserial` dependency is installed

### No Serial Ports Available

- Verify your serial adapter is connected
- Check device permissions: `ls -l /dev/ttyUSB*`
- Add Home Assistant user to dialout group (if using Home Assistant OS, this is automatic)

### Authentication Failed

- Verify username and password
- Default credentials are typically:
  - Username: `admin`
  - Password: `pm8`
- Check device documentation for correct credentials

### Outlets Not Detected

- Ensure the device responds to the `ver` command
- Check serial connection settings (9600 baud, 8N1)
- Verify serial cable is working properly
- Try removing and re-adding the integration

### Entity Names Not Updating

If you changed the device name but old entity names persist:

1. Remove the integration completely
2. Restart Home Assistant
3. Re-add the integration with the new name

## Technical Details

### Communication Protocol

- **Baud Rate**: 9600
- **Data Bits**: 8
- **Parity**: None
- **Stop Bits**: 1
- **Flow Control**: None

### Commands Used

| Command | Purpose | Frequency |
|---------|---------|-----------|
| `ver` | Get outlet count and firmware version | Once during setup |
| `current` | Read current consumption | Every 10 seconds |
| `temperature` | Read device temperature | Every 30 seconds |
| `status all` | Get all outlet states | Every 5 minutes |
| `on <n>` | Turn on outlet n | On demand |
| `off <n>` | Turn off outlet n | On demand |
| `cycle <n>` | Power cycle outlet n | On demand |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Clone the repository
2. Create a branch for your feature
3. Make your changes
4. Test thoroughly with a physical device
5. Submit a pull request

## License

MIT Licsene

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## Changelog

### Version 1.0.0 (2024)
- Initial release
- Support for multiple devices
- Optimized polling intervals
- Auto-detection of outlet count
- Custom device naming
- Switch, button, and sensor entities
