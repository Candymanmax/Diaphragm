@echo off
setlocal
cd /d "%~dp0"

set "CI_BUILD=0"
if /i "%~1"=="--ci" set "CI_BUILD=1"

set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys, PySide6" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
)

if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "import sys, PySide6" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"
)

if not defined PYTHON_EXE if exist ".runtime\Scripts\python.exe" (
    ".runtime\Scripts\python.exe" -c "import sys, PySide6" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%CD%\.runtime\Scripts\python.exe"
)

if not defined PYTHON_EXE if exist ".runtime-python\python.exe" (
    ".runtime-python\python.exe" -c "import sys, PySide6" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%CD%\.runtime-python\python.exe"
)

if not defined PYTHON_EXE (
    echo Run launch.bat once before building the packaged app.
    if "%CI_BUILD%"=="0" pause
    exit /b 1
)

"%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-input "pyinstaller>=6,<7"
if errorlevel 1 goto :error

"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onedir ^
    --name "Diaphragm" --windowed ^
    --icon "harness_ui\assets\diaphragm_icon.ico" ^
    --add-data "config.default.yaml;." ^
    --add-data "harness_ui\assets\icons;harness_ui\assets\icons" ^
    --add-data "harness_ui\assets\diaphragm_icon.ico;harness_ui\assets" ^
    --add-data "harness_ui\assets\diaphragm_icon.svg;harness_ui\assets" ^
    --collect-all chatterbox --collect-all syntok --collect-binaries sklearn ^
    --collect-data perth ^
    --recursive-copy-metadata diffusers --recursive-copy-metadata transformers ^
    --exclude-module torch --exclude-module torchaudio ^
    desktop_gui.py
if errorlevel 1 goto :error

rem PySide6 uses the Windows ICU forwarder. PyInstaller can otherwise copy an
rem incompatible ICU DLL from an unrelated tool on the build machine's PATH.
if exist "dist\Diaphragm\_internal\icuuc.dll" del /q "dist\Diaphragm\_internal\icuuc.dll"
if errorlevel 1 goto :error

rem Some PyInstaller/sklearn combinations discover the sklearn package but
rem omit its wheel-local native libraries. Copy them explicitly so Chatterbox
rem can load sklearn on a clean Windows machine.
for %%P in ("%PYTHON_EXE%") do set "PYTHON_EXE_DIR=%%~dpP"
set "SKLEARN_LIB_DIR=%PYTHON_EXE_DIR%..\Lib\site-packages\sklearn\.libs"
if not exist "%SKLEARN_LIB_DIR%" set "SKLEARN_LIB_DIR=%PYTHON_EXE_DIR%Lib\site-packages\sklearn\.libs"
if not exist "%SKLEARN_LIB_DIR%\vcomp140.dll" goto :error
if not exist "%SKLEARN_LIB_DIR%\msvcp140.dll" goto :error
if not exist "dist\Diaphragm\_internal\sklearn\.libs" mkdir "dist\Diaphragm\_internal\sklearn\.libs"
copy /y "%SKLEARN_LIB_DIR%\*.dll" "dist\Diaphragm\_internal\sklearn\.libs\" >nul
if errorlevel 1 goto :error
if not exist "dist\Diaphragm\_internal\sklearn\.libs\vcomp140.dll" goto :error
if not exist "dist\Diaphragm\_internal\sklearn\.libs\msvcp140.dll" goto :error

echo Packaged application created in dist\Diaphragm\
if "%CI_BUILD%"=="0" pause
exit /b 0

:error
echo The packaged application could not be built.
if "%CI_BUILD%"=="0" pause
exit /b 1
