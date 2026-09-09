@echo off
setlocal

cd /d "%~dp0"

set "PROJECT_PYTHON="

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PROJECT_PYTHON=%CD%\.venv\Scripts\python.exe"
)

if not defined PROJECT_PYTHON if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PROJECT_PYTHON=%CD%\venv\Scripts\python.exe"
)

if not defined PROJECT_PYTHON if exist ".runtime\Scripts\python.exe" (
    ".runtime\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PROJECT_PYTHON=%CD%\.runtime\Scripts\python.exe"
)

if not defined PROJECT_PYTHON if exist ".runtime-python\python.exe" (
    ".runtime-python\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PROJECT_PYTHON=%CD%\.runtime-python\python.exe"
)

if defined PROJECT_PYTHON goto :dependencies

set "BASE_PYTHON="
set "BASE_ARGS="

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    "%LocalAppData%\Programs\Python\Python311\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "BASE_PYTHON=%LocalAppData%\Programs\Python\Python311\python.exe"
)

if not defined BASE_PYTHON if exist "%LocalAppData%\Python\pythoncore-3.11-64\python.exe" (
    "%LocalAppData%\Python\pythoncore-3.11-64\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "BASE_PYTHON=%LocalAppData%\Python\pythoncore-3.11-64\python.exe"
)

if not defined BASE_PYTHON if exist "%ProgramFiles%\Python311\python.exe" (
    "%ProgramFiles%\Python311\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "BASE_PYTHON=%ProgramFiles%\Python311\python.exe"
)

if not defined BASE_PYTHON for /d %%D in ("%LocalAppData%\Programs\Python\Python311*") do (
    if exist "%%~fD\python.exe" (
        "%%~fD\python.exe" -c "import sys" >nul 2>&1
        if not errorlevel 1 set "BASE_PYTHON=%%~fD\python.exe"
    )
)

if not defined BASE_PYTHON for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Python\PythonCore\3.11\InstallPath" /ve 2^>nul ^| find "REG_SZ"') do (
    if exist "%%B\python.exe" (
        "%%B\python.exe" -c "import sys" >nul 2>&1
        if not errorlevel 1 set "BASE_PYTHON=%%B\python.exe"
    )
)

if not defined BASE_PYTHON for /f "tokens=2,*" %%A in ('reg query "HKLM\Software\Python\PythonCore\3.11\InstallPath" /ve 2^>nul ^| find "REG_SZ"') do (
    if exist "%%B\python.exe" (
        "%%B\python.exe" -c "import sys" >nul 2>&1
        if not errorlevel 1 set "BASE_PYTHON=%%B\python.exe"
    )
)

where py >nul 2>&1
if not defined BASE_PYTHON if not errorlevel 1 (
    py -3.11 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "BASE_PYTHON=py"
        set "BASE_ARGS=-3.11"
    )
)

if not defined BASE_PYTHON (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -c "import sys" >nul 2>&1
        if not errorlevel 1 (
            set "BASE_PYTHON=py"
            set "BASE_ARGS=-3"
        )
    )
)

if not defined BASE_PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys" >nul 2>&1
        if not errorlevel 1 set "BASE_PYTHON=python"
    )
)

if not defined BASE_PYTHON (
    where python3.11 >nul 2>&1
    if not errorlevel 1 (
        python3.11 -c "import sys" >nul 2>&1
        if not errorlevel 1 set "BASE_PYTHON=python3.11"
    )
)

if not defined BASE_PYTHON (
    echo A usable Python 3.11 installation could not be started.
    echo.
    echo Install 64-bit Python 3.11, enable "Add Python to PATH", then
    echo close and reopen this terminal before running launch.bat again.
    echo Any existing stale project environment was left untouched.
    pause
    exit /b 1
)

echo Creating an isolated project environment in .runtime\
"%BASE_PYTHON%" %BASE_ARGS% -m venv .runtime
if errorlevel 1 goto :venv_error
set "PROJECT_PYTHON=%CD%\.runtime\Scripts\python.exe"

:dependencies
set "PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu"
set "PYTORCH_VARIANT=CPU"

where nvidia-smi >nul 2>&1
if not errorlevel 1 (
    nvidia-smi -L >nul 2>&1
    if not errorlevel 1 (
        set "PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu126"
        set "PYTORCH_VARIANT=CUDA 12.6"
    )
)

call :check_torch_variant
if errorlevel 1 (
    echo Installing the %PYTORCH_VARIANT% PyTorch runtime. This may take a while.
    "%PROJECT_PYTHON%" -m pip install --disable-pip-version-check --no-input --force-reinstall --no-cache-dir torch==2.6.0 torchaudio==2.6.0 --index-url "%PYTORCH_INDEX_URL%"
    if errorlevel 1 goto :torch_install_error
    call :check_torch_variant
    if errorlevel 1 goto :torch_verify_error
)

"%PROJECT_PYTHON%" -c "import importlib.util as u; names=('yaml','PySide6','torch','torchaudio','soundfile','pyloudnorm','syntok','tqdm','chatterbox','keyring'); assert all(u.find_spec(n) for n in names)" >nul 2>&1
if errorlevel 1 (
    echo Installing project dependencies. This may take a while.
    "%PROJECT_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto :install_error
)

echo Starting Diaphragm...
"%PROJECT_PYTHON%" -X faulthandler desktop_gui.py %*
set "DIAPHRAGM_EXIT_CODE=%ERRORLEVEL%"
if not "%DIAPHRAGM_EXIT_CODE%"=="0" goto :launch_error
exit /b 0

:check_torch_variant
if /i "%PYTORCH_VARIANT%"=="CUDA 12.6" (
    "%PROJECT_PYTHON%" -c "import torch, torchaudio; assert torch.__version__.split('+')[0]=='2.6.0'; assert torch.version.cuda=='12.6'; assert torch.cuda.is_available(); assert '+cu126' in torch.__version__; assert torchaudio.__version__.split('+')[0]=='2.6.0'; assert '+cu126' in torchaudio.__version__" >nul 2>&1
    if errorlevel 1 exit /b 1
) else (
    "%PROJECT_PYTHON%" -c "import torch, torchaudio; assert torch.__version__.split('+')[0]=='2.6.0'; assert torch.version.cuda is None; assert not torch.cuda.is_available(); assert '+cpu' in torch.__version__; assert torchaudio.__version__.split('+')[0]=='2.6.0'; assert '+cpu' in torchaudio.__version__" >nul 2>&1
    if errorlevel 1 exit /b 1
)
exit /b 0

:venv_error
echo Could not create the project Python environment.
pause
exit /b 1

:install_error
echo Could not install the project dependencies.
pause
exit /b 1

:torch_install_error
echo Could not install the selected %PYTORCH_VARIANT% PyTorch runtime.
echo Check your internet connection and NVIDIA driver, then try again.
pause
exit /b 1

:torch_verify_error
echo The selected %PYTORCH_VARIANT% PyTorch runtime could not access the expected device.
echo Check your NVIDIA driver, then try again.
pause
exit /b 1

:launch_error
echo The GUI could not be started (exit code %DIAPHRAGM_EXIT_CODE%).
echo Run launch.bat --smoke-test to collect a startup diagnostic.
pause
exit /b 1
