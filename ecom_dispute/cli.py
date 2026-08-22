from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .abcd_annotation import (
    agreement_and_consensus,
    build_annotation_forms,
    rescore_first_run,
)
from .abcd_evaluation import build_abcd_manifest, evaluate_abcd
from .annotation_web import serve_annotation
from .e2e_evaluation import evaluate_e2e
from .evaluation import evaluate, evaluate_baseline
from .harness import DiagnosticHarness
from .llm import ResponsesClient
from .repository import DEFAULT_DB, Repository, rebuild_database
from .review_ab_evaluation import build_review_manifest, generate_review_ab
from .review_web import serve_review_form
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
    e2e.add_argument("--workers", type=int, default=1)
    abcd_manifest = commands.add_parser("abcd-manifest")
    abcd_manifest.add_argument("--dataset", type=Path, required=True)
    abcd_manifest.add_argument(
        "--manifest", type=Path, default=Path("evals/formal_abcd_200_manifest.json")
    )
    abcd_eval = commands.add_parser("abcd-eval")
    abcd_eval.add_argument("--dataset", type=Path, required=True)
    abcd_eval.add_argument(
        "--manifest", type=Path, default=Path("evals/formal_abcd_200_manifest.json")
    )
    abcd_eval.add_argument("--workers", type=int, default=4)
    review_manifest = commands.add_parser("review-manifest")
    review_manifest.add_argument(
        "--inputs", type=Path, default=Path("data/formal_e2e_120_inputs.json")
    )
    review_manifest.add_argument(
        "--manifest", type=Path, default=Path("evals/formal_review_40_manifest.json")
    )
    review_manifest.add_argument("--review-db", type=Path, default=Path("/tmp/review-manifest.db"))
    review_ab = commands.add_parser("review-ab")
    review_ab.add_argument(
        "--inputs", type=Path, default=Path("data/formal_e2e_120_inputs.json")
    )
    review_ab.add_argument(
        "--manifest", type=Path, default=Path("evals/formal_review_40_manifest.json")
    )
    review_ab.add_argument(
        "--output", type=Path, default=Path("evals/formal_review_40_blind_form.json")
    )
    review_ab.add_argument(
        "--key", type=Path, default=Path("evals/formal_review_40_ab_key.json")
    )
    review_ab.add_argument("--review-db", type=Path, default=Path("/tmp/review-ab.db"))
    review_ab.add_argument("--workers", type=int, default=4)
    annotation_build = commands.add_parser("abcd-annotation-build")
    annotation_build.add_argument("--dataset", type=Path, required=True)
    annotation_build.add_argument(
        "--manifest", type=Path, default=Path("evals/formal_abcd_200_manifest.json")
    )
    annotation_build.add_argument(
        "--rater1", type=Path, default=Path("evals/formal_abcd_200_rater1.json")
    )
    annotation_build.add_argument(
        "--rater2", type=Path, default=Path("evals/formal_abcd_200_rater2.json")
    )
    annotation_web = commands.add_parser("abcd-annotation-web")
    annotation_web.add_argument("--form", type=Path, required=True)
    annotation_web.add_argument("--host", default="127.0.0.1")
    annotation_web.add_argument("--port", type=int, default=8877)
    annotation_agreement = commands.add_parser("abcd-annotation-agreement")
    annotation_agreement.add_argument(
        "--rater1", type=Path, default=Path("evals/formal_abcd_200_rater1.json")
    )
    annotation_agreement.add_argument(
        "--rater2", type=Path, default=Path("evals/formal_abcd_200_rater2.json")
    )
    annotation_agreement.add_argument(
        "--consensus", type=Path, default=Path("evals/formal_abcd_200_consensus.json")
    )
    annotation_rescore = commands.add_parser("abcd-annotation-rescore")
    annotation_rescore.add_argument(
        "--raw",
        type=Path,
        default=Path("evals/formal_abcd_200_gpt-5.6-luna_run1_raw.json.gz"),
    )
    annotation_rescore.add_argument(
        "--consensus", type=Path, default=Path("evals/formal_abcd_200_consensus.json")
    )
    review_web = commands.add_parser("review-ab-web")
    review_web.add_argument("--form", type=Path, required=True)
    review_web.add_argument("--host", default="127.0.0.1")
    review_web.add_argument("--port", type=int, default=8887)
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
        result = evaluate_e2e(client, args.e2e_db, args.inputs, args.oracle, args.workers)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "abcd-manifest":
        result = build_abcd_manifest(args.dataset, args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=dict))
        return
    if args.command == "abcd-eval":
        client = _llm_client(args, required=True)
        result = evaluate_abcd(client, args.dataset, args.manifest, args.workers)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "review-manifest":
        result = build_review_manifest(args.inputs, args.manifest, args.review_db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "review-ab":
        client = _llm_client(args, required=True)
        result = generate_review_ab(
            client,
            args.inputs,
            args.manifest,
            args.output,
            args.key,
            args.review_db,
            args.workers,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "abcd-annotation-build":
        result = build_annotation_forms(args.dataset, args.manifest, args.rater1, args.rater2)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "abcd-annotation-web":
        serve_annotation(args.form, args.host, args.port)
        return
    if args.command == "abcd-annotation-agreement":
        result = agreement_and_consensus(args.rater1, args.rater2, args.consensus)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "abcd-annotation-rescore":
        result = rescore_first_run(args.raw, args.consensus)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "review-ab-web":
        serve_review_form(args.form, args.host, args.port)
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
