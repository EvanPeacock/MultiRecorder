@echo off

set "CONFIG_FILE=config.yaml"

echo.
echo.
echo Using CONFIG_FILE = %CONFIG_FILE%
echo.
echo.
echo "Starting OBS Controller..."
echo.
echo.

cd controller
OBS_Controller.exe --config-file "%CONFIG_FILE%"

:end
timeout /t 30