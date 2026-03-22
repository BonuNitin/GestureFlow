@echo off
title Gesture Flow AI Launcher
color 0B
echo =======================================================
echo            INITIALIZING GESTURE FLOW AI
echo =======================================================
echo.
echo Starting the Python Server Backend...

:: Navigate to the script's directory exactly where this .bat is placed
cd /d "%~dp0"

:: Start the python server asynchronously in a minimized command window
start "Gesture Flow Engine" /min cmd /c "python app.py"

:: Wait 3 seconds to ensure Flask has completely booted up
timeout /t 3 /nobreak >nul

:: Launch the user's default Web Browser
echo Loading Web Interface...
start "" "http://127.0.0.1:5000"

echo.
echo Launch sequence complete!
echo You can safely close this black launcher window now.
echo Note: To completely turn the system off later, just close the minimized background command prompt window.
timeout /t 5 >nul
exit
