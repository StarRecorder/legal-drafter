@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Python venv executable not found:
    echo         %PYTHON%
    echo.
    echo Create the virtual environment first, for example:
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -e .[dev]
    exit /b 1
)

pushd "%ROOT%"
echo Starting legal-drafter backend server...
echo URL: http://127.0.0.1:8000
echo Use --index-path to override the default index location if needed.
echo Press Ctrl+C to stop.
echo.
"%PYTHON%" -m legal_drafter.cli.demo --host 127.0.0.1 --port 8000 %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
