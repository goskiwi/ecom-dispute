from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def rescore_semantic_run(raw_path: Path, semantic_oracle_path: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    oracle = json.loads(semantic_oracle_path.read_text(encoding="utf-8"))
    results = []
    for original in raw["results"]:
        case_id = original["case_id"]
        expected = oracle[case_id]
        observed = original["semantics"]
        user_types = set(observed["observed_user_types"])
        agent_types = set(observed["observed_agent_types"])
        checks = {
            name: original["checks"][name]
            for name in ("decision", "responsible_party", "review_required")
        }
        if "business_type" in original["llm"]:
            checks["business_type"] = original["llm"]["business_type"] == expected["business_type"]
            checks["has_dispute"] = original["llm"]["has_dispute"] == expected["has_dispute"]
        else:
            checks["semantic_route"] = original["llm"].get("dispute_type") == "refund_dispute"
        checks.update(
            {
                "user_claim_types": set(expected["required_user_types"]).issubset(user_types),
                "agent_commitment_types": set(expected["required_agent_types"]).issubset(
                    agent_types
                ),
                "conversation_conflict": (
                    observed["conversation_conflict"] == expected["conversation_conflict"]
                ),
            }
        )
        results.append(
            {
                "case_id": case_id,
                "source_type": original["source_type"],
                "checks": checks,
                "passed": all(checks.values()),
                "semantics": observed,
                "llm": original["llm"],
            }
        )

    expected_user = sum(len(oracle[item["case_id"]]["required_user_types"]) for item in results)
    matched_user = sum(
        len(
            set(oracle[item["case_id"]]["required_user_types"])
            & set(item["semantics"]["observed_user_types"])
        )
        for item in results
    )
    expected_agent = sum(len(oracle[item["case_id"]]["required_agent_types"]) for item in results)
    matched_agent = sum(
        len(
            set(oracle[item["case_id"]]["required_agent_types"])
            & set(item["semantics"]["observed_agent_types"])
        )
        for item in results
    )
    conflict_tp = sum(
        oracle[item["case_id"]]["conversation_conflict"]
        and item["semantics"]["conversation_conflict"]
        for item in results
    )
    conflict_fp = sum(
        not oracle[item["case_id"]]["conversation_conflict"]
        and item["semantics"]["conversation_conflict"]
        for item in results
    )
    conflict_fn = sum(
        oracle[item["case_id"]]["conversation_conflict"]
        and not item["semantics"]["conversation_conflict"]
        for item in results
    )
    business_type_checks = [
        item["checks"]["business_type"] for item in results if "business_type" in item["checks"]
    ]
    has_dispute_checks = [
        item["checks"]["has_dispute"] for item in results if "has_dispute" in item["checks"]
    ]
    return {
        "source_run": raw_path.name,
        "scoring": "audited_semantic_oracle",
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "pass_rate": sum(item["passed"] for item in results) / len(results),
        "llm_calls": raw["llm_calls"],
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
        "latency_ms": raw["latency_ms"],
        "semantic_metrics": {
            "business_type_accuracy": (
                sum(business_type_checks) / len(business_type_checks)
                if business_type_checks
                else None
            ),
            "has_dispute_accuracy": (
                sum(has_dispute_checks) / len(has_dispute_checks) if has_dispute_checks else None
            ),
            "user_type_recall": matched_user / expected_user,
            "agent_type_recall": matched_agent / expected_agent,
            "conversation_conflict_precision": (
                conflict_tp / (conflict_tp + conflict_fp) if conflict_tp + conflict_fp else 1.0
            ),
            "conversation_conflict_recall": (
                conflict_tp / (conflict_tp + conflict_fn) if conflict_tp + conflict_fn else 1.0
            ),
            "conflict_tp": conflict_tp,
            "conflict_fp": conflict_fp,
            "conflict_fn": conflict_fn,
        },
        "results": results,
    }
