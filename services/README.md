# CubeGame Service

This directory contains the systemd service file for running the CubeGame application as a Linux service.

## Service File

**cubegame.service** - Service for `CubeGame_New_active_qml_sound.py`

## Prerequisites

- Ensure Python 3 is installed on the target system
- Install required Python packages:
  ```bash
  pip3 install PyQt5 numpy requests paho-mqtt
  ```
- Ensure the following system packages are installed:
  ```bash
  sudo apt update
  sudo apt install python3-pyqt5 python3-pyqt5.qtquick python3-pyqt5.qtmultimedia
  sudo apt install qt5-qmltooling-plugins qml-module-qtquick-controls2
  sudo apt install pulseaudio alsa-utils
  ```
- Update the paths in the service file if they differ on your target system
- Ensure X11 display is available for GUI application

## Installation Instructions

### 1. Copy service file to systemd directory:
```bash
sudo cp cubegame.service /etc/systemd/system/
```

### 2. Reload systemd to recognize new service:
```bash
sudo systemctl daemon-reload
```

### 3. Enable service to start on boot (optional):
```bash
sudo systemctl enable cubegame.service
```

## Service Management

### Start service:
```bash
sudo systemctl start cubegame.service
```

### Stop service:
```bash
sudo systemctl stop cubegame.service
```

### Restart service:
```bash
sudo systemctl restart cubegame.service
```

### Check service status:
```bash
sudo systemctl status cubegame.service
```

### View service logs:
```bash
# View recent logs
sudo journalctl -u cubegame.service -n 50

# Follow logs in real-time
sudo journalctl -u cubegame.service -f

# View logs from specific time
sudo journalctl -u cubegame.service --since "1 hour ago"
```

### Disable service (stop auto-start on boot):
```bash
sudo systemctl disable cubegame.service
```

## Configuration Details

- **User/Group**: Service runs as user `mostafa`. Update this in the service file if needed.
- **Working Directory**: Service uses the `/home/mostafa/UXE/games_UXE_2025/game4` directory.
- **Python Path**: Service uses `/usr/bin/python3`. Update if Python is installed elsewhere.
- **Display**: Service includes GUI environment variables for X11 display (`DISPLAY=:0`).
- **QML**: Service includes Qt5 QML environment variables for proper QML widget functionality.
- **Audio**: Service includes PulseAudio environment variables for sound support.
- **Resources**: 
  - Memory limit: 3GB (CubeGame may use more resources due to QML)
  - CPU limit: 85%

## Environment Variables

The service includes these environment variables for proper GUI operation:

- `DISPLAY=:0` - X11 display for GUI
- `XDG_RUNTIME_DIR=/run/user/1000` - Runtime directory for user session
- `PULSE_RUNTIME_PATH=/run/user/1000/pulse` - PulseAudio runtime path
- `QT_QPA_PLATFORM=xcb` - Qt platform abstraction for X11
- `QML_IMPORT_PATH=/usr/lib/x86_64-linux-gnu/qt5/qml` - QML module path

## Troubleshooting

### Common Issues:

1. **Service fails to start:**
   ```bash
   # Check detailed logs
   sudo journalctl -u cubegame.service -xe
   ```

2. **Python import errors:**
   ```bash
   # Install missing packages
   pip3 install [missing-package]
   
   # Or use system packages
   sudo apt install python3-[package-name]
   ```

3. **Display/GUI issues:**
   ```bash
   # Check X11 access
   echo $DISPLAY
   xhost +local:
   
   # For remote systems, enable X11 forwarding
   ssh -X user@hostname
   ```

4. **Audio issues:**
   ```bash
   # Check PulseAudio
   pulseaudio --check
   pactl info
   
   # Restart PulseAudio if needed
   pulseaudio -k
   pulseaudio --start
   ```

5. **QML issues:**
   ```bash
   # Check QML modules
   qmlscene --list-modules
   
   # Install missing QML modules
   sudo apt install qml-module-qtquick-controls2
   sudo apt install qml-module-qtmultimedia
   ```

6. **Permission issues:**
   - Ensure the user `mostafa` exists and has proper permissions
   - Check file permissions in the game directory
   - Verify audio/video group membership:
     ```bash
     sudo usermod -a -G audio,video mostafa
     ```

### Debug Mode:

To run the game manually for debugging:
```bash
cd /home/mostafa/UXE/games_UXE_2025/game4
python3 CubeGame_New_active_qml_sound.py
```

### Update Service:

When updating the game code:
1. Stop the service: `sudo systemctl stop cubegame.service`
2. Update your code
3. Restart the service: `sudo systemctl start cubegame.service`

### Logs Location:

Service logs are stored in the systemd journal. Use `journalctl` commands above to view them, or check:
- `/var/log/syslog` - General system logs
- Application logs may be written to the game's `logs/` directory if configured

## Security Notes

The service includes basic security settings:
- `NoNewPrivileges=true` - Prevents privilege escalation
- `PrivateTmp=true` - Provides private /tmp directory
- Resource limits to prevent system resource exhaustion

For production deployments, consider additional security measures based on your environment requirements.
