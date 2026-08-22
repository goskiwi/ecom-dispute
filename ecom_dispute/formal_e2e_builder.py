from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .repository import Repository, rebuild_database

ROOT = Path(__file__).resolve().parent.parent
ROUTES = (
    "refund",
    "refund_amount",
    "duplicate_charge",
    "payment_order_failure",
    "delivery",
    "merchant_not_shipped",
    "delivered_not_received",
    "cancellation_in_transit",
    "return_eligibility",
    "wrong_item",
    "missing_item",
    "damaged_item",
)

CHILD_TABLES = {
    "payments": "payment_id",
    "refunds": "refund_id",
    "logistics_events": "event_id",
    "order_items": "order_item_id",
    "payment_gateway_events": "gateway_event_id",
    "delivery_proofs": "proof_id",
    "delivery_addresses": "address_id",
    "cancellation_requests": "cancellation_id",
    "return_requests": "return_request_id",
    "warehouse_pack_records": "pack_record_id",
    "claim_attachments": "attachment_id",
}


def build_formal_e2e(
    db_path: Path,
    input_path: Path,
    oracle_path: Path,
) -> dict:
    repository = Repository(rebuild_database(db_path))
    regression_oracle = _load_regression_oracle()
    grouped: dict[str, list[str]] = defaultdict(list)
    for case_id in repository.case_ids():
        case = repository.case(case_id)
        if case.business_type in ROUTES:
            grouped[case.business_type].append(case_id)

    cases = []
    oracle = {}
    independent_templates = expression_variants = 0
    for route in ROUTES:
        source_ids = sorted(grouped[route])
        if not source_ids:
            raise ValueError(f"no regression cases available for route: {route}")
        selected = source_ids[:10]
        independent_templates += len(selected)
        while len(selected) < 10:
            selected.append(source_ids[len(selected) % len(source_ids)])
            expression_variants += 1
        for index, source_case_id in enumerate(selected, start=1):
            formal_id = f"formal_{route}_{index:02d}"
            exported = _export_case(repository, source_case_id, formal_id)
            if index > len(source_ids[:10]) or _is_generic(exported["conversation"]):
                exported["conversation"] = _formal_conversation(
                    route, regression_oracle[source_case_id]["decision"], index
                )
            cases.append(exported)
            expected = dict(regression_oracle[source_case_id])
            expected.update(_route_contract(route, exported, expected))
            oracle[formal_id] = expected

    payload = {
        "source": "formal_e2e_120_pre_llm_84_templates_36_expression_variants",
        "cases": cases,
    }
    input_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    oracle_path.write_text(json.dumps(oracle, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "case_count": len(cases),
        "independent_templates": independent_templates,
        "expression_variants": expression_variants,
        "routes": {route: 10 for route in ROUTES},
    }


def _load_regression_oracle() -> dict[str, dict]:
    oracle = json.loads((ROOT / "evals" / "oracle.json").read_text(encoding="utf-8"))
    for name in ("oracle_m6.json", "oracle_m8.json"):
        path = ROOT / "evals" / name
        if path.is_file():
            oracle.update(json.loads(path.read_text(encoding="utf-8")))
    matrix = json.loads(
        (ROOT / "data" / "cases" / "m10_item_matrix.json").read_text(encoding="utf-8")
    )
    for group in matrix:
        for offset in range(group["count"]):
            variant = group["variants"][offset % len(group["variants"])]
            oracle[f"m10_{group['business_type']}_{offset + 1:03d}"] = variant["expected"]
    return oracle


def _export_case(repository: Repository, source_case_id: str, formal_id: str) -> dict:
    case = repository.case(source_case_id)
    order_id = f"{formal_id}-order"
    with repository.connect() as connection:
        order = dict(
            connection.execute(
                "SELECT * FROM orders WHERE order_id = ?", (case.order_id,)
            ).fetchone()
        )
        after_sales_row = connection.execute(
            "SELECT * FROM after_sales_cases WHERE order_id = ?", (case.order_id,)
        ).fetchone()
        rows = {
            table: [dict(item) for item in connection.execute(
                f"SELECT * FROM {table} WHERE order_id = ?", (case.order_id,)
            ).fetchall()]
            for table in CHILD_TABLES
        }

    order.pop("order_id")
    order.pop("region")
    order.pop("business_type")
    id_map: dict[str, str] = {}
    for table, key in CHILD_TABLES.items():
        for row_index, row in enumerate(rows[table], start=1):
            old_id = str(row[key])
            new_id = f"{formal_id}-{table}-{row_index}"
            id_map[old_id] = new_id
            row[key] = new_id
            row.pop("order_id")
    for row in rows["return_requests"]:
        row["order_item_id"] = id_map.get(row["order_item_id"], row["order_item_id"])

    after_sales = dict(after_sales_row) if after_sales_row else None
    if after_sales:
        after_sales["after_sales_id"] = f"{formal_id}-after-sales"
        after_sales.pop("order_id")
    return {
        "case_id": formal_id,
        "order_id": order_id,
        "region": case.region,
        "business_type": case.business_type,
        "occurred_at": case.occurred_at.isoformat(),
        "current_time": case.current_time.isoformat(),
        "conversation": case.conversation,
        "order": order,
        "payments": rows["payments"],
        "refunds": rows["refunds"],
        "after_sales": after_sales,
        "logistics_events": rows["logistics_events"],
        "order_items": rows["order_items"],
        "payment_gateway_events": rows["payment_gateway_events"],
        "delivery_proofs": rows["delivery_proofs"],
        "delivery_addresses": rows["delivery_addresses"],
        "cancellation_requests": rows["cancellation_requests"],
        "return_requests": rows["return_requests"],
        "warehouse_pack_records": rows["warehouse_pack_records"],
        "claim_attachments": rows["claim_attachments"],
    }


def _route_contract(route: str, exported: dict, expected: dict) -> dict[str, Any]:
    tool_map = {
        "refund": ["get_order", "get_payment_records", "get_refund_records", "get_after_sales_case", "read_policy"],
        "refund_amount": ["get_order", "get_payment_records", "get_refund_records", "read_policy"],
        "duplicate_charge": ["get_order", "get_payment_records", "get_refund_records", "read_policy"],
        "payment_order_failure": ["get_order", "get_payment_records", "get_refund_records", "read_policy"],
        "delivery": ["get_order", "get_logistics_events", "read_policy"],
        "merchant_not_shipped": ["get_order", "get_logistics_events", "read_policy"],
        "delivered_not_received": ["get_order", "get_logistics_events", "get_delivery_proof", "get_delivery_address", "read_policy"],
        "cancellation_in_transit": ["get_order", "get_logistics_events", "get_cancellation_request", "get_refund_records", "read_policy"],
        "return_eligibility": ["get_order", "get_order_items", "get_return_request", "read_policy"],
        "wrong_item": ["get_order", "get_order_items", "get_warehouse_pack_record", "get_claim_attachments", "read_policy"],
        "missing_item": ["get_order", "get_order_items", "get_warehouse_pack_record", "get_claim_attachments", "read_policy"],
        "damaged_item": ["get_order", "get_order_items", "get_warehouse_pack_record", "get_claim_attachments", "get_logistics_events", "read_policy"],
    }
    agents = ["conversation"]
    if route in {"refund_amount", "duplicate_charge", "payment_order_failure", "return_eligibility"}:
        agents.append("evidence_gap")
    if expected["review_required"]:
        agents.append("review")
    evidence = {"conversation", "order", "policy"}
    evidence_map = {
        "payments": "payment",
        "refunds": "refund",
        "logistics_events": "logistics",
        "order_items": "order_item",
        "payment_gateway_events": "payment_gateway",
        "delivery_proofs": "delivery_proof",
        "delivery_addresses": "delivery_address",
        "cancellation_requests": "cancellation_request",
        "return_requests": "return_request",
        "warehouse_pack_records": "warehouse_pack",
        "claim_attachments": "claim_attachment",
    }
    if exported["after_sales"]:
        evidence.add("after_sales")
    for field, kind in evidence_map.items():
        if exported[field]:
            evidence.add(kind)
    return {
        "route_type": route,
        "required_tools": tool_map[route],
        "required_agents": agents,
        "required_evidence_kinds": sorted(evidence),
    }


def _is_generic(conversation: list[dict[str, str]]) -> bool:
    return any("请核验" in item["text"] and "争议" in item["text"] for item in conversation)


def _formal_conversation(route: str, decision: str, index: int) -> list[dict[str, str]]:
    descriptions = {
        "refund_amount": "退款金额和订单实付金额不一致",
        "duplicate_charge": "同一订单疑似出现重复扣款",
        "payment_order_failure": "银行卡扣款后订单状态异常",
        "merchant_not_shipped": "订单一直没有承运商揽收",
        "delivered_not_received": "物流显示签收但用户没有收到",
        "cancellation_in_transit": "取消申请和物流揽收时间存在争议",
        "return_eligibility": "用户咨询当前商品是否满足退货条件",
        "wrong_item": "收到的商品SKU与订单不一致",
        "missing_item": "实际收到数量少于订单数量",
        "damaged_item": "商品到货后发现破损",
    }
    text = descriptions.get(route, f"请核验{route}状态")
    return [
        {"speaker": "user", "text": f"{text}，这是第{index}种表达。"},
        {"speaker": "agent", "text": f"我正在按{decision}对应证据路径核验。"},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("/tmp/formal-e2e-builder.db"))
    parser.add_argument("--inputs", type=Path, default=ROOT / "data" / "formal_e2e_120_inputs.json")
    parser.add_argument("--oracle", type=Path, default=ROOT / "evals" / "formal_e2e_120_oracle.json")
    args = parser.parse_args()
    print(json.dumps(build_formal_e2e(args.db, args.inputs, args.oracle), ensure_ascii=False))


if __name__ == "__main__":
    main()
