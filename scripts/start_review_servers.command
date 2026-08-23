#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
cd "$PROJECT_DIR"

cleanup() {
  kill "${ABCD_PID:-}" "${REVIEW_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uv run python -m ecom_dispute abcd-annotation-web \
  --form evals/formal_abcd_200_rater1.json \
  --host 127.0.0.1 \
  --port 8877 &
ABCD_PID=$!

uv run python -m ecom_dispute review-ab-web \
  --form evals/formal_review_40_rater1.json \
  --host 127.0.0.1 \
  --port 8887 &
REVIEW_PID=$!

echo ""
echo "EcomDispute review services are running."
echo "ABCD annotation: http://127.0.0.1:8877/"
echo "Review A/B:     http://127.0.0.1:8887/"
echo "Keep this Terminal window open. Press Control-C to stop both services."
echo ""

wait
