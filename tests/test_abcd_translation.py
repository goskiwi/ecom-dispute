import json
from pathlib import Path

from ecom_dispute.abcd_translation import translate_annotation_forms


class FakeTranslationClient:
    model = "fake-translator"

    def create_response(self, payload: dict) -> dict:
        translated = {"turns": [{"speaker": "user", "text": "我的退款在哪里？"}]}
        return {
            "id": "translation-1",
            "model": self.model,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(translated)}],
                }
            ],
        }


def test_translation_is_shared_without_exposing_route_labels(tmp_path: Path) -> None:
    base = {
        "rater_id": "rater1",
        "items": [
            {
                "external_id": "abcd:1",
                "conversation": [{"speaker": "user", "text": "Where is my refund?"}],
                "annotation": {"primary_route": None},
            }
        ],
    }
    first = tmp_path / "r1.json"
    second = tmp_path / "r2.json"
    first.write_text(json.dumps(base), encoding="utf-8")
    base["rater_id"] = "rater2"
    second.write_text(json.dumps(base), encoding="utf-8")

    result = translate_annotation_forms(
        FakeTranslationClient(),  # type: ignore[arg-type]
        first,
        second,
        tmp_path / "cache.json",
        workers=1,
    )

    first_payload = json.loads(first.read_text(encoding="utf-8"))
    second_payload = json.loads(second.read_text(encoding="utf-8"))
    assert result["translated"] == 1
    assert first_payload["items"][0]["translation"][0]["text"] == "我的退款在哪里？"
    assert first_payload["items"][0]["translation"] == second_payload["items"][0]["translation"]
    assert first_payload["items"][0]["annotation"]["primary_route"] is None
