import json
from pathlib import Path

import pytest

from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database


@pytest.fixture()
def repository(tmp_path: Path) -> Repository:
    return Repository(rebuild_database(tmp_path / "item.db"))


def _base_case(repository: Repository, case_id: str, business_type: str) -> str:
    order_id = f"ord-{case_id}"
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO cases VALUES (?, ?, 'manual', 'CN', ?, '2026-04-01T10:00:00', '2026-04-05T12:00:00', ?)",
            (
                case_id,
                order_id,
                business_type,
                json.dumps(
                    [
                        {"speaker": "user", "text": "商品存在售后问题。"},
                        {"speaker": "agent", "text": "正在核验。"},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO orders VALUES (?, 'item-user', 'CN', ?, 'delivered', 199, 'CNY', '2026-04-01T08:00:00', '2026-04-03T18:00:00', 1)",
            (order_id, business_type),
        )
        connection.execute(
            "INSERT INTO order_items VALUES (?, ?, 'sku-ordered', '测试商品', 2, 99.5, 'general', 1)",
            (f"item-{case_id}", order_id),
        )
    return order_id


def test_return_eligibility(repository: Repository) -> None:
    order_id = _base_case(repository, "item-return", "return_eligibility")
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO return_requests VALUES ('return-1', ?, ?, 'requested', '2026-04-05T08:00:00', 'no_longer_needed', 'unopened', 1)",
            (order_id, "item-item-return"),
        )
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("item-return")
    )
    assert report.decision == "return_eligible"


def test_wrong_item_uses_warehouse_sku(repository: Repository) -> None:
    order_id = _base_case(repository, "item-wrong", "wrong_item")
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO warehouse_pack_records VALUES ('pack-wrong', ?, 'sku-other', 2, '2026-04-02T08:00:00', 'station-1', 1)",
            (order_id,),
        )
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("item-wrong")
    )
    assert report.decision == "wrong_item_warehouse_mismatch"


def test_missing_item_uses_packed_quantity(repository: Repository) -> None:
    order_id = _base_case(repository, "item-missing", "missing_item")
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO warehouse_pack_records VALUES ('pack-missing', ?, 'sku-ordered', 1, '2026-04-02T08:00:00', 'station-2', 1)",
            (order_id,),
        )
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("item-missing")
    )
    assert report.decision == "missing_item_warehouse_shortage"


def test_damaged_item_keeps_attachment_as_reference(repository: Repository) -> None:
    order_id = _base_case(repository, "item-damaged", "damaged_item")
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO claim_attachments VALUES ('attachment-1', ?, 'damage_photo', 'evidence://item-damaged/photo-1', 524288, '商品外壳破裂照片', '2026-04-04T08:00:00', 1)",
            (order_id,),
        )
    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("item-damaged")
    )
    attachment = next(item for item in report.evidence if item.kind.value == "claim_attachment")
    assert report.decision == "damaged_item_evidence_confirmed"
    assert attachment.uri == "evidence://item-damaged/photo-1"
    assert attachment.size_bytes == 524288
    assert "raw" not in attachment.facts
