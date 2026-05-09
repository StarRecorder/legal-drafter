@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
set "INDEX_PATH=%ROOT%law_index.sqlite3"

if not exist "%PYTHON%" (
    echo [ERROR] Python venv executable not found:
    echo         %PYTHON%
    echo.
    echo Create the virtual environment first, for example:
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -e .[dev]
    exit /b 1
)

if not exist "%INDEX_PATH%" (
    echo [ERROR] Law index file not found:
    echo         %INDEX_PATH%
    echo.
    echo Build the index first, for example:
    echo   .venv\Scripts\legal-drafter-index.exe refresh --service-topic ECOMMERCE --rebuild
    exit /b 1
)

pushd "%ROOT%"
echo Starting legal-drafter demo server...
echo URL: http://127.0.0.1:8000
echo Press Ctrl+C to stop.
echo.
"%PYTHON%" -m legal_drafter.cli.demo --index-path "%INDEX_PATH%" --host 127.0.0.1 --port 8000 %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
