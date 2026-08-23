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
  --form evals/v3_abcd_200_rater1.json \
  --host 127.0.0.1 \
  --port 8877 &
ABCD_PID=$!

if [[ -f evals/v3_review_blind_form.json ]]; then
  uv run python -m ecom_dispute review-ab-web \
    --form evals/v3_review_blind_form.json \
    --host 127.0.0.1 \
    --port 8887 &
  REVIEW_PID=$!
fi

echo ""
echo "EcomDispute review services are running."
echo "ABCD annotation: http://127.0.0.1:8877/"
if [[ -n "${REVIEW_PID:-}" ]]; then
  echo "Review A/B:     http://127.0.0.1:8887/"
else
  echo "Review A/B:     not started (generate evals/v3_review_blind_form.json first)"
fi
echo "Keep this Terminal window open. Press Control-C to stop both services."
echo ""

wait
