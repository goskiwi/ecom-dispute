import json
from pathlib import Path

from ecom_dispute.review_ab_evaluation import build_review_manifest

ROOT = Path(__file__).resolve().parent.parent


def test_review_manifest_uses_real_available_category_distribution(tmp_path: Path) -> None:
    manifest = tmp_path / "review-manifest.json"
    result = build_review_manifest(
        ROOT / "data" / "formal_e2e_120_inputs.json",
        manifest,
        tmp_path / "review.db",
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert result["case_count"] == 40
    assert result["categories"] == {"conflict": 5, "missing": 4, "compliance": 31}
    assert len(payload["items"]) == 40
    assert payload["rubric"]["overall_preference"] == "A | B | tie"
