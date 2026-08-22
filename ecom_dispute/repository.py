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
    policies = [
        (
            "refund-cn-standard",
            1,
            "CN",
            "refund",
            "2025-01-01T00:00:00",
            "2026-01-01T00:00:00",
            json.dumps({"initiate_within_hours": 72, "arrival_within_days": 7}, ensure_ascii=False),
            "旧版政策：审核通过后 72 小时内发起退款，退款后通常在 7 日内到账。",
        ),
        (
            "refund-cn-standard",
            2,
            "CN",
            "refund",
            "2026-01-01T00:00:00",
            None,
            json.dumps({"initiate_within_hours": 48, "arrival_within_days": 5}, ensure_ascii=False),
            "现行政策：审核通过后 48 小时内发起退款，退款后通常在 5 日内到账。",
        ),
    ]
    connection.executemany("INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", policies)

    specs = [
        _case("refund_complete_001", "manual", "2026-01-03T10:00:00", "2026-01-06T12:00:00", "我想确认退款是否已经完成。", "我帮您核验退款流水。", refund="succeeded", credit="succeeded"),
        _case("refund_complete_002", "manual", "2026-01-04T09:00:00", "2026-01-08T12:00:00", "钱好像退回来了，麻烦看下是不是这单。", "系统显示已经原路退回。", refund="succeeded", credit="succeeded"),
        _case("refund_complete_003", "rule_generated", "2026-01-05T10:00:00", "2026-01-09T12:00:00", "退款状态查询。", "正在查询。", refund="succeeded", credit="succeeded"),
        _case("refund_conflict_001", "manual", "2026-01-04T10:00:00", "2026-01-10T12:00:00", "系统显示退款成功，但银行卡一直没入账。", "页面显示已退款，请再核对账单。", refund="succeeded"),
        _case("refund_conflict_002", "manual", "2026-01-05T10:00:00", "2026-01-11T12:00:00", "只到账九十九，订单明明是一百九十九。", "后台退款已经完成。", refund="succeeded", credit="succeeded", credit_amount=99.0),
        _case("refund_conflict_003", "rule_generated", "2026-01-06T10:00:00", "2026-01-12T12:00:00", "退款成功为何没有到账？", "请核对支付账户。", refund="succeeded", credit="failed"),
        _case("refund_conflict_004", "rule_generated", "2026-01-07T10:00:00", "2026-01-14T12:00:00", "退款页面与银行卡记录不一致。", "退款页面状态为成功。", refund="succeeded"),
        _case("refund_missing_001", "manual", "2026-01-02T10:00:00", "2026-01-08T12:00:00", "客服五天前说退款已经通过，但一直没收到。", "已为您申请退款，请耐心等待。"),
        _case("refund_missing_002", "manual", "2026-01-03T08:00:00", "2026-01-06T12:00:00", "审核通过三天了，怎么连退款记录都没有？", "退款会尽快处理。"),
        _case("refund_missing_003", "rule_generated", "2026-01-04T08:00:00", "2026-01-14T12:00:00", "退款申请超时未处理。", "请继续等待。"),
        _case("refund_missing_004", "rule_generated", "2026-01-05T08:00:00", "2026-01-08T12:00:00", "售后通过后没有退款流水。", "已记录您的问题。"),
        _case("refund_pending_001", "manual", "2026-01-03T10:00:00", "2026-01-04T12:00:00", "昨天退款了，为什么银行卡还没到账？", "退款已经发起，到账需要一点时间。", refund="processing"),
        _case("refund_pending_002", "manual", "2026-01-04T10:00:00", "2026-01-06T09:00:00", "前天点了退款，现在还是处理中。", "支付渠道正在处理。", refund="processing"),
        _case("refund_pending_003", "rule_generated", "2026-01-05T10:00:00", "2026-01-09T20:00:00", "退款四天仍在处理中。", "预计五天内到账。", refund="processing"),
        _case("refund_overdue_001", "manual", "2026-01-02T10:00:00", "2026-01-09T12:00:00", "退款发起六天多了还没有结果。", "系统仍显示处理中。", refund="processing", refund_at="2026-01-03T10:00:00"),
        _case("refund_overdue_002", "rule_generated", "2026-01-03T10:00:00", "2026-01-13T12:00:00", "退款处理超过政策时限。", "正在联系支付渠道。", refund="processing", refund_at="2026-01-04T10:00:00"),
        _case("refund_within_001", "manual", "2026-01-07T10:00:00", "2026-01-08T10:00:00", "售后刚通过一天，退款怎么还没发起？", "会在规定时间内处理。"),
        _case("refund_within_002", "rule_generated", "2026-01-08T10:00:00", "2026-01-10T09:00:00", "审核通过四十七小时尚无退款记录。", "正在排队处理。"),
        _case("refund_missing_evidence_001", "rule_generated", "2026-01-05T10:00:00", "2026-01-12T12:00:00", "我申请过退款但系统查不到售后单。", "需要进一步核验。", after_sales=False),
        _case("refund_historical_policy_001", "rule_generated", "2025-12-30T10:00:00", "2026-01-01T12:00:00", "两天前审核通过，退款还没发起。", "请按申请时的政策等待。"),
        _case("refund_complete_004", "manual", "2026-02-01T09:00:00", "2026-02-05T12:00:00", "卡里收到一百九十九了，是这笔退款吗？", "我先核对订单和退款流水。", refund="succeeded", credit="succeeded", extra_messages=[{"speaker": "user", "text": "页面也显示退款成功。"}, {"speaker": "agent", "text": "确认已经原路退回。"}]),
        _case("refund_complete_005", "manual", "2026-02-02T09:00:00", "2026-02-06T12:00:00", "帮我查下这单退款进度。", "退款已经完成。", refund="succeeded", credit="succeeded", extra_messages=[{"speaker": "user", "text": "我看到账单了，确实到账。"}]),
        _case("refund_complete_006", "rule_generated", "2026-02-03T09:00:00", "2026-02-07T12:00:00", "退款已到账。", "系统确认退款成功。", refund="succeeded", credit="succeeded"),
        _case("refund_complete_007", "rule_generated", "2026-02-04T09:00:00", "2026-02-08T12:00:00", "核验退款状态。", "正在查询。", refund="succeeded", credit="succeeded", extra_messages=[{"speaker": "agent", "text": "查询结果为退款已完成。"}]),
        _case("refund_conflict_005", "manual", "2026-02-05T09:00:00", "2026-02-12T12:00:00", "我没有收到退款，银行流水也没有。", "系统显示退款已经完成。", refund="succeeded", extra_messages=[{"speaker": "user", "text": "不是延迟一天，已经一周了。"}]),
        _case("refund_conflict_006", "manual", "2026-02-06T09:00:00", "2026-02-13T12:00:00", "退款状态成功，但入账流水是失败的。", "页面显示已经退款。", refund="succeeded", credit="failed"),
        _case("refund_missing_005", "manual", "2026-02-01T10:00:00", "2026-02-05T12:00:00", "售后通过四天了，还没看到退款记录。", "退款已经发起，请等待到账。", extra_messages=[{"speaker": "user", "text": "可是订单里完全查不到退款单号。"}]),
        _case("refund_missing_006", "manual", "2026-02-02T10:00:00", "2026-02-07T12:00:00", "钱没回来，退款流水也没有。", "这笔退款已经完成。"),
        _case("refund_missing_007", "rule_generated", "2026-02-03T10:00:00", "2026-02-08T12:00:00", "审核通过后未发起退款。", "请耐心等待处理。"),
        _case("refund_missing_008", "rule_generated", "2026-02-04T10:00:00", "2026-02-09T12:00:00", "系统没有退款记录。", "退款正在支付渠道处理中。"),
        _case("refund_missing_009", "rule_generated", "2026-02-05T10:00:00", "2026-02-10T12:00:00", "退款超过四十八小时仍未发起。", "我帮您查询退款状态。"),
        _case("refund_pending_004", "manual", "2026-02-06T10:00:00", "2026-02-08T12:00:00", "前天发起退款，现在还在处理中。", "退款正在处理中。", refund="processing"),
        _case("refund_pending_005", "manual", "2026-02-07T10:00:00", "2026-02-10T12:00:00", "页面还是处理中，怎么客服说完成了？", "退款已经完成。", refund="processing"),
        _case("refund_pending_006", "rule_generated", "2026-02-08T10:00:00", "2026-02-12T12:00:00", "退款处理第四天。", "预计五日内到账，请等待。", refund="processing"),
        _case("refund_overdue_003", "manual", "2026-02-01T10:00:00", "2026-02-09T12:00:00", "退款处理中超过六天还没到账。", "支付渠道仍在处理。", refund="processing", refund_at="2026-02-02T10:00:00"),
        _case("refund_overdue_004", "rule_generated", "2026-02-02T10:00:00", "2026-02-12T12:00:00", "退款处理已经九天。", "退款仍处于处理中。", refund="processing", refund_at="2026-02-03T10:00:00"),
        _case("refund_within_003", "manual", "2026-02-10T10:00:00", "2026-02-11T10:00:00", "售后昨天通过，但订单里没有退款记录。", "退款已经发起。"),
        _case("refund_within_004", "rule_generated", "2026-02-11T10:00:00", "2026-02-13T09:00:00", "审核通过四十七小时，退款尚未发起。", "请等待系统处理。"),
        _case("refund_missing_evidence_002", "rule_generated", "2026-02-08T10:00:00", "2026-02-15T12:00:00", "申请退款后找不到售后审核信息。", "我帮您核验申请状态。", after_sales=False, extra_messages=[{"speaker": "user", "text": "订单里也没有退款流水。"}]),
        _case("refund_historical_policy_002", "manual", "2025-12-28T10:00:00", "2025-12-31T08:00:00", "旧政策下审核通过七十小时，还没发起退款。", "按申请时七十二小时政策处理。"),
    ]
    for index, spec in enumerate(specs, start=1):
        _insert_case(connection, index, spec)


def _case(
    case_id: str,
    source_type: str,
    occurred_at: str,
    current_time: str,
    user_text: str,
    agent_text: str,
    *,
    refund: str | None = None,
    refund_at: str | None = None,
    credit: str | None = None,
    credit_amount: float = 199.0,
    after_sales: bool = True,
    extra_messages: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "source_type": source_type,
        "occurred_at": occurred_at,
        "current_time": current_time,
        "conversation": [
            {"speaker": "user", "text": user_text},
            {"speaker": "agent", "text": agent_text},
            *(extra_messages or []),
        ],
        "refund": refund,
        "refund_at": refund_at,
        "credit": credit,
        "credit_amount": credit_amount,
        "after_sales": after_sales,
    }


def _insert_case(connection: sqlite3.Connection, index: int, spec: dict[str, Any]) -> None:
    order_id = f"ord-{1000 + index}"
    connection.execute(
        "INSERT INTO cases VALUES (?, ?, ?, 'CN', 'refund', ?, ?, ?)",
        (
            spec["case_id"],
            order_id,
            spec["source_type"],
            spec["occurred_at"],
            spec["current_time"],
            json.dumps(spec["conversation"], ensure_ascii=False),
        ),
    )
    connection.execute(
        "INSERT INTO orders VALUES (?, ?, 'CN', 'refund', 'paid', 199.0, 'CNY', '2025-12-20T09:00:00', 1)",
        (order_id, f"user-{index}"),
    )
    connection.execute(
        "INSERT INTO payments VALUES (?, ?, 'debit', 199.0, 'succeeded', '2025-12-20T09:01:00', 1)",
        (f"pay-{index}-debit", order_id),
    )
    if spec["after_sales"]:
        connection.execute(
            "INSERT INTO after_sales_cases VALUES (?, ?, 'approved', ?, 'user_return', 1)",
            (f"as-{index}", order_id, spec["occurred_at"]),
        )
    if spec["refund"]:
        initiated_at = spec["refund_at"] or spec["occurred_at"]
        completed_at = initiated_at if spec["refund"] == "succeeded" else None
        connection.execute(
            "INSERT INTO refunds VALUES (?, ?, 199.0, ?, ?, ?, 1)",
            (f"ref-{index}", order_id, spec["refund"], initiated_at, completed_at),
        )
    if spec["credit"]:
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'credit', ?, ?, ?, 1)",
            (
                f"pay-{index}-credit",
                order_id,
                spec["credit_amount"],
                spec["credit"],
                spec["current_time"],
            ),
        )
