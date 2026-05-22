@echo off
REM TSBookMaker 설치 스크립트 (Windows)
setlocal

echo [TSBookMaker] Python 가상환경 생성중...
if not exist .venv (
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [TSBookMaker] pip 업그레이드중...
python -m pip install --upgrade pip wheel setuptools

echo [TSBookMaker] 의존성 설치중...
pip install -e .

if not exist .env (
    echo [TSBookMaker] .env 생성 (.env.example 복사^)
    copy .env.example .env
    echo.
    echo === .env 파일이 생성되었습니다. ===
    echo === DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY 를 채워주세요. ===
    echo.
)

if not exist data\notebooks (
    mkdir data\notebooks
)

echo [TSBookMaker] 설치 완료. 실행: run.bat
endlocal
