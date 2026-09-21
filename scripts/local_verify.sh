#!/usr/bin/env bash
# Real end-to-end acceptance on a host without Docker.
# Starts the real FastAPI service and the nginx-equivalent static+proxy
# server, then runs backend/verify.py over HTTP and reports its exit code.
set -u
cd "$(dirname "$0")/.."

PY="$PWD/.venv/bin/python"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-8080}"

cleanup() {
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null
}
trap cleanup EXIT

(cd backend && "$PY" -m uvicorn app.main:app --host 127.0.0.1 \
  --port "$API_PORT") >/tmp/verify-api.log 2>&1 &
API_PID=$!
(cd backend && API_URL="http://127.0.0.1:$API_PORT" WEB_PORT="$WEB_PORT" \
  "$PY" ../scripts/dev_proxy.py) >/tmp/verify-web.log 2>&1 &
WEB_PID=$!

VERIFY_WEB_URL="http://127.0.0.1:$WEB_PORT" \
VERIFY_API_URL="http://127.0.0.1:$API_PORT" \
  "$PY" backend/verify.py
code=$?
echo "verify exit code: $code"
exit $code
