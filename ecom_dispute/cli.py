from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .e2e_evaluation import evaluate_e2e
from .evaluation import evaluate, evaluate_baseline
from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import DEFAULT_DB, Repository, rebuild_database
from .semantic_holdout import evaluate_holdout
from .web import serve


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecom-dispute")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--base-url", default=os.getenv("ECOM_DISPUTE_BASE_URL"))
    parser.add_argument("--model", default=os.getenv("ECOM_DISPUTE_MODEL", "gpt-5.4-mini"))
    parser.add_argument("--timeout", type=int, default=60)
    commands = parser.add_subparsers(dest="command", required=True)
    data = commands.add_parser("data")
    data.add_argument("action", choices=["rebuild"])
    demo = commands.add_parser("demo")
    demo.add_argument("--case-id", required=True)
    demo.add_argument("--agent-mode", choices=["live-llm", "heuristic-test"], default="live-llm")
    evaluation = commands.add_parser("eval")
    evaluation.add_argument(
        "--mode",
        choices=["deterministic", "llm", "baseline", "compare"],
        default="deterministic",
    )
    evaluation.add_argument("--case-id", action="append", dest="case_ids")
    web = commands.add_parser("web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--agent-mode", choices=["live-llm", "heuristic-test"], default="live-llm")
    holdout = commands.add_parser("holdout")
    holdout.add_argument("--inputs", type=Path, default=Path("data/semantic_holdout_inputs.json"))
    holdout.add_argument("--oracle", type=Path, default=Path("evals/semantic_holdout_oracle.json"))
    holdout.add_argument("--repeats", type=int, default=3)
    holdout.add_argument("--workers", type=int, default=1)
    e2e = commands.add_parser("e2e-eval")
    e2e.add_argument("--inputs", type=Path, default=Path("data/v1_e2e_12route_inputs.json"))
    e2e.add_argument("--oracle", type=Path, default=Path("evals/v1_e2e_12route_oracle.json"))
    e2e.add_argument("--e2e-db", type=Path, default=Path("data/v1_e2e_12route.db"))
    return parser


def _llm_client(args: argparse.Namespace, required: bool = False) -> ResponsesClient | None:
    key = os.getenv("ECOM_DISPUTE_API_KEY")
    if not required and not key:
        return None
    if not key or not args.base_url:
        raise SystemExit("LLM mode requires ECOM_DISPUTE_API_KEY and --base-url")
    return ResponsesClient(args.base_url, key, args.model, args.timeout)


def _build_harness(args: argparse.Namespace, repository: Repository) -> DiagnosticHarness:
    if args.agent_mode == "heuristic-test":
        return DiagnosticHarness.heuristic_tests(repository)
    client = _llm_client(args, required=True)
    return DiagnosticHarness.live(repository, client)


def main() -> None:
    args = _parser().parse_args()
    if args.command == "data":
        print(rebuild_database(args.db))
        return
    if args.command == "holdout":
        client = _llm_client(args, required=True)
        result = evaluate_holdout(client, args.inputs, args.oracle, args.repeats, args.workers)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "e2e-eval":
        client = _llm_client(args, required=True)
        result = evaluate_e2e(client, args.e2e_db, args.inputs, args.oracle)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    repository = Repository(args.db)
    harness = _build_harness(args, repository) if args.command in {"web", "demo"} else None
    if args.command == "web":
        serve(repository, harness, args.agent_mode, args.host, args.port)
    elif args.command == "demo":
        report = harness.diagnose_sync(repository.case(args.case_id))
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
