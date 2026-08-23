import json
from pathlib import Path

from ecom_dispute.annotation_web import AnnotationApplication


def test_annotation_web_overlays_quick_audit_sample(tmp_path: Path) -> None:
    form_path = tmp_path / "form.json"
    sample_path = tmp_path / "sample.json"
    form_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "external_id": "abcd:1",
                        "annotation": {"primary_route": "other"},
                        "assistant_review": {"review_tier": "quick_audit"},
                    },
                    {
                        "external_id": "abcd:2",
                        "annotation": {"primary_route": "other"},
                        "assistant_review": {"review_tier": "quick_audit"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    sample_path.write_text(
        json.dumps({"items": [{"external_id": "abcd:2"}]}),
        encoding="utf-8",
    )

    items = AnnotationApplication(form_path, sample_path).form()["items"]

    assert items[0]["assistant_review"]["quick_audit_sample"] is False
    assert items[1]["assistant_review"]["quick_audit_sample"] is True
