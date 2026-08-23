import json
from pathlib import Path

from ecom_dispute.abcd_preannotation import _conservative_audit_reasons, preannotate_abcd


class FakePreannotationClient:
    model = "fake-adjudicator"

    def create_response(self, payload: dict) -> dict:
        annotation = {
            "supported": True,
            "has_business_exception": True,
            "primary_route": "refund_progress",
            "acceptable_routes": [],
            "return_reason": None,
            "evidence_turns": [0],
            "reason": "用户明确表示退款尚未到账。",
            "confidence": "high",
            "ambiguity": None,
        }
        return {
            "id": "candidate-1",
            "model": self.model,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(annotation)}],
                }
            ],
        }


def test_preannotation_creates_separate_unverified_draft(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    output = tmp_path / "draft.json"
    source.write_text(
        json.dumps(
            {
                "rater_id": "rater1",
                "route_guide": {"refund_progress": "退款", "other": "其他"},
                "items": [
                    {
                        "external_id": "abcd:1",
                        "conversation": [{"speaker": "user", "text": "No refund yet"}],
                        "annotation": {"supported": None},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = preannotate_abcd(
        FakePreannotationClient(),  # type: ignore[arg-type]
        source,
        output,
        tmp_path / "cache.json",
        workers=1,
    )

    original = json.loads(source.read_text(encoding="utf-8"))
    draft = json.loads(output.read_text(encoding="utf-8"))
    assert original["items"][0]["annotation"] == {"supported": None}
    assert draft["rater_id"] == "assistant_draft"
    assert draft["items"][0]["annotation"]["primary_route"] == "refund_progress"
    assert draft["items"][0]["annotation"]["human_verified"] is False
    assert draft["items"][0]["assistant_review"]["review_tier"] == "quick_audit"
    assert result["quick_audit"] == 1


def test_audit_escalates_boundaries_without_changing_candidate() -> None:
    candidate = {"primary_route": "fulfillment_progress"}
    conversation = [
        {
            "speaker": "user",
            "text": "It shows delivered, but I haven't received the package.",
        }
    ]

    reasons = _conservative_audit_reasons(candidate, conversation)

    assert reasons == ["同时出现系统送达与用户未收到，复核delivered_not_received边界"]
    assert candidate == {"primary_route": "fulfillment_progress"}
