@echo off
REM TSBookMaker 실행 스크립트 (Windows)
REM .venv\Scripts\streamlit.exe 를 직접 호출 — activate 불필요, 더블클릭 안전.

if not exist ".venv\Scripts\streamlit.exe" (
    echo.
    echo [TSBookMaker] streamlit 이 설치되어 있지 않습니다.
    echo [TSBookMaker] 먼저 setup.bat 을 실행하세요.
    echo.
    pause
    exit /b 1
)

set TSB_UI_PORT=8610

echo.
echo ===================================================
echo  TSBookMaker - http://localhost:%TSB_UI_PORT%
echo  (종료: 이 창에서 Ctrl+C, 또는 X 로 창 닫기)
echo ===================================================
echo.

".venv\Scripts\streamlit.exe" run app.py --server.port %TSB_UI_PORT% --server.headless false

REM 만에 하나 streamlit 이 즉시 종료된 경우 에러 메시지를 볼 수 있도록 대기
if errorlevel 1 pause
