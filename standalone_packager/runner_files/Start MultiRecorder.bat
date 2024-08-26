@echo off

set "CONFIG_FILE=config.yaml"

echo Using CONFIG_FILE = %CONFIG_FILE%
echo.
echo.
echo Starting MultiRecorder...
echo.
echo.

cd multi_recorder
MultiRecorder.exe --config-file "%CONFIG_FILE%" -f

:end
timeout /t 30