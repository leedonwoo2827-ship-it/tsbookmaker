#!/usr/bin/env bash
# TSBookMaker 실행 스크립트 (macOS / Linux)
set -e

if [ ! -f ".venv/bin/activate" ]; then
    echo "[TSBookMaker] .venv 가 없습니다. 먼저 ./setup.sh 를 실행하세요."
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# .env 로드
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

: "${TSB_UI_PORT:=8610}"
: "${TSB_LITELLM_PORT:=4610}"

echo "[TSBookMaker] LiteLLM proxy 기동중 (port ${TSB_LITELLM_PORT})..."
litellm --config litellm_config.yaml --port "${TSB_LITELLM_PORT}" >/tmp/tsbm-litellm.log 2>&1 &
LITELLM_PID=$!
trap "kill ${LITELLM_PID} 2>/dev/null || true" EXIT

sleep 3

echo "[TSBookMaker] Streamlit UI 기동중 (port ${TSB_UI_PORT})..."
echo "[TSBookMaker] 브라우저: http://localhost:${TSB_UI_PORT}"
streamlit run app.py --server.port "${TSB_UI_PORT}" --server.headless true
