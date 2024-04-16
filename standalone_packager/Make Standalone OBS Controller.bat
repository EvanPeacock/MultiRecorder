@REM pushd %~dp1
echo WINPYDIR = %WINPYDIR%
call %WINPYDIR%\..\scripts\env.bat   

:: =================================================================================================
:: Deployment Test Script
:: Usage:
::    create a requirements.txt package list in your package directory - be as minimal as possible.
::    Run this batch file with the correct names and directories below. If import errors occur, add
::    to the requirements.txt file.
::        VENVDIR: directory name where virtualenv is created.
::        PKGSRC: directory containing python code under test
::        PYCMD:  name of the python script in %PKGSRC% that will be run.
:: =================================================================================================


:: ===== Get the abs package path by switching to it and saving the current directory %CD% =====
:: https://stackoverflow.com/questions/1645843/resolve-absolute-path-from-relative-path-and-or-file-name
set BASEPKGDIR=..
pushd %BASEPKGDIR%
set BASEPKGDIR=%CD%
popd

:: ===== Set up names here =====
set VENVDIR=venv
set PKGSRC=controller
set PYNAME=OBS_Controller
set PYCMD="%PYNAME%.py"
::set PYVER=0.9.12dev
::set /p PYVER=<%PKGSRC%\_version.py
::for /F "tokens=1,2 delims==." %%a in ("%PYVER%") do (
::   set VER=%%b
::)

:: =============================


:: *UNSET* PYTHONPATH --> THIS IS IMPORTANT TO DO FOR VIRTUALENV!
set PYTHONPATH=



echo "Creating virtualenv..."
virtualenv --clear %VENVDIR%
xcopy /E "%BASEPKGDIR%\%PKGSRC%" "%VENVDIR%\%PKGSRC%\" /EXCLUDE:excluded_file_list.txt

cd %VENVDIR%

echo Starting virtual env %VENVDIR%... 

call Scripts\activate.bat

echo %VIRTUAL_ENV%

@echo on

pip install --no-cache-dir  -r %PKGSRC%\requirements.txt

cd "%PKGSRC%"
python  "%PYCMD%"

:: print out a list of what was required with version numbers
pip freeze

timeout /t 10

pip install nuitka  ordered-set

::python -m nuitka --standalone --onefile "%PYCMD%"   
:: NOTE: nuitka ignores gcs_pfd/ADAHRS_HSI.dll & gcs_nav/NavDisplay.dll  for some reason unless you specify it directly
:: DONT FORGET THE ENDING QUOTE 
set "ARGS=--standalone  --follow-imports   --no-deployment-flag=self-execution"
set "ARGS=%ARGS%  --show-progress --show-modules"
::set "ARGS=%ARGS% --include-package=cffi"
set "ARGS=%ARGS% --include-data-files=config.yaml=."
set "ARGS=%ARGS% --include-data-dir="assets"=assets"
set "ARGS=%ARGS% --noinclude-numba-mode=nofollow"
set "ARGS=%ARGS% --noinclude-setuptools-mode=nofollow"
python -m nuitka %ARGS% "%PYCMD%"   

:: ===== Package up the program in a friendly way =====
:: include manual and runner batch files
rmdir /S /Q tempzip
mkdir tempzip
robocopy %PYNAME%.dist tempzip/controller /E
robocopy %BASEPKGDIR%/standalone_packager/runner_files tempzip "Start OBS Controller Standalone.bat"

python -c "import shutil,os;shutil.make_archive('%PYNAME%',format='zip',root_dir='tempzip')

move "%PYNAME%.zip" ../../"%PYNAME%.zip"

rmdir /S /Q tempzip

timeout /t 60