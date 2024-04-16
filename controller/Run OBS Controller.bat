@echo off
if "%WINPYDIR%"=="" ( echo "'WINPYDIR' is not defined. It should point to the directory where python.exe is stored." &  goto end )
echo WINPYDIR = %WINPYDIR%
if exist "%WINPYDIR%\..\scripts\env.bat" ( call %WINPYDIR%\..\scripts\env.bat ) else ( set "PATH=%WINPYDIR%\;%PATH%;" & echo Not using python env.bat)

rem remove the /min option to see error printouts on startup
set START_CMD=start /min

rem ===========================================================================
@rem BASE_PATH is the directory this file is in
set BASE_PATH=%~dp0

rem ===========================================================================

echo.
echo.
echo Using CONFIG_FILE = %CONFIG_FILE%
echo.
echo.
echo "OBS_Controller..."
python "%BASE_PATH%\OBS_Controller.py" 


:end
timeout /t 10