@echo off
chcp 65001 > nul
setlocal

REM Move into the directory where this batch file is located so that
REM relative imports (e.g. "main:app") resolve correctly.
cd /d "%~dp0"

set "VENV_ACTIVATE="

REM Search candidate virtual environment locations in priority order.
if exist "%~dp0.venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%~dp0venv\Scripts\activate.bat"
) else if exist "%~dp0..\.venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%~dp0..\.venv\Scripts\activate.bat"
) else if exist "%~dp0..\venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%~dp0..\venv\Scripts\activate.bat"
) else if exist "%~dp0..\..\.venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%~dp0..\..\.venv\Scripts\activate.bat"
) else if exist "%~dp0..\..\venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%~dp0..\..\venv\Scripts\activate.bat"
)

if defined VENV_ACTIVATE (
    echo [start.bat] Activating virtual env: %VENV_ACTIVATE%
    call "%VENV_ACTIVATE%"
) else (
    echo [start.bat] No virtual env found. Using system python.
)

echo [start.bat] Running python main.py
python main.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [start.bat] Server exited abnormally. exit_code=%EXIT_CODE%
    pause
)

endlocal & exit /b %EXIT_CODE%
