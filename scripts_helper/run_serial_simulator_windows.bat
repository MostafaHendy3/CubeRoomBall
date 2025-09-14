@echo off
REM Windows Batch File to Run Serial Simulator
REM ST1 Scale Simulator - Windows Version

echo ============================================================
echo ST1 Scale Simulator - Windows Version
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

REM Check if pyserial is installed
python -c "import serial" >nul 2>&1
if errorlevel 1 (
    echo WARNING: pyserial library not found
    echo Installing pyserial...
    pip install pyserial
    if errorlevel 1 (
        echo ERROR: Failed to install pyserial
        echo Please run: pip install pyserial
        pause
        exit /b 1
    )
)

echo Python and required libraries are available
echo.

REM Run the simulator
echo Starting Serial Simulator...
python serial_class_sender_mimcing_windows.py

echo.
echo Simulator finished.
pause
