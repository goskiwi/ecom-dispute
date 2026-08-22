from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from .contracts import Evidence, EvidenceKind, ToolResult
from .repository import Repository


class ToolRegistry:
    def __init__(self, repository: Repository):
        self.repository = repository
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], ToolResult] = {}
        self._tools: dict[str, Callable[..., ToolResult]] = {
            "get_order": self.get_order,
            "get_logistics_events": self.get_logistics_events,
            "get_payment_records": self.get_payment_records,
            "get_refund_records": self.get_refund_records,
            "get_after_sales_case": self.get_after_sales_case,
            "read_policy": self.read_policy,
        }

    @property
    def names(self) -> set[str]:
        return set(self._tools)

    def response_tools(self, allowed: set[str] | None = None) -> list[dict]:
        descriptions = {
            "get_order": "按订单号查询订单状态、金额、地区和业务类型。",
            "get_logistics_events": "按订单号查询物流事件。",
            "get_payment_records": "按订单号查询扣款和入账支付流水。",
            "get_refund_records": "按订单号查询退款发起、处理和完成记录。",
            "get_after_sales_case": "按订单号查询售后申请、审核状态和通过时间。",
            "read_policy": "按地区、业务类型和事件时间查询当时生效的政策版本。",
        }
        tools = []
        for name in sorted(allowed or self.names):
            if name not in self._tools:
                continue
            if name == "read_policy":
                properties = {
                    "region": {"type": "string"},
                    "business_type": {"type": "string"},
                    "effective_at": {"type": "string", "description": "ISO-8601 时间"},
                }
                required = ["region", "business_type", "effective_at"]
            else:
                properties = {"order_id": {"type": "string"}}
                required = ["order_id"]
            tools.append(
                {
                    "type": "function",
                    "name": name,
                    "description": descriptions[name],
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    },
                }
            )
        return tools

    def execute(self, name: str, **arguments: str) -> ToolResult:
        if name not in self._tools:
            return ToolResult(tool_name=name, status="invalid", error_code="UNKNOWN_TOOL")
        cache_key = (name, tuple(sorted(arguments.items())))
        if cache_key not in self._cache:
            self._cache[cache_key] = self._tools[name](**arguments)
        return self._cache[cache_key].model_copy(deep=True)

    def get_order(self, order_id: str) -> ToolResult:
        row = self.repository.one("orders", "order_id", order_id)
        return self._single("get_order", EvidenceKind.ORDER, "orders", "order_id", row, "created_at")

    def get_after_sales_case(self, order_id: str) -> ToolResult:
        row = self.repository.one("after_sales_cases", "order_id", order_id)
        return self._single(
            "get_after_sales_case",
            EvidenceKind.AFTER_SALES,
            "after_sales_cases",
            "after_sales_id",
            row,
            "approved_at",
        )

    def get_logistics_events(self, order_id: str) -> ToolResult:
        return self._many(
            "get_logistics_events",
            EvidenceKind.LOGISTICS,
            "logistics_events",
            "event_id",
            self.repository.many("logistics_events", order_id),
            "occurred_at",
        )

    def get_payment_records(self, order_id: str) -> ToolResult:
        return self._many(
            "get_payment_records",
            EvidenceKind.PAYMENT,
            "payments",
            "payment_id",
            self.repository.many("payments", order_id),
            "occurred_at",
        )

    def get_refund_records(self, order_id: str) -> ToolResult:
        return self._many(
            "get_refund_records",
            EvidenceKind.REFUND,
            "refunds",
            "refund_id",
            self.repository.many("refunds", order_id),
            "completed_at",
        )

    def read_policy(self, region: str, business_type: str, effective_at: str) -> ToolResult:
        row = self.repository.policy(region, business_type, datetime.fromisoformat(effective_at))
        if row:
            row["rules"] = json.loads(row.pop("rules_json"))
        return self._single(
            "read_policy", EvidenceKind.POLICY, "policies", "policy_id", row, "effective_from"
        )

    @staticmethod
    def _single(
        tool: str,
        kind: EvidenceKind,
        source: str,
        key_field: str,
        row: dict | None,
        time_field: str,
    ) -> ToolResult:
        if not row:
            return ToolResult(tool_name=tool, status="not_found", message="business record not found")
        return ToolResult(
            tool_name=tool,
            status="ok",
            evidence=[ToolRegistry._evidence(kind, source, key_field, row, time_field)],
        )

    @staticmethod
    def _many(
        tool: str,
        kind: EvidenceKind,
        source: str,
        key_field: str,
        rows: list[dict],
        time_field: str,
    ) -> ToolResult:
        if not rows:
            return ToolResult(tool_name=tool, status="not_found", message="business records not found")
        return ToolResult(
            tool_name=tool,
            status="ok",
            evidence=[ToolRegistry._evidence(kind, source, key_field, row, time_field) for row in rows],
        )

    @staticmethod
    def _evidence(
        kind: EvidenceKind, source: str, key_field: str, row: dict, time_field: str
    ) -> Evidence:
        business_key = str(row[key_field])
        version = int(row.get("version", 1))
        occurred = row.get(time_field)
        return Evidence(
            evidence_id=f"{source}:{business_key}:v{version}",
            kind=kind,
            source=source,
            business_key=business_key,
            version=version,
            occurred_at=datetime.fromisoformat(occurred) if occurred else None,
            facts=row,
            summary=ToolRegistry._summary(kind, row),
        )

    @staticmethod
    def _summary(kind: EvidenceKind, row: dict) -> str:
        if kind == EvidenceKind.REFUND:
            return f"退款 {row['refund_id']} 状态为 {row['status']}，金额 {row['amount']}"
        if kind == EvidenceKind.PAYMENT:
            return f"支付事件 {row['payment_id']} 为 {row['event_type']}/{row['status']}"
        if kind == EvidenceKind.AFTER_SALES:
            return f"售后单 {row['after_sales_id']} 状态为 {row['status']}"
        if kind == EvidenceKind.POLICY:
            return f"适用政策 {row['policy_id']} v{row['version']}"
        if kind == EvidenceKind.ORDER:
            return f"订单 {row['order_id']} 状态为 {row['status']}"
        return f"{kind.value} 记录 {row}"
