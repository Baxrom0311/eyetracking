#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${1:-ubuntu@100.67.189.65}"

echo "Tunnel ochilmoqda: ${REMOTE_HOST}"
echo "eyetracking1 -> http://localhost:8000"
echo "eyetracking2 -> http://localhost:8090"
echo "To'xtatish uchun Ctrl+C bosing."

exec ssh \
  -L 8000:127.0.0.1:8000 \
  -L 8090:127.0.0.1:8090 \
  "${REMOTE_HOST}"
