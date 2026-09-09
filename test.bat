@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON_EXE=%CD%\.runtime\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo The repaired .runtime environment is missing.
    echo Run launch.bat once to create it and install the project dependencies.
    exit /b 1
)

"%PYTHON_EXE%" -c "import sys; print('Using ' + sys.executable + ' (' + sys.version.split()[0] + ')')"
if errorlevel 1 (
    echo The .runtime Python executable could not be started.
    exit /b 1
)

set "QT_QPA_PLATFORM=offscreen"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"

echo Running syntax checks...
"%PYTHON_EXE%" -B -m compileall -q desktop_gui.py harness_ui modules tests
if errorlevel 1 exit /b 1

echo Running unit tests...
"%PYTHON_EXE%" -B -m unittest discover -s tests -p "test*.py" -v
if errorlevel 1 exit /b 1

echo Running the privacy check...
"%PYTHON_EXE%" -B privacy_check.py --current-only
if errorlevel 1 exit /b 1

echo All checks passed.
exit /b 0
