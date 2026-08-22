from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .evaluation import evaluate, evaluate_baseline
from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import DEFAULT_DB, Repository, rebuild_database


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecom-dispute")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--base-url", default=os.getenv("ECOM_DISPUTE_BASE_URL"))
    parser.add_argument("--model", default=os.getenv("ECOM_DISPUTE_MODEL", "gpt-5.4-mini"))
    commands = parser.add_subparsers(dest="command", required=True)
    data = commands.add_parser("data")
    data.add_argument("action", choices=["rebuild"])
    demo = commands.add_parser("demo")
    demo.add_argument("--case-id", required=True)
    evaluation = commands.add_parser("eval")
    evaluation.add_argument(
        "--mode", choices=["offline", "llm", "baseline", "compare"], default="offline"
    )
    evaluation.add_argument("--case-id", action="append", dest="case_ids")
    return parser


def _llm_client(args: argparse.Namespace, required: bool = False) -> ResponsesClient | None:
    key = os.getenv("ECOM_DISPUTE_API_KEY")
    if not required and not key:
        return None
    if not key or not args.base_url:
        raise SystemExit("LLM mode requires ECOM_DISPUTE_API_KEY and --base-url")
    return ResponsesClient(args.base_url, key, args.model)


def main() -> None:
    args = _parser().parse_args()
    if args.command == "data":
        print(rebuild_database(args.db))
        return
    repository = Repository(args.db)
    if args.command == "demo":
        client = _llm_client(args)
        report = DiagnosticHarness(repository, llm_client=client).diagnose_sync(
            repository.case(args.case_id)
        )
        print(report.model_dump_json(indent=2))
    elif args.command == "eval":
        client = _llm_client(args, required=args.mode in {"llm", "baseline", "compare"})
        if args.mode == "baseline":
            result = evaluate_baseline(repository, client, case_ids=args.case_ids)
        elif args.mode == "compare":
            result = {
                "hybrid": evaluate(repository, llm_client=client, case_ids=args.case_ids),
                "baseline": evaluate_baseline(repository, client, case_ids=args.case_ids),
            }
        else:
            result = evaluate(repository, llm_client=client, case_ids=args.case_ids)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
