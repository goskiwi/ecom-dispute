from __future__ import annotations

import copy
import json
from pathlib import Path

from ecom_dispute.repository import Repository
from ecom_dispute.skills import SkillRegistry, default_strategies
from ecom_dispute.tool_registry import ToolRegistry

ROOT = Path(__file__).resolve().parents[1]

EVIDENCE_FIELDS = {
    "payment": "payments",
    "refund": "refunds",
    "after_sales": "after_sales",
    "cancellation_request": "cancellation_requests",
    "order_item": "order_items",
    "return_request": "return_requests",
    "return_tracking": "return_tracking_events",
    "exchange_request": "exchange_options",
    "warehouse_pack": "warehouse_pack_records",
    "order_fee": "order_fee_records",
    "charge_claim": "charge_dispute_records",
    "order_change_option": "order_change_options",
    "product_catalog": "product_catalog_records",
    "inventory": "inventory_records",
    "price": "price_records",
    "promotion": "promotion_records",
    "shipping_option": "shipping_option_records",
    "membership": "membership_records",
    "checkout_event": "checkout_events",
    "cart_event": "cart_events",
    "search_event": "search_events",
    "site_health": "site_health_events",
}


def main() -> None:
    source = json.loads((ROOT / "data" / "v3_e2e_90_inputs.json").read_text())
    base_cases = {
        item["business_type"]: item for item in source["cases"] if item["case_id"].startswith("v3-")
    }
    repository = Repository(ROOT / "data" / "ecom_dispute.db")
    tools = ToolRegistry(repository)
    skills = SkillRegistry(default_strategies(), known_tools=tools.names)
    cases = []
    oracle = {}
    for business_type in sorted(base_cases):
        resolved = skills.resolve(business_type)
        required = [kind.value for kind in resolved.required_evidence]
        removable = [kind for kind in required if kind in EVIDENCE_FIELDS]
        missing_kind = removable[-1] if removable else "policy"
        case = copy.deepcopy(base_cases[business_type])
        case_id = f"v3f-missing-{business_type}"
        case["case_id"] = case_id
        case["conversation"] = [
            {
                "speaker": "user",
                "text": f"请核验{business_type}，但关键业务记录可能缺失。",
            },
            {"speaker": "agent", "text": "我会查询现有证据并在不足时转人工。"},
        ]
        if missing_kind == "policy":
            case["region"] = "ZZ"
            case["order"]["region"] = "ZZ"
        else:
            field = EVIDENCE_FIELDS[missing_kind]
            case[field] = None if field == "after_sales" else []
        cases.append(case)
        oracle[case_id] = {
            "route_type": business_type,
            "decision": "manual_review",
            "responsible_party": "undetermined",
            "review_required": True,
            "missing_evidence": [missing_kind],
            "required_tools": list(resolved.route.core_tools),
            "action_type": None,
        }
    (ROOT / "data" / "v3_failure_matrix_inputs.json").write_text(
        json.dumps(
            {"source": "v3_missing_required_evidence_matrix", "cases": cases},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    (ROOT / "evals" / "v3_failure_matrix_oracle.json").write_text(
        json.dumps(oracle, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        {
            "cases": len(cases),
            "missing_kinds": sorted({item["missing_evidence"][0] for item in oracle.values()}),
        }
    )


if __name__ == "__main__":
    main()
