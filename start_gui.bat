@echo off
REM Qoder Reset Tool GUI Launcher for Windows

REM Set console to UTF-8 encoding
chcp 65001 >nul

REM Detect Python installation
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: Python not found
    echo Please install Python from:
    echo 1. https://www.python.org/downloads/windows/
    echo 2. Microsoft Store
    echo 3. Anaconda Distribution
    pause
    exit /b 1
)

REM Check Python version (requires Python 3.7+)
for /f "delims=" %%a in ('python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"') do set "PYVER=%%a"
set "PYVER=%PYVER:.=%"
if %PYVER% lss 37 (
    echo ❌ Error: Python 3.7 or higher is required
    echo Current version: %PYVER%
    pause
    exit /b 1
)

REM Install or upgrade required packages
echo ⚙️ Checking and installing required packages...
python -m pip install --upgrade pip
python -m pip install PyQt5 requests

REM Verify package installation
python -c "import PyQt5; import requests" 2>nul
if %errorlevel% neq 0 (
    echo ❌ Error: Failed to install required packages
    echo Please run: python -m pip install PyQt5 requests
    pause
    exit /b 1
)

REM Check if GUI script exists
if not exist "qoder_reset_gui.py" (
    echo ❌ Error: qoder_reset_gui.py not found
    echo Please ensure you are in the correct directory
    pause
    exit /b 1
)

REM Clear screen and show startup info
cls
echo ==================================================
echo 🚀 Qoder Reset Tool GUI Launcher
echo ==================================================
echo ✅ Environment checks passed
echo ✅ Starting application...
echo ==================================================

REM Launch the GUI application
start "" pythonw qoder_reset_gui.py

REM Post-execution
echo ==================================================
echo 🏁 Qoder Reset Tool GUI Launched
echo ==================================================
timeout /t 2 >nul
