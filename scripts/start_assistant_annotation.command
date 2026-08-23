#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
cd "$PROJECT_DIR"

DRAFT=evals/v3_abcd_200_assistant_draft.json
if [[ ! -f "$DRAFT" ]]; then
  echo "Missing $DRAFT. Run abcd-preannotate first."
  read -r "?Press Return to close."
  exit 1
fi

echo ""
echo "Assistant-assisted ABCD review: http://127.0.0.1:8879/"
echo "Keep this Terminal window open. Press Control-C to stop."
echo ""

uv run python -m ecom_dispute abcd-annotation-web \
  --form "$DRAFT" \
  --audit-sample evals/v3_abcd_200_quick_audit_sample.json \
  --host 127.0.0.1 \
  --port 8879
