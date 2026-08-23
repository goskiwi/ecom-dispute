from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .repository import Repository, rebuild_database

ROOT = Path(__file__).resolve().parents[1]

CHILD_TABLES = (
    "payments",
    "refunds",
    "logistics_events",
    "order_items",
    "payment_gateway_events",
    "delivery_proofs",
    "delivery_addresses",
    "cancellation_requests",
    "return_requests",
    "warehouse_pack_records",
    "claim_attachments",
    "order_fee_records",
    "charge_dispute_records",
    "return_tracking_events",
    "exchange_options",
    "order_change_options",
    "product_catalog_records",
    "inventory_records",
    "price_records",
    "promotion_records",
    "shipping_option_records",
    "membership_records",
    "checkout_events",
    "cart_events",
    "search_events",
    "site_health_events",
)


def build_formal_e2e(
    db_path: Path,
    input_path: Path,
    oracle_path: Path,
) -> dict:
    repository = Repository(rebuild_database(db_path))
    cases = [_export_case(repository, case_id) for case_id in repository.case_ids()]
    oracle = json.loads((ROOT / "evals" / "v3_decision_oracle.json").read_text(encoding="utf-8"))
    input_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        json.dumps(
            {"source": "v3_frozen_26_route_minimum", "cases": cases}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    oracle_path.write_text(
        json.dumps(oracle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "case_count": len(cases),
        "independent_templates": len(cases),
        "expression_variants": 0,
        "routes": dict(Counter(case["business_type"] for case in cases)),
    }


def _export_case(repository: Repository, case_id: str) -> dict:
    case = repository.case(case_id)
    with repository.connect() as connection:
        order = dict(
            connection.execute(
                "SELECT * FROM orders WHERE order_id = ?", (case.order_id,)
            ).fetchone()
        )
        after_sales_row = connection.execute(
            "SELECT * FROM after_sales_cases WHERE order_id = ?", (case.order_id,)
        ).fetchone()
        children = {
            table: [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM {table} WHERE order_id = ?", (case.order_id,)
                ).fetchall()
            ]
            for table in CHILD_TABLES
        }
    return {
        "case_id": case.case_id,
        "order_id": case.order_id,
        "region": case.region,
        "business_type": case.business_type,
        "occurred_at": case.occurred_at.isoformat(),
        "current_time": case.current_time.isoformat(),
        "conversation": case.conversation,
        "order": order,
        "after_sales": dict(after_sales_row) if after_sales_row else None,
        **children,
    }
