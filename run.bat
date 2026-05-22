@echo off
REM TSBookMaker 실행 스크립트 (Windows)
REM LiteLLM 프록시 + Streamlit UI 동시 기동
setlocal enabledelayedexpansion

if not exist .venv\Scripts\activate.bat (
    echo [TSBookMaker] .venv 가 없습니다. 먼저 setup.bat 을 실행하세요.
    exit /b 1
)

call .venv\Scripts\activate.bat

REM .env 로드 (간단한 파서)
if exist .env (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        set "%%A=%%B"
    )
)

REM 디폴트 포트
if "%TSB_UI_PORT%"=="" set TSB_UI_PORT=8610
if "%TSB_LITELLM_PORT%"=="" set TSB_LITELLM_PORT=4610

echo [TSBookMaker] LiteLLM proxy 기동중 (port %TSB_LITELLM_PORT%)...
start "TSBM-LiteLLM" cmd /c litellm --config litellm_config.yaml --port %TSB_LITELLM_PORT%

REM LiteLLM 가 뜨기까지 잠깐 대기
timeout /t 3 /nobreak >nul

echo [TSBookMaker] Streamlit UI 기동중 (port %TSB_UI_PORT%)...
echo [TSBookMaker] 브라우저: http://localhost:%TSB_UI_PORT%
streamlit run app.py --server.port %TSB_UI_PORT% --server.headless true

endlocal
