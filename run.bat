@echo off
chcp 65001 > nul
REM TSBookMaker launcher (Windows). Calls .venv\Scripts\streamlit.exe directly
REM so no venv activation is needed. Kept ASCII-only to avoid cmd codepage
REM issues that swallowed earlier double-click attempts.

if not exist ".venv\Scripts\streamlit.exe" (
    echo.
    echo [TSBookMaker] streamlit is not installed.
    echo [TSBookMaker] Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

set "TSB_UI_PORT=8610"

echo.
echo ===================================================
echo  TSBookMaker - http://localhost:%TSB_UI_PORT%
echo  Stop: Ctrl+C in this window, or close it.
echo ===================================================
echo.

".venv\Scripts\streamlit.exe" run app.py --server.port %TSB_UI_PORT% --server.headless false

if errorlevel 1 pause
