import json
from pathlib import Path

from ecom_dispute.review_web import ReviewFormApplication


def test_review_web_persists_ratings(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "review_id": "review-01",
                        "ratings": {"overall_preference": None},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    application = ReviewFormApplication(path)

    application.update("review-01", {"overall_preference": "A"})

    assert application.form()["items"][0]["ratings"]["overall_preference"] == "A"
