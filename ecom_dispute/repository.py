from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .contracts import CaseInput

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
        allowed = {"orders": "order_id", "after_sales_cases": "order_id"}
        if allowed.get(table) != key:
            raise ValueError("unsupported lookup")
        with self.connect() as connection:
            row = connection.execute(f"SELECT * FROM {table} WHERE {key} = ?", (value,)).fetchone()
            return dict(row) if row else None

    def many(self, table: str, order_id: str) -> list[dict[str, Any]]:
        if table not in {"logistics_events", "payments", "refunds"}:
            raise ValueError("unsupported lookup")
        with self.connect() as connection:
            return _rows(connection.execute(f"SELECT * FROM {table} WHERE order_id = ?", (order_id,)))

    def policy(self, region: str, business_type: str, effective_at: datetime) -> dict[str, Any] | None:
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


def rebuild_database(db_path: Path | str = DEFAULT_DB) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    _seed(connection)
    connection.commit()
    connection.close()
    return path


def _seed(connection: sqlite3.Connection) -> None:
    policy = (
        "refund-cn-standard",
        2,
        "CN",
        "refund",
        "2026-01-01T00:00:00",
        None,
        json.dumps({"initiate_within_hours": 48, "arrival_within_days": 5}, ensure_ascii=False),
        "售后审核通过后 48 小时内应发起退款；退款成功后通常在 5 日内到账。",
    )
    connection.execute("INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", policy)

    cases = [
        {
            "case_id": "refund_missing_001",
            "order_id": "ord-1001",
            "current_time": "2026-01-08T12:00:00",
            "conversation": [
                {"speaker": "user", "text": "客服五天前说退款已经通过，但我一直没收到钱。"},
                {"speaker": "agent", "text": "已为您申请退款，请耐心等待到账。"},
            ],
        },
        {
            "case_id": "refund_pending_001",
            "order_id": "ord-1002",
            "current_time": "2026-01-04T12:00:00",
            "conversation": [
                {"speaker": "user", "text": "昨天退款了，为什么银行卡还没有到账？"},
                {"speaker": "agent", "text": "退款已经发起，到账需要一点时间。"},
            ],
        },
        {
            "case_id": "refund_complete_001",
            "order_id": "ord-1003",
            "current_time": "2026-01-06T12:00:00",
            "conversation": [
                {"speaker": "user", "text": "我想确认退款是否已经完成。"},
                {"speaker": "agent", "text": "我帮您核验退款流水。"},
            ],
        },
        {
            "case_id": "refund_conflict_001",
            "order_id": "ord-1004",
            "current_time": "2026-01-10T12:00:00",
            "conversation": [
                {"speaker": "user", "text": "系统显示退款成功，但银行卡十天了仍未入账。"},
                {"speaker": "agent", "text": "页面显示已退款，请您再核对账单。"},
            ],
        },
    ]
    for index, case in enumerate(cases, start=1):
        occurred = f"2026-01-0{index}T10:00:00"
        connection.execute(
            "INSERT INTO cases VALUES (?, ?, 'CN', 'refund', ?, ?, ?)",
            (
                case["case_id"],
                case["order_id"],
                occurred,
                case["current_time"],
                json.dumps(case["conversation"], ensure_ascii=False),
            ),
        )
        connection.execute(
            "INSERT INTO orders VALUES (?, ?, 'CN', 'refund', 'paid', 199.0, 'CNY', ?, 1)",
            (case["order_id"], f"user-{index}", "2025-12-28T09:00:00"),
        )
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'debit', 199.0, 'succeeded', '2025-12-28T09:01:00', 1)",
            (f"pay-{index}-debit", case["order_id"]),
        )
        connection.execute(
            "INSERT INTO after_sales_cases VALUES (?, ?, 'approved', ?, 'user_return', 1)",
            (f"as-{index}", case["order_id"], occurred),
        )

    connection.execute(
        "INSERT INTO refunds VALUES ('ref-2', 'ord-1002', 199.0, 'processing', '2026-01-03T11:00:00', NULL, 1)"
    )
    connection.execute(
        "INSERT INTO refunds VALUES ('ref-3', 'ord-1003', 199.0, 'succeeded', '2026-01-03T11:00:00', '2026-01-04T08:00:00', 1)"
    )
    connection.execute(
        "INSERT INTO payments VALUES ('pay-3-credit', 'ord-1003', 'credit', 199.0, 'succeeded', '2026-01-05T08:00:00', 1)"
    )
    connection.execute(
        "INSERT INTO refunds VALUES ('ref-4', 'ord-1004', 199.0, 'succeeded', '2026-01-04T11:00:00', '2026-01-05T08:00:00', 1)"
    )

