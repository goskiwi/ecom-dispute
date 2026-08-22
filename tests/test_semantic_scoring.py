from pathlib import Path

from ecom_dispute.semantic_scoring import rescore_semantic_run

ROOT = Path(__file__).resolve().parent.parent


def test_audited_oracle_rescores_without_rerunning_model() -> None:
    result = rescore_semantic_run(
        ROOT / "evals" / "hybrid_semantic_gpt-5.4-mini_40cases_2026-08-22.json",
        ROOT / "evals" / "semantic_oracle.json",
    )
    assert result["case_count"] == 40
    assert result["passed"] == 34
    assert result["semantic_metrics"]["conversation_conflict_precision"] == 1.0
    assert result["semantic_metrics"]["conversation_conflict_recall"] == 1.0
