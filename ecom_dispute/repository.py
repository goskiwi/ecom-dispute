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
M6_CASES = ROOT / "data" / "cases" / "m6_cases.json"
M10_ITEM_MATRIX = ROOT / "data" / "cases" / "m10_item_matrix.json"


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
        (
            "delivery-cn-standard",
            1,
            "CN",
            "delivery",
            "2025-01-01T00:00:00",
            None,
            json.dumps(
                {"merchant_ship_hours": 48, "delivery_grace_hours": 24},
                ensure_ascii=False,
            ),
            "商家应在下单后 48 小时内交运；承诺送达后有 24 小时物流宽限期。",
        ),
        (
            "refund-amount-cn-standard",
            1,
            "CN",
            "refund_amount",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"expected_amount_source": "order_paid_amount"}, ensure_ascii=False),
            "退款金额应以订单实付金额和售后审核结果为准。",
        ),
        (
            "duplicate-charge-cn-standard",
            1,
            "CN",
            "duplicate_charge",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"pending_authorization_hours": 72}, ensure_ascii=False),
            "同一订单仅允许一笔成功扣款；待处理预授权通常在 72 小时内释放。",
        ),
        (
            "payment-order-failure-cn-standard",
            1,
            "CN",
            "payment_order_failure",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"reverse_within_hours": 24}, ensure_ascii=False),
            "订单创建失败后，已扣资金应在 24 小时内撤销或发起退款。",
        ),
        (
            "merchant-ship-cn-standard",
            1,
            "CN",
            "merchant_not_shipped",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"merchant_ship_hours": 48}, ensure_ascii=False),
            "商家应在下单后 48 小时内完成承运商揽收。",
        ),
        (
            "delivered-receipt-cn-standard",
            1,
            "CN",
            "delivered_not_received",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"proof_required": True}, ensure_ascii=False),
            "用户否认收货时，承运商应提供可核验签收证明。",
        ),
        (
            "cancellation-transit-cn-standard",
            1,
            "CN",
            "cancellation_in_transit",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"refund_within_hours": 48}, ensure_ascii=False),
            "取消申请与揽收时间决定拦截、拒收或退回路径，受理后应在 48 小时内发起退款。",
        ),
        (
            "return-eligibility-cn-standard",
            1,
            "CN",
            "return_eligibility",
            "2025-01-01T00:00:00",
            None,
            json.dumps(
                {"return_window_days": 7, "excluded_categories": ["personal_care"]},
                ensure_ascii=False,
            ),
            "普通商品支持七日退货，个人护理等特殊品类除外。",
        ),
        (
            "wrong-item-cn-standard",
            1,
            "CN",
            "wrong_item",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"warehouse_record_required": True}, ensure_ascii=False),
            "错件争议需核对订单商品、仓库扫描和用户附件。",
        ),
        (
            "missing-item-cn-standard",
            1,
            "CN",
            "missing_item",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"warehouse_quantity_required": True}, ensure_ascii=False),
            "少件争议需核对订单数量和仓库打包数量。",
        ),
        (
            "damaged-item-cn-standard",
            1,
            "CN",
            "damaged_item",
            "2025-01-01T00:00:00",
            None,
            json.dumps({"attachment_required": True}, ensure_ascii=False),
            "破损争议应收集商品、外包装和物流相关凭证。",
        ),
        (
            "service-compliance-cn-standard",
            1,
            "CN",
            "service_compliance",
            "2025-01-01T00:00:00",
            None,
            json.dumps(
                {
                    "fact_statements_must_be_grounded": True,
                    "unsupported_promises_forbidden": True,
                    "conflict_requires_escalation": True,
                },
                ensure_ascii=False,
            ),
            "客服业务陈述必须有事实依据；不支持无依据承诺；冲突案件必须升级复检。",
        ),
    ]
    connection.executemany("INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", policies)

    specs = [
        _case(
            "refund_complete_001",
            "manual",
            "2026-01-03T10:00:00",
            "2026-01-06T12:00:00",
            "我想确认退款是否已经完成。",
            "我帮您核验退款流水。",
            refund="succeeded",
            credit="succeeded",
        ),
        _case(
            "refund_complete_002",
            "manual",
            "2026-01-04T09:00:00",
            "2026-01-08T12:00:00",
            "钱好像退回来了，麻烦看下是不是这单。",
            "系统显示已经原路退回。",
            refund="succeeded",
            credit="succeeded",
        ),
        _case(
            "refund_complete_003",
            "rule_generated",
            "2026-01-05T10:00:00",
            "2026-01-09T12:00:00",
            "退款状态查询。",
            "正在查询。",
            refund="succeeded",
            credit="succeeded",
        ),
        _case(
            "refund_conflict_001",
            "manual",
            "2026-01-04T10:00:00",
            "2026-01-10T12:00:00",
            "系统显示退款成功，但银行卡一直没入账。",
            "页面显示已退款，请再核对账单。",
            refund="succeeded",
        ),
        _case(
            "refund_conflict_002",
            "manual",
            "2026-01-05T10:00:00",
            "2026-01-11T12:00:00",
            "只到账九十九，订单明明是一百九十九。",
            "后台退款已经完成。",
            refund="succeeded",
            credit="succeeded",
            credit_amount=99.0,
        ),
        _case(
            "refund_conflict_003",
            "rule_generated",
            "2026-01-06T10:00:00",
            "2026-01-12T12:00:00",
            "退款成功为何没有到账？",
            "请核对支付账户。",
            refund="succeeded",
            credit="failed",
        ),
        _case(
            "refund_conflict_004",
            "rule_generated",
            "2026-01-07T10:00:00",
            "2026-01-14T12:00:00",
            "退款页面与银行卡记录不一致。",
            "退款页面状态为成功。",
            refund="succeeded",
        ),
        _case(
            "refund_missing_001",
            "manual",
            "2026-01-02T10:00:00",
            "2026-01-08T12:00:00",
            "客服五天前说退款已经通过，但一直没收到。",
            "已为您申请退款，请耐心等待。",
        ),
        _case(
            "refund_missing_002",
            "manual",
            "2026-01-03T08:00:00",
            "2026-01-06T12:00:00",
            "审核通过三天了，怎么连退款记录都没有？",
            "退款会尽快处理。",
        ),
        _case(
            "refund_missing_003",
            "rule_generated",
            "2026-01-04T08:00:00",
            "2026-01-14T12:00:00",
            "退款申请超时未处理。",
            "请继续等待。",
        ),
        _case(
            "refund_missing_004",
            "rule_generated",
            "2026-01-05T08:00:00",
            "2026-01-08T12:00:00",
            "售后通过后没有退款流水。",
            "已记录您的问题。",
        ),
        _case(
            "refund_pending_001",
            "manual",
            "2026-01-03T10:00:00",
            "2026-01-04T12:00:00",
            "昨天退款了，为什么银行卡还没到账？",
            "退款已经发起，到账需要一点时间。",
            refund="processing",
        ),
        _case(
            "refund_pending_002",
            "manual",
            "2026-01-04T10:00:00",
            "2026-01-06T09:00:00",
            "前天点了退款，现在还是处理中。",
            "支付渠道正在处理。",
            refund="processing",
        ),
        _case(
            "refund_pending_003",
            "rule_generated",
            "2026-01-05T10:00:00",
            "2026-01-09T20:00:00",
            "退款四天仍在处理中。",
            "预计五天内到账。",
            refund="processing",
        ),
        _case(
            "refund_overdue_001",
            "manual",
            "2026-01-02T10:00:00",
            "2026-01-09T12:00:00",
            "退款发起六天多了还没有结果。",
            "系统仍显示处理中。",
            refund="processing",
            refund_at="2026-01-03T10:00:00",
        ),
        _case(
            "refund_overdue_002",
            "rule_generated",
            "2026-01-03T10:00:00",
            "2026-01-13T12:00:00",
            "退款处理超过政策时限。",
            "正在联系支付渠道。",
            refund="processing",
            refund_at="2026-01-04T10:00:00",
        ),
        _case(
            "refund_within_001",
            "manual",
            "2026-01-07T10:00:00",
            "2026-01-08T10:00:00",
            "售后刚通过一天，退款怎么还没发起？",
            "会在规定时间内处理。",
        ),
        _case(
            "refund_within_002",
            "rule_generated",
            "2026-01-08T10:00:00",
            "2026-01-10T09:00:00",
            "审核通过四十七小时尚无退款记录。",
            "正在排队处理。",
        ),
        _case(
            "refund_missing_evidence_001",
            "rule_generated",
            "2026-01-05T10:00:00",
            "2026-01-12T12:00:00",
            "我申请过退款但系统查不到售后单。",
            "需要进一步核验。",
            after_sales=False,
        ),
        _case(
            "refund_historical_policy_001",
            "rule_generated",
            "2025-12-30T10:00:00",
            "2026-01-01T12:00:00",
            "两天前审核通过，退款还没发起。",
            "请按申请时的政策等待。",
        ),
        _case(
            "refund_complete_004",
            "manual",
            "2026-02-01T09:00:00",
            "2026-02-05T12:00:00",
            "卡里收到一百九十九了，是这笔退款吗？",
            "我先核对订单和退款流水。",
            refund="succeeded",
            credit="succeeded",
            extra_messages=[
                {"speaker": "user", "text": "页面也显示退款成功。"},
                {"speaker": "agent", "text": "确认已经原路退回。"},
            ],
        ),
        _case(
            "refund_complete_005",
            "manual",
            "2026-02-02T09:00:00",
            "2026-02-06T12:00:00",
            "帮我查下这单退款进度。",
            "退款已经完成。",
            refund="succeeded",
            credit="succeeded",
            extra_messages=[{"speaker": "user", "text": "我看到账单了，确实到账。"}],
        ),
        _case(
            "refund_complete_006",
            "rule_generated",
            "2026-02-03T09:00:00",
            "2026-02-07T12:00:00",
            "退款已到账。",
            "系统确认退款成功。",
            refund="succeeded",
            credit="succeeded",
        ),
        _case(
            "refund_complete_007",
            "rule_generated",
            "2026-02-04T09:00:00",
            "2026-02-08T12:00:00",
            "核验退款状态。",
            "正在查询。",
            refund="succeeded",
            credit="succeeded",
            extra_messages=[{"speaker": "agent", "text": "查询结果为退款已完成。"}],
        ),
        _case(
            "refund_conflict_005",
            "manual",
            "2026-02-05T09:00:00",
            "2026-02-12T12:00:00",
            "我没有收到退款，银行流水也没有。",
            "系统显示退款已经完成。",
            refund="succeeded",
            extra_messages=[{"speaker": "user", "text": "不是延迟一天，已经一周了。"}],
        ),
        _case(
            "refund_conflict_006",
            "manual",
            "2026-02-06T09:00:00",
            "2026-02-13T12:00:00",
            "退款状态成功，但入账流水是失败的。",
            "页面显示已经退款。",
            refund="succeeded",
            credit="failed",
        ),
        _case(
            "refund_missing_005",
            "manual",
            "2026-02-01T10:00:00",
            "2026-02-05T12:00:00",
            "售后通过四天了，还没看到退款记录。",
            "退款已经发起，请等待到账。",
            extra_messages=[{"speaker": "user", "text": "可是订单里完全查不到退款单号。"}],
        ),
        _case(
            "refund_missing_006",
            "manual",
            "2026-02-02T10:00:00",
            "2026-02-07T12:00:00",
            "钱没回来，退款流水也没有。",
            "这笔退款已经完成。",
        ),
        _case(
            "refund_missing_007",
            "rule_generated",
            "2026-02-03T10:00:00",
            "2026-02-08T12:00:00",
            "审核通过后未发起退款。",
            "请耐心等待处理。",
        ),
        _case(
            "refund_missing_008",
            "rule_generated",
            "2026-02-04T10:00:00",
            "2026-02-09T12:00:00",
            "系统没有退款记录。",
            "退款正在支付渠道处理中。",
        ),
        _case(
            "refund_missing_009",
            "rule_generated",
            "2026-02-05T10:00:00",
            "2026-02-10T12:00:00",
            "退款超过四十八小时仍未发起。",
            "我帮您查询退款状态。",
        ),
        _case(
            "refund_pending_004",
            "manual",
            "2026-02-06T10:00:00",
            "2026-02-08T12:00:00",
            "前天发起退款，现在还在处理中。",
            "退款正在处理中。",
            refund="processing",
        ),
        _case(
            "refund_pending_005",
            "manual",
            "2026-02-07T10:00:00",
            "2026-02-10T12:00:00",
            "页面还是处理中，怎么客服说完成了？",
            "退款已经完成。",
            refund="processing",
        ),
        _case(
            "refund_pending_006",
            "rule_generated",
            "2026-02-08T10:00:00",
            "2026-02-12T12:00:00",
            "退款处理第四天。",
            "预计五日内到账，请等待。",
            refund="processing",
        ),
        _case(
            "refund_overdue_003",
            "manual",
            "2026-02-01T10:00:00",
            "2026-02-09T12:00:00",
            "退款处理中超过六天还没到账。",
            "支付渠道仍在处理。",
            refund="processing",
            refund_at="2026-02-02T10:00:00",
        ),
        _case(
            "refund_overdue_004",
            "rule_generated",
            "2026-02-02T10:00:00",
            "2026-02-12T12:00:00",
            "退款处理已经九天。",
            "退款仍处于处理中。",
            refund="processing",
            refund_at="2026-02-03T10:00:00",
        ),
        _case(
            "refund_within_003",
            "manual",
            "2026-02-10T10:00:00",
            "2026-02-11T10:00:00",
            "售后昨天通过，但订单里没有退款记录。",
            "退款已经发起。",
        ),
        _case(
            "refund_within_004",
            "rule_generated",
            "2026-02-11T10:00:00",
            "2026-02-13T09:00:00",
            "审核通过四十七小时，退款尚未发起。",
            "请等待系统处理。",
        ),
        _case(
            "refund_missing_evidence_002",
            "rule_generated",
            "2026-02-08T10:00:00",
            "2026-02-15T12:00:00",
            "申请退款后找不到售后审核信息。",
            "我帮您核验申请状态。",
            after_sales=False,
            extra_messages=[{"speaker": "user", "text": "订单里也没有退款流水。"}],
        ),
        _case(
            "refund_historical_policy_002",
            "manual",
            "2025-12-28T10:00:00",
            "2025-12-31T08:00:00",
            "旧政策下审核通过七十小时，还没发起退款。",
            "按申请时七十二小时政策处理。",
        ),
    ]
    for index, spec in enumerate(specs, start=1):
        _insert_case(connection, index, spec)

    delivery_specs = [
        _delivery_case(
            "delivery_ontime_001",
            "manual",
            "2026-03-01T09:00:00",
            "2026-03-05T18:00:00",
            "2026-03-06T12:00:00",
            "包裹昨天已经收到，我想确认签收时间。",
            "我帮您核验物流记录。",
            "delivered",
            [
                ("shipment_created", "2026-03-01T10:00:00", "label_created"),
                ("picked_up", "2026-03-02T08:00:00", "carrier_pickup"),
                ("delivered", "2026-03-04T16:00:00", "signed"),
            ],
        ),
        _delivery_case(
            "delivery_ontime_002",
            "rule_generated",
            "2026-03-02T09:00:00",
            "2026-03-06T18:00:00",
            "2026-03-07T12:00:00",
            "订单已按预计时间送达。",
            "物流显示已送达。",
            "delivered",
            [
                ("shipment_created", "2026-03-02T10:00:00", "label_created"),
                ("picked_up", "2026-03-03T08:00:00", "carrier_pickup"),
                ("delivered", "2026-03-06T18:00:00", "signed"),
            ],
        ),
        _delivery_case(
            "delivery_ontime_003",
            "manual",
            "2026-03-03T09:00:00",
            "2026-03-07T18:00:00",
            "2026-03-09T12:00:00",
            "晚了半天才送到，这算超时吗？",
            "平台政策包含二十四小时宽限期。",
            "delivered",
            [
                ("shipment_created", "2026-03-03T10:00:00", "label_created"),
                ("picked_up", "2026-03-04T08:00:00", "carrier_pickup"),
                ("delivered", "2026-03-08T06:00:00", "signed"),
            ],
        ),
        _delivery_case(
            "delivery_ontime_004",
            "rule_generated",
            "2026-03-04T09:00:00",
            "2026-03-08T18:00:00",
            "2026-03-09T12:00:00",
            "商品已经提前送达。",
            "确认物流已完成。",
            "delivered",
            [
                ("shipment_created", "2026-03-04T10:00:00", "label_created"),
                ("picked_up", "2026-03-05T08:00:00", "carrier_pickup"),
                ("delivered", "2026-03-07T14:00:00", "signed"),
            ],
        ),
        _delivery_case(
            "delivery_within_001",
            "manual",
            "2026-03-05T09:00:00",
            "2026-03-10T18:00:00",
            "2026-03-09T12:00:00",
            "还没收到货，但预计明天才送达。",
            "包裹仍在运输中，请等待。",
            "shipped",
            [
                ("shipment_created", "2026-03-05T10:00:00", "label_created"),
                ("picked_up", "2026-03-06T08:00:00", "carrier_pickup"),
                ("in_transit", "2026-03-08T08:00:00", "linehaul"),
            ],
        ),
        _delivery_case(
            "delivery_within_002",
            "rule_generated",
            "2026-03-06T09:00:00",
            "2026-03-10T18:00:00",
            "2026-03-11T06:00:00",
            "超过预计时间十二小时还没收到。",
            "当前仍在物流宽限期内。",
            "shipped",
            [
                ("shipment_created", "2026-03-06T10:00:00", "label_created"),
                ("picked_up", "2026-03-07T08:00:00", "carrier_pickup"),
                ("in_transit", "2026-03-10T08:00:00", "linehaul"),
            ],
        ),
        _delivery_case(
            "delivery_within_003",
            "manual",
            "2026-03-07T09:00:00",
            "2026-03-12T18:00:00",
            "2026-03-08T09:00:00",
            "下单一天还没发货。",
            "商家仍在发货时限内。",
            "paid",
            [("shipment_created", "2026-03-07T10:00:00", "label_created")],
        ),
        _delivery_case(
            "delivery_logistics_001",
            "manual",
            "2026-03-01T09:00:00",
            "2026-03-05T18:00:00",
            "2026-03-08T12:00:00",
            "物流超过承诺时间两天还没到。",
            "包裹仍在运输途中。",
            "shipped",
            [
                ("shipment_created", "2026-03-01T10:00:00", "label_created"),
                ("picked_up", "2026-03-02T08:00:00", "carrier_pickup"),
                ("in_transit", "2026-03-07T08:00:00", "linehaul"),
            ],
        ),
        _delivery_case(
            "delivery_logistics_002",
            "manual",
            "2026-03-02T09:00:00",
            "2026-03-06T18:00:00",
            "2026-03-09T12:00:00",
            "快递说包裹丢失，一直没收到货。",
            "正在联系物流方处理。",
            "shipped",
            [
                ("shipment_created", "2026-03-02T10:00:00", "label_created"),
                ("picked_up", "2026-03-03T08:00:00", "carrier_pickup"),
                ("exception", "2026-03-07T08:00:00", "carrier_lost"),
            ],
        ),
        _delivery_case(
            "delivery_logistics_003",
            "rule_generated",
            "2026-03-03T09:00:00",
            "2026-03-07T18:00:00",
            "2026-03-10T12:00:00",
            "物流显示包裹破损无法继续配送。",
            "已提交物流异常处理。",
            "shipped",
            [
                ("shipment_created", "2026-03-03T10:00:00", "label_created"),
                ("picked_up", "2026-03-04T08:00:00", "carrier_pickup"),
                ("exception", "2026-03-08T08:00:00", "damaged"),
            ],
        ),
        _delivery_case(
            "delivery_logistics_004",
            "rule_generated",
            "2026-03-04T09:00:00",
            "2026-03-08T18:00:00",
            "2026-03-11T12:00:00",
            "包裹运输超时三天。",
            "物流仍在转运。",
            "shipped",
            [
                ("shipment_created", "2026-03-04T10:00:00", "label_created"),
                ("picked_up", "2026-03-05T08:00:00", "carrier_pickup"),
                ("in_transit", "2026-03-10T08:00:00", "linehaul"),
            ],
        ),
        _delivery_case(
            "delivery_logistics_005",
            "manual",
            "2026-03-05T09:00:00",
            "2026-03-09T18:00:00",
            "2026-03-12T12:00:00",
            "连续两天显示派送中，仍然没有收到。",
            "物流状态是派送中。",
            "shipped",
            [
                ("shipment_created", "2026-03-05T10:00:00", "label_created"),
                ("picked_up", "2026-03-06T08:00:00", "carrier_pickup"),
                ("out_for_delivery", "2026-03-10T08:00:00", "last_mile"),
            ],
        ),
        _delivery_case(
            "delivery_merchant_001",
            "manual",
            "2026-03-01T09:00:00",
            "2026-03-07T18:00:00",
            "2026-03-04T12:00:00",
            "下单三天商家还没交给快递。",
            "订单仍等待商家发货。",
            "paid",
            [("shipment_created", "2026-03-01T10:00:00", "label_created")],
        ),
        _delivery_case(
            "delivery_merchant_002",
            "rule_generated",
            "2026-03-02T09:00:00",
            "2026-03-08T18:00:00",
            "2026-03-05T12:00:00",
            "超过四十八小时没有揽收记录。",
            "正在催促商家发货。",
            "paid",
            [("shipment_created", "2026-03-02T10:00:00", "label_created")],
        ),
        _delivery_case(
            "delivery_merchant_003",
            "manual",
            "2026-03-03T09:00:00",
            "2026-03-09T18:00:00",
            "2026-03-06T12:00:00",
            "订单只有电子面单，快递一直没揽收。",
            "商家尚未完成交运。",
            "paid",
            [("shipment_created", "2026-03-03T10:00:00", "label_created")],
        ),
        _delivery_case(
            "delivery_force_majeure_001",
            "manual",
            "2026-03-04T09:00:00",
            "2026-03-08T18:00:00",
            "2026-03-11T12:00:00",
            "暴雪导致物流延迟，什么时候能到？",
            "天气原因暂停运输，请等待更新。",
            "shipped",
            [
                ("shipment_created", "2026-03-04T10:00:00", "label_created"),
                ("picked_up", "2026-03-05T08:00:00", "carrier_pickup"),
                ("exception", "2026-03-09T08:00:00", "weather"),
            ],
        ),
        _delivery_case(
            "delivery_force_majeure_002",
            "rule_generated",
            "2026-03-05T09:00:00",
            "2026-03-09T18:00:00",
            "2026-03-12T12:00:00",
            "台风造成配送延迟。",
            "不可抗力导致线路暂停。",
            "shipped",
            [
                ("shipment_created", "2026-03-05T10:00:00", "label_created"),
                ("picked_up", "2026-03-06T08:00:00", "carrier_pickup"),
                ("exception", "2026-03-10T08:00:00", "weather"),
            ],
        ),
        _delivery_case(
            "delivery_conflict_001",
            "manual",
            "2026-03-06T09:00:00",
            "2026-03-10T18:00:00",
            "2026-03-12T12:00:00",
            "订单显示已送达，但物流轨迹没有签收。",
            "系统订单状态是已送达。",
            "delivered",
            [
                ("shipment_created", "2026-03-06T10:00:00", "label_created"),
                ("picked_up", "2026-03-07T08:00:00", "carrier_pickup"),
            ],
        ),
        _delivery_case(
            "delivery_conflict_002",
            "rule_generated",
            "2026-03-07T09:00:00",
            "2026-03-11T18:00:00",
            "2026-03-12T12:00:00",
            "物流有签收事件，但订单仍显示运输中。",
            "需要核验订单与物流状态。",
            "shipped",
            [
                ("shipment_created", "2026-03-07T10:00:00", "label_created"),
                ("picked_up", "2026-03-08T08:00:00", "carrier_pickup"),
                ("delivered", "2026-03-11T12:00:00", "signed"),
            ],
        ),
        _delivery_case(
            "delivery_late_001",
            "manual",
            "2026-03-08T09:00:00",
            "2026-03-12T18:00:00",
            "2026-03-16T12:00:00",
            "包裹晚了两天才送到。",
            "确认已经送达。",
            "delivered",
            [
                ("shipment_created", "2026-03-08T10:00:00", "label_created"),
                ("picked_up", "2026-03-09T08:00:00", "carrier_pickup"),
                ("delivered", "2026-03-14T18:00:00", "signed"),
            ],
        ),
    ]
    for index, spec in enumerate(delivery_specs, start=len(specs) + 1):
        _insert_delivery_case(connection, index, spec)
    _seed_m6_cases(connection)
    _seed_m10_item_cases(connection)


def _seed_m10_item_cases(connection: sqlite3.Connection) -> None:
    groups = json.loads(M10_ITEM_MATRIX.read_text(encoding="utf-8"))
    serial = 0
    for group in groups:
        for offset in range(group["count"]):
            serial += 1
            variant = group["variants"][offset % len(group["variants"])]
            business_type = group["business_type"]
            scenario = variant["scenario"]
            case_id = f"m10_{business_type}_{offset + 1:03d}"
            order_id = f"m10-ord-{serial:03d}"
            connection.execute(
                "INSERT INTO cases VALUES (?, ?, 'rule_generated', 'CN', ?, '2026-05-01T10:00:00', '2026-05-20T12:00:00', ?)",
                (
                    case_id,
                    order_id,
                    business_type,
                    json.dumps(
                        [
                            {"speaker": "user", "text": f"请核验{business_type}商品售后争议。"},
                            {"speaker": "agent", "text": "正在核验商品和凭证。"},
                        ],
                        ensure_ascii=False,
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO orders VALUES (?, ?, 'CN', ?, 'delivered', 199.0, 'CNY', '2026-05-01T08:00:00', '2026-05-03T18:00:00', 1)",
                (order_id, f"m10-user-{serial:03d}", business_type),
            )
            category = "personal_care" if scenario == "excluded" else "general"
            connection.execute(
                "INSERT INTO order_items VALUES (?, ?, 'sku-ordered', '测试商品', 2, 99.5, ?, 1)",
                (f"m10-item-{serial:03d}", order_id, category),
            )
            _seed_m10_item_variant(connection, serial, order_id, business_type, scenario)


def _seed_m10_item_variant(
    connection: sqlite3.Connection,
    serial: int,
    order_id: str,
    business_type: str,
    scenario: str,
) -> None:
    if business_type == "return_eligibility":
        requested_at = "2026-05-15T08:00:00" if scenario == "expired" else "2026-05-05T08:00:00"
        condition = "opened_damaged" if scenario == "condition" else "unopened"
        connection.execute(
            "INSERT INTO return_requests VALUES (?, ?, ?, 'requested', ?, 'user_request', ?, 1)",
            (
                f"m10-return-{serial:03d}",
                order_id,
                f"m10-item-{serial:03d}",
                requested_at,
                condition,
            ),
        )
        return
    if business_type in {"wrong_item", "missing_item"}:
        sku = "sku-other" if scenario == "warehouse_mismatch" else "sku-ordered"
        quantity = 1 if scenario == "warehouse_shortage" else 2
        connection.execute(
            "INSERT INTO warehouse_pack_records VALUES (?, ?, ?, ?, '2026-05-02T08:00:00', 'station-m10', 1)",
            (f"m10-pack-{serial:03d}", order_id, sku, quantity),
        )
        return
    if business_type == "damaged_item" and scenario in {"attachment", "warehouse_only"}:
        connection.execute(
            "INSERT INTO warehouse_pack_records VALUES (?, ?, 'sku-ordered', 2, '2026-05-02T08:00:00', 'station-m10', 1)",
            (f"m10-pack-{serial:03d}", order_id),
        )
    if business_type == "damaged_item" and scenario == "attachment":
        connection.execute(
            "INSERT INTO claim_attachments VALUES (?, ?, 'damage_photo', ?, 524288, '商品破损照片', '2026-05-04T08:00:00', 1)",
            (
                f"m10-attachment-{serial:03d}",
                order_id,
                f"evidence://m10/{serial:03d}/damage-photo",
            ),
        )


def _seed_m6_cases(connection: sqlite3.Connection) -> None:
    specs = json.loads(M6_CASES.read_text(encoding="utf-8"))
    for index, spec in enumerate(specs, start=1):
        case_id = spec["case_id"]
        business_type = spec["business_type"]
        scenario = spec["scenario"]
        order_id = f"m6-ord-{index:03d}"
        current_time = (
            "2026-04-02T08:00:00"
            if business_type == "merchant_not_shipped" and scenario == "within"
            else "2026-04-05T12:00:00"
        )
        order_status = (
            "failed" if business_type == "payment_order_failure" else "paid"
        )
        if business_type == "delivered_not_received" and scenario != "not_marked":
            order_status = "delivered"
        connection.execute(
            "INSERT INTO cases VALUES (?, ?, 'rule_generated', 'CN', ?, '2026-04-01T10:00:00', ?, ?)",
            (
                case_id,
                order_id,
                business_type,
                current_time,
                json.dumps(
                    [
                        {"speaker": "user", "text": f"请处理{case_id}对应的争议。"},
                        {"speaker": "agent", "text": "我正在核验业务记录。"},
                    ],
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO orders VALUES (?, ?, 'CN', ?, ?, 199.0, 'CNY', '2026-04-01T08:00:00', '2026-04-03T18:00:00', 1)",
            (order_id, f"m6-user-{index:03d}", business_type, order_status),
        )
        if business_type == "refund_amount":
            _seed_m6_refund_amount(connection, index, order_id, scenario)
        elif business_type == "duplicate_charge":
            _seed_m6_duplicate_charge(connection, index, order_id, scenario)
        elif business_type == "payment_order_failure":
            _seed_m6_payment_failure(connection, index, order_id, scenario)
        elif business_type == "merchant_not_shipped":
            if scenario == "picked_up":
                _insert_m6_logistics(connection, index, order_id, "picked_up", "09:00:00")
        elif business_type == "delivered_not_received":
            _seed_m6_delivery_receipt(connection, index, order_id, scenario)
        elif business_type == "cancellation_in_transit":
            _seed_m6_cancellation(connection, index, order_id, scenario)


def _seed_m6_refund_amount(
    connection: sqlite3.Connection, index: int, order_id: str, scenario: str
) -> None:
    connection.execute(
        "INSERT INTO payments VALUES (?, ?, 'debit', 199.0, 'succeeded', '2026-04-01T08:01:00', 1)",
        (f"m6-pay-{index}-debit", order_id),
    )
    if scenario == "missing_refund":
        return
    refund_amount = 99.0 if scenario == "incorrect" else 199.0
    credit_amount = 99.0 if scenario == "credit_mismatch" else refund_amount
    connection.execute(
        "INSERT INTO refunds VALUES (?, ?, ?, 'succeeded', '2026-04-02T08:00:00', '2026-04-03T08:00:00', 1)",
        (f"m6-ref-{index}", order_id, refund_amount),
    )
    connection.execute(
        "INSERT INTO payments VALUES (?, ?, 'credit', ?, 'succeeded', '2026-04-03T08:01:00', 1)",
        (f"m6-pay-{index}-credit", order_id, credit_amount),
    )


def _seed_m6_duplicate_charge(
    connection: sqlite3.Connection, index: int, order_id: str, scenario: str
) -> None:
    if scenario == "missing_payment":
        return
    statuses = {
        "confirmed": ["succeeded", "succeeded"],
        "pending": ["succeeded", "pending"],
        "not_found": ["succeeded"],
    }[scenario]
    for event_index, status in enumerate(statuses, start=1):
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'debit', 199.0, ?, ?, 1)",
            (
                f"m6-pay-{index}-{event_index}",
                order_id,
                status,
                f"2026-04-01T08:0{event_index}:00",
            ),
        )


def _seed_m6_payment_failure(
    connection: sqlite3.Connection, index: int, order_id: str, scenario: str
) -> None:
    debit_status = "failed" if scenario == "not_captured" else "succeeded"
    connection.execute(
        "INSERT INTO payments VALUES (?, ?, 'debit', 199.0, ?, '2026-04-01T08:01:00', 1)",
        (f"m6-pay-{index}-debit", order_id, debit_status),
    )
    if scenario == "reversed_credit":
        connection.execute(
            "INSERT INTO payments VALUES (?, ?, 'reversal', 199.0, 'succeeded', '2026-04-01T09:01:00', 1)",
            (f"m6-pay-{index}-reversal", order_id),
        )
    if scenario == "reversed_refund":
        connection.execute(
            "INSERT INTO refunds VALUES (?, ?, 199.0, 'succeeded', '2026-04-01T09:00:00', '2026-04-01T10:00:00', 1)",
            (f"m6-ref-{index}", order_id),
        )


def _seed_m6_delivery_receipt(
    connection: sqlite3.Connection, index: int, order_id: str, scenario: str
) -> None:
    if scenario != "not_marked":
        _insert_m6_logistics(connection, index, order_id, "delivered", "12:00:00")
    if scenario == "disputed":
        connection.execute(
            "INSERT INTO delivery_proofs VALUES (?, ?, '门卫', 'signature', '2026-04-03T12:00:00', 'signed by concierge', 1)",
            (f"m6-proof-{index}", order_id),
        )
    connection.execute(
        "INSERT INTO delivery_addresses VALUES (?, ?, '南京', '鼓楼区***路', '1234', 1)",
        (f"m6-address-{index}", order_id),
    )


def _seed_m6_cancellation(
    connection: sqlite3.Connection, index: int, order_id: str, scenario: str
) -> None:
    requested_at = "2026-04-01T09:00:00"
    connection.execute(
        "INSERT INTO cancellation_requests VALUES (?, ?, 'accepted', ?, '2026-04-01T09:01:00', 'user_request', 1)",
        (f"m6-cancel-{index}", order_id, requested_at),
    )
    if scenario in {"before_pickup", "after_pickup", "completed"}:
        pickup_time = "10:00:00" if scenario == "before_pickup" else "08:00:00"
        _insert_m6_logistics(connection, index, order_id, "picked_up", pickup_time)
    if scenario == "completed":
        connection.execute(
            "INSERT INTO refunds VALUES (?, ?, 199.0, 'succeeded', '2026-04-02T09:00:00', '2026-04-03T09:00:00', 1)",
            (f"m6-ref-{index}", order_id),
        )


def _insert_m6_logistics(
    connection: sqlite3.Connection,
    index: int,
    order_id: str,
    event_type: str,
    time: str,
) -> None:
    connection.execute(
        "INSERT INTO logistics_events VALUES (?, ?, ?, ?, ?, 1)",
        (
            f"m6-log-{index}-{event_type}",
            order_id,
            event_type,
            f"2026-04-01T{time}",
            event_type,
        ),
    )


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
        "INSERT INTO orders VALUES (?, ?, 'CN', 'refund', 'paid', 199.0, 'CNY', '2025-12-20T09:00:00', NULL, 1)",
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


def _delivery_case(
    case_id: str,
    source_type: str,
    created_at: str,
    promised_delivery_at: str,
    current_time: str,
    user_text: str,
    agent_text: str,
    order_status: str,
    events: list[tuple[str, str, str]],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "source_type": source_type,
        "created_at": created_at,
        "promised_delivery_at": promised_delivery_at,
        "current_time": current_time,
        "conversation": [
            {"speaker": "user", "text": user_text},
            {"speaker": "agent", "text": agent_text},
        ],
        "order_status": order_status,
        "events": events,
    }


def _insert_delivery_case(connection: sqlite3.Connection, index: int, spec: dict[str, Any]) -> None:
    order_id = f"ord-{1000 + index}"
    connection.execute(
        "INSERT INTO cases VALUES (?, ?, ?, 'CN', 'delivery', ?, ?, ?)",
        (
            spec["case_id"],
            order_id,
            spec["source_type"],
            spec["created_at"],
            spec["current_time"],
            json.dumps(spec["conversation"], ensure_ascii=False),
        ),
    )
    connection.execute(
        "INSERT INTO orders VALUES (?, ?, 'CN', 'delivery', ?, 299.0, 'CNY', ?, ?, 1)",
        (
            order_id,
            f"user-{index}",
            spec["order_status"],
            spec["created_at"],
            spec["promised_delivery_at"],
        ),
    )
    for event_index, (event_type, occurred_at, detail) in enumerate(spec["events"], start=1):
        connection.execute(
            "INSERT INTO logistics_events VALUES (?, ?, ?, ?, ?, 1)",
            (f"log-{index}-{event_index}", order_id, event_type, occurred_at, detail),
        )
