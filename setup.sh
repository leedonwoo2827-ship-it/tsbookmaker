#!/usr/bin/env bash
# TSBookMaker 설치 스크립트 (macOS / Linux)
set -e

echo "[TSBookMaker] Python 가상환경 생성중..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[TSBookMaker] pip 업그레이드중..."
python -m pip install --upgrade pip wheel setuptools

echo "[TSBookMaker] 의존성 설치중..."
pip install -e .

if [ ! -f ".env" ]; then
    echo "[TSBookMaker] .env 생성 (.env.example 복사)"
    cp .env.example .env
    echo
    echo "=== .env 파일이 생성되었습니다. ==="
    echo "=== DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY 를 채워주세요. ==="
    echo
fi

mkdir -p data/notebooks

echo "[TSBookMaker] 설치 완료. 실행: ./run.sh"
