from __future__ import annotations

import asyncio
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .agents import ReviewAgent
from .contracts import CaseState
from .e2e_evaluation import prepare_e2e_database
from .harness import DiagnosticHarness
from .llm import ResponsesClient


def build_review_manifest(
    input_path: Path,
    manifest_path: Path,
    db_path: Path,
) -> dict:
    repository, case_ids = prepare_e2e_database(db_path, input_path)
    candidates = []
    for case_id in case_ids:
        report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(
            repository.case(case_id)
        )
        if not report.review_required:
            continue
        category = _review_category(report)
        candidates.append({"case_id": case_id, "category": category})
    selected = []
    for category in ("conflict", "missing", "compliance", "strategy"):
        for item in candidates:
            if item["category"] == category and item not in selected:
                selected.append(item)
                if len(selected) == 40:
                    break
        if len(selected) == 40:
            break
    if len(selected) != 40:
        raise ValueError(f"review manifest requires 40 cases, found {len(selected)}")
    payload = {
        "source": "formal_e2e_120_pre_review_agent",
        "rubric": {
            "evidence_correctness": "1-5",
            "conflict_coverage": "1-5",
            "question_actionability": "1-5",
            "irrelevant_content": "1-5 (5 means no irrelevant content)",
            "overall_preference": "A | B | tie",
        },
        "items": selected,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for item in selected:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {"case_count": 40, "categories": counts}


def generate_review_ab(
    client: ResponsesClient,
    input_path: Path,
    manifest_path: Path,
    output_path: Path,
    key_path: Path,
    db_path: Path,
    workers: int = 4,
) -> dict:
    repository, _ = prepare_e2e_database(db_path, input_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def run_one(item: dict) -> dict:
        case = repository.case(item["case_id"])
        report = DiagnosticHarness.heuristic_tests(repository).diagnose_sync(case)
        fixed = _fixed_review(report)
        state = CaseState(
            case_id=case.case_id,
            findings=report.findings,
            evidence={entry.evidence_id: entry for entry in report.evidence},
            conflicts=report.conflicts,
            missing_evidence=report.missing_evidence,
        )
        try:
            generated = asyncio.run(ReviewAgent(client).run(case, state))
        except (RuntimeError, ValueError) as exc:
            return {**item, "error": str(exc)}
        llm = {
            "summary": generated.findings[0].claim,
            "evidence_ids": generated.findings[0].evidence_ids,
            "questions": generated.telemetry["review_questions"],
            "recommended_action": generated.telemetry["recommended_action"],
            "priority": generated.telemetry["priority"],
        }
        return {**item, "fixed": fixed, "llm": llm, "telemetry": generated.telemetry}

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_one, item): item for item in manifest["items"]}
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda item: item["case_id"])

    rng = random.Random(20260823)
    forms = []
    key = {}
    for index, row in enumerate(rows, start=1):
        if "error" in row:
            forms.append({"review_id": f"review-{index:02d}", **row})
            continue
        llm_is_a = bool(rng.getrandbits(1))
        option_a = row["llm"] if llm_is_a else row["fixed"]
        option_b = row["fixed"] if llm_is_a else row["llm"]
        review_id = f"review-{index:02d}"
        forms.append(
            {
                "review_id": review_id,
                "category": row["category"],
                "option_a": option_a,
                "option_b": option_b,
                "ratings": {
                    "option_a": _blank_rating(),
                    "option_b": _blank_rating(),
                    "overall_preference": None,
                    "comment": None,
                },
            }
        )
        key[review_id] = {"A": "review_agent" if llm_is_a else "fixed_template"}
        key[review_id]["B"] = "fixed_template" if llm_is_a else "review_agent"
    output_path.write_text(
        json.dumps({"rubric": manifest["rubric"], "items": forms}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "case_count": len(rows),
        "api_errors": sum("error" in item for item in rows),
        "input_tokens": sum(item.get("telemetry", {}).get("input_tokens", 0) for item in rows),
        "output_tokens": sum(item.get("telemetry", {}).get("output_tokens", 0) for item in rows),
        "latency_ms": sum(item.get("telemetry", {}).get("latency_ms", 0) for item in rows),
    }


def _review_category(report: object) -> str:
    if report.conflicts:
        return "conflict"
    if report.missing_evidence:
        return "missing"
    if any(
        finding.category == "service_compliance" and finding.review_recommended
        for finding in report.findings
    ):
        return "compliance"
    return "strategy"


def _fixed_review(report: object) -> dict:
    reasons = list(report.conflicts) or [
        f"缺失证据：{item}" for item in report.missing_evidence
    ]
    if not reasons:
        reasons = [
            finding.claim
            for finding in report.findings
            if finding.category == "service_compliance" and finding.review_recommended
        ]
    return {
        "summary": "；".join(reasons) or "策略要求人工复检",
        "evidence_ids": report.evidence_ids[:10],
        "questions": ["请核验冲突证据和缺失业务记录后确认系统结论。"],
        "recommended_action": report.recommended_action,
        "priority": "high" if report.conflicts else "normal",
    }


def _blank_rating() -> dict:
    return {
        "evidence_correctness": None,
        "conflict_coverage": None,
        "question_actionability": None,
        "irrelevant_content": None,
    }
