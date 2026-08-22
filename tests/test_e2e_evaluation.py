import json
from pathlib import Path

from ecom_dispute.e2e_evaluation import _score_report, prepare_e2e_database
from ecom_dispute.harness import DiagnosticHarness

ROOT = Path(__file__).resolve().parent.parent


def test_e2e_database_import_and_fixed_scoring(tmp_path: Path) -> None:
    repository, case_ids = prepare_e2e_database(
        tmp_path / "e2e.db", ROOT / "data" / "e2e_blind_inputs.json"
    )
    assert len(case_ids) == 20
    case = repository.case("e2e_refund_001")
    assert case.source_type == "e2e_blind"

    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(case)
    oracle = json.loads((ROOT / "evals" / "e2e_blind_oracle.json").read_text())
    scored = _score_report(report, oracle[case.case_id])
    assert scored["checks"]["decision"]
    assert scored["checks"]["responsible_party"]
    assert scored["checks"]["required_evidence"]
    assert scored["checks"]["evidence_grounded"]
