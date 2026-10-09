@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 goto no_python

if not exist "%~dp0qoder_reset_gui.py" goto no_script
if not exist "%~dp0requirements.txt" goto no_requirements

echo Installing required Python packages...
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto install_failed

echo Starting Qoder Reset Tool...
where pythonw >nul 2>&1
if errorlevel 1 goto launch_console
start "" pythonw "%~dp0qoder_reset_gui.py"
exit /b 0

:launch_console
start "" python "%~dp0qoder_reset_gui.py"
exit /b 0

:no_python
echo ERROR: Python was not found.
echo Install Python for Windows, then run this file again.
pause
exit /b 1

:no_script
echo ERROR: qoder_reset_gui.py was not found next to this launcher.
pause
exit /b 1

:no_requirements
echo ERROR: requirements.txt was not found next to this launcher.
pause
exit /b 1

:install_failed
echo ERROR: Required packages could not be installed.
echo Check your internet connection and Python pip installation, then retry.
pause
exit /b 1
