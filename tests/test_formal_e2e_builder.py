import json
from pathlib import Path

from ecom_dispute.e2e_evaluation import prepare_e2e_database
from ecom_dispute.formal_e2e_builder import build_formal_e2e


def test_formal_builder_creates_120_cases_before_model_run(tmp_path: Path) -> None:
    inputs = tmp_path / "formal-inputs.json"
    oracle = tmp_path / "formal-oracle.json"
    result = build_formal_e2e(tmp_path / "source.db", inputs, oracle)

    assert result["case_count"] == 120
    assert result["independent_templates"] == 84
    assert result["expression_variants"] == 36
    input_payload = json.loads(inputs.read_text(encoding="utf-8"))
    oracle_payload = json.loads(oracle.read_text(encoding="utf-8"))
    assert len(input_payload["cases"]) == 120
    assert len(oracle_payload) == 120
    assert all(count == 10 for count in result["routes"].values())

    repository, case_ids = prepare_e2e_database(
        tmp_path / "formal-import.db", inputs
    )
    assert len(case_ids) == 120
    assert repository.case("formal_refund_01").business_type == "refund"
