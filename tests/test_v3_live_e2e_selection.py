import json
from pathlib import Path


def test_live_e2e_selection_is_precommitted_stratified_and_leak_free() -> None:
    inputs = json.loads(Path("data/v3_1_live_e2e_40_inputs.json").read_text(encoding="utf-8"))
    oracle = json.loads(Path("evals/v3_1_live_e2e_40_oracle.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path("evals/v3_1_live_e2e_40_manifest.json").read_text(encoding="utf-8"))
    assert len(inputs["cases"]) == len(oracle) == manifest["case_count"] == 40
    assert manifest["route_count"] == 26
    assert sum(item["review_required"] for item in oracle.values()) == 31
    assert sum(item["action_type"] is not None for item in oracle.values()) == 12
    cases = {item["case_id"]: item for item in inputs["cases"]}
    for item in manifest["items"]:
        conversation = json.dumps(cases[item["case_id"]]["conversation"], ensure_ascii=False)
        assert item["decision"] not in conversation
