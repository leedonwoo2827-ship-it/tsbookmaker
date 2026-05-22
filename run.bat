@echo off
REM TSBookMaker 실행 스크립트 (Windows)
REM Streamlit UI 한 프로세스만 기동. API URL/Key 는 화면 좌측 ⚙ 설정에서 입력.
setlocal enabledelayedexpansion

if not exist .venv\Scripts\activate.bat (
    echo [TSBookMaker] .venv 가 없습니다. 먼저 setup.bat 을 실행하세요.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

if exist .env (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        set "%%A=%%B"
    )
)

if "%TSB_UI_PORT%"=="" set TSB_UI_PORT=8610

echo [TSBookMaker] Streamlit UI 기동중 (port %TSB_UI_PORT%)...
echo [TSBookMaker] 브라우저: http://localhost:%TSB_UI_PORT%
echo [TSBookMaker] 종료: 이 창에서 Ctrl+C
streamlit run app.py --server.port %TSB_UI_PORT% --server.headless false

endlocal
