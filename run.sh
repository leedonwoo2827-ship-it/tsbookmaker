#!/usr/bin/env bash
# TSBookMaker 실행 스크립트 (macOS / Linux)
# Streamlit UI 한 프로세스만 기동. API URL/Key 는 화면 좌측 ⚙ 설정에서 입력.
set -e

if [ ! -f ".venv/bin/activate" ]; then
    echo "[TSBookMaker] .venv 가 없습니다. 먼저 ./setup.sh 를 실행하세요."
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

: "${TSB_UI_PORT:=8610}"

echo "[TSBookMaker] Streamlit UI 기동중 (port ${TSB_UI_PORT})..."
echo "[TSBookMaker] 브라우저: http://localhost:${TSB_UI_PORT}"
streamlit run app.py --server.port "${TSB_UI_PORT}" --server.headless false
