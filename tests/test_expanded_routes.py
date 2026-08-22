import json
from pathlib import Path

import pytest

from ecom_dispute.harness import DiagnosticHarness
from ecom_dispute.repository import Repository, rebuild_database


def _insert_case(
    repository: Repository,
    *,
    case_id: str,
    business_type: str,
    order_status: str = "paid",
    paid_amount: float = 199.0,
    current_time: str = "2026-04-05T12:00:00",
) -> str:
    order_id = f"ord-{case_id}"
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO cases VALUES (?, ?, 'manual', 'CN', ?, ?, ?, ?)",
            (
                case_id,
                order_id,
                business_type,
                "2026-04-01T10:00:00",
                current_time,
                json.dumps(
                    [
                        {"speaker": "user", "text": "请核验这笔争议。"},
                        {"speaker": "agent", "text": "正在核验业务记录。"},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO orders VALUES (?, 'user-expanded', 'CN', ?, ?, ?, 'CNY', ?, ?, 1)",
            (
                order_id,
                business_type,
                order_status,
                paid_amount,
                "2026-04-01T08:00:00",
                "2026-04-03T18:00:00",
            ),
        )
    return order_id


@pytest.fixture()
def repository(tmp_path: Path) -> Repository:
    return Repository(rebuild_database(tmp_path / "expanded.db"))


def test_refund_amount_mismatch_route(repository: Repository) -> None:
    order_id = _insert_case(
        repository, case_id="expanded-refund-amount", business_type="refund_amount"
    )
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO payments VALUES ('expanded-debit', ?, 'debit', 199, 'succeeded', '2026-04-01T08:01:00', 1)",
            (order_id,),
        )
        connection.execute(
            "INSERT INTO payments VALUES ('expanded-credit', ?, 'credit', 99, 'succeeded', '2026-04-03T08:01:00', 1)",
            (order_id,),
        )
        connection.execute(
            "INSERT INTO refunds VALUES ('expanded-refund', ?, 99, 'succeeded', '2026-04-02T08:00:00', '2026-04-03T08:00:00', 1)",
            (order_id,),
        )

    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("expanded-refund-amount")
    )

    assert report.dispute_type == "refund_amount_mismatch"
    assert report.decision == "refund_amount_incorrect"
    assert report.responsible_party == "platform"


def test_duplicate_charge_route(repository: Repository) -> None:
    order_id = _insert_case(
        repository, case_id="expanded-duplicate", business_type="duplicate_charge"
    )
    with repository.connect() as connection:
        connection.executemany(
            "INSERT INTO payments VALUES (?, ?, 'debit', 199, 'succeeded', ?, 1)",
            [
                ("duplicate-1", order_id, "2026-04-01T08:01:00"),
                ("duplicate-2", order_id, "2026-04-01T08:02:00"),
            ],
        )

    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("expanded-duplicate")
    )

    assert report.decision == "duplicate_charge_confirmed"
    assert report.responsible_party == "payment_channel"
    assert report.review_required


def test_payment_captured_order_failed_route(repository: Repository) -> None:
    order_id = _insert_case(
        repository,
        case_id="expanded-order-failed",
        business_type="payment_order_failure",
        order_status="failed",
    )
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO payments VALUES ('failed-debit', ?, 'debit', 199, 'succeeded', '2026-04-01T08:01:00', 1)",
            (order_id,),
        )

    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("expanded-order-failed")
    )

    assert report.decision == "captured_order_failed_unreversed"
    assert report.responsible_party == "platform"


def test_merchant_not_shipped_route(repository: Repository) -> None:
    _insert_case(
        repository,
        case_id="expanded-not-shipped",
        business_type="merchant_not_shipped",
        current_time="2026-04-05T12:00:00",
    )

    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("expanded-not-shipped")
    )

    assert report.decision == "merchant_ship_overdue"
    assert report.responsible_party == "merchant"


def test_delivered_not_received_route(repository: Repository) -> None:
    order_id = _insert_case(
        repository,
        case_id="expanded-not-received",
        business_type="delivered_not_received",
        order_status="delivered",
    )
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO logistics_events VALUES ('delivered-event', ?, 'delivered', '2026-04-03T12:00:00', 'signed', 1)",
            (order_id,),
        )
        connection.execute(
            "INSERT INTO delivery_proofs VALUES ('proof-1', ?, '门卫', 'signature', '2026-04-03T12:00:00', 'signed by concierge', 1)",
            (order_id,),
        )
        connection.execute(
            "INSERT INTO delivery_addresses VALUES ('address-1', ?, '南京', '鼓楼区***路', '1234', 1)",
            (order_id,),
        )

    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("expanded-not-received")
    )

    assert report.decision == "delivery_receipt_disputed"
    assert report.review_required
    assert any(item.kind.value == "delivery_proof" for item in report.evidence)


def test_cancellation_in_transit_route(repository: Repository) -> None:
    order_id = _insert_case(
        repository,
        case_id="expanded-cancel-transit",
        business_type="cancellation_in_transit",
    )
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO cancellation_requests VALUES ('cancel-1', ?, 'accepted', '2026-04-01T09:00:00', '2026-04-01T09:01:00', 'user_request', 1)",
            (order_id,),
        )
        connection.execute(
            "INSERT INTO logistics_events VALUES ('pickup-after-cancel', ?, 'picked_up', '2026-04-01T10:00:00', 'carrier_pickup', 1)",
            (order_id,),
        )

    report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
        repository.case("expanded-cancel-transit")
    )

    assert report.decision == "cancel_before_pickup_but_shipped"
    assert report.responsible_party == "merchant"
