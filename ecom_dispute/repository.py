from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import CaseInput, DecisionReport, ReviewTask

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "ecom_dispute.db"
SCHEMA = ROOT / "data" / "schema.sql"


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


class Repository:
    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def one(self, table: str, key: str, value: str) -> dict[str, Any] | None:
        allowed = {
            "orders": "order_id",
            "after_sales_cases": "order_id",
            "delivery_proofs": "order_id",
            "delivery_addresses": "order_id",
            "cancellation_requests": "order_id",
        }
        if allowed.get(table) != key:
            raise ValueError("unsupported lookup")
        with self.connect() as connection:
            row = connection.execute(f"SELECT * FROM {table} WHERE {key} = ?", (value,)).fetchone()
            return dict(row) if row else None

    def many(self, table: str, order_id: str) -> list[dict[str, Any]]:
        if table not in {
            "logistics_events",
            "payments",
            "refunds",
            "payment_gateway_events",
            "order_items",
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
        }:
            raise ValueError("unsupported lookup")
        with self.connect() as connection:
            return _rows(
                connection.execute(f"SELECT * FROM {table} WHERE order_id = ?", (order_id,))
            )

    def policy(
        self, region: str, business_type: str, effective_at: datetime
    ) -> dict[str, Any] | None:
        at = effective_at.isoformat()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM policies
                WHERE region = ? AND business_type = ?
                  AND effective_from <= ?
                  AND (effective_to IS NULL OR effective_to > ?)
                ORDER BY version DESC LIMIT 1
                """,
                (region, business_type, at, at),
            ).fetchone()
            return dict(row) if row else None

    def case(self, case_id: str) -> CaseInput:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not row:
            raise KeyError(f"case not found: {case_id}")
        data = dict(row)
        data["conversation"] = json.loads(data.pop("conversation_json"))
        return CaseInput.model_validate(data)

    def case_ids(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT case_id FROM cases ORDER BY case_id").fetchall()
        return [row[0] for row in rows]

    def ensure_review_task(self, report: DecisionReport) -> ReviewTask:
        evidence_ids = sorted(
            {
                evidence_id
                for finding in report.findings
                if finding.review_recommended
                or finding.category in {"fact_conflict", "conversation_fact_conflict"}
                for evidence_id in finding.evidence_ids
            }
        )
        reasons = report.conflicts + [f"缺失证据: {item}" for item in report.missing_evidence]
        reason = "；".join(reasons) or "裁决策略要求人工复检"
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO review_tasks VALUES (?, ?, ?, ?, 'pending', ?, ?, NULL, NULL, NULL, ?, NULL)
                """,
                (
                    f"review:{report.case_id}",
                    report.case_id,
                    reason,
                    json.dumps(evidence_ids, ensure_ascii=False),
                    report.decision,
                    report.responsible_party,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE review_tasks
                SET reason = ?, conflict_evidence_json = ?, system_decision = ?,
                    system_responsible_party = ?
                WHERE case_id = ? AND status = 'pending'
                """,
                (
                    reason,
                    json.dumps(evidence_ids, ensure_ascii=False),
                    report.decision,
                    report.responsible_party,
                    report.case_id,
                ),
            )
        task = self.review_task(report.case_id)
        if not task:
            raise RuntimeError(f"failed to create review task for {report.case_id}")
        return task

    def review_task(self, case_id: str) -> ReviewTask | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_tasks WHERE case_id = ?", (case_id,)
            ).fetchone()
        return self._review_task(dict(row)) if row else None

    def review_tasks(self, status: str | None = None) -> list[ReviewTask]:
        with self.connect() as connection:
            if status:
                rows = connection.execute(
                    "SELECT * FROM review_tasks WHERE status = ? ORDER BY created_at", (status,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM review_tasks ORDER BY created_at"
                ).fetchall()
        return [self._review_task(dict(row)) for row in rows]

    def resolve_review(
        self,
        case_id: str,
        decision: str,
        responsible_party: str,
        comment: str,
    ) -> ReviewTask:
        if not decision or not responsible_party:
            raise ValueError("decision and responsible_party are required")
        resolved_at = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE review_tasks
                SET status = 'resolved', reviewer_decision = ?, reviewer_responsible_party = ?,
                    reviewer_comment = ?, resolved_at = ?
                WHERE case_id = ? AND status = 'pending'
                """,
                (decision, responsible_party, comment, resolved_at, case_id),
            )
        if cursor.rowcount != 1:
            raise ValueError(f"pending review task not found: {case_id}")
        task = self.review_task(case_id)
        if not task:
            raise RuntimeError(f"resolved review task missing: {case_id}")
        return task

    @staticmethod
    def _review_task(row: dict[str, Any]) -> ReviewTask:
        row["conflict_evidence_ids"] = json.loads(row.pop("conflict_evidence_json"))
        return ReviewTask.model_validate(row)


def rebuild_database(db_path: Path | str = DEFAULT_DB) -> Path:
    return initialize_database(db_path, seed=True)


def initialize_database(db_path: Path | str, *, seed: bool) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    if seed:
        _seed(connection)
    connection.commit()
    connection.close()
    return path


def _seed(connection: sqlite3.Connection) -> None:
    from .seed_v3 import seed_v3

    seed_v3(connection)
