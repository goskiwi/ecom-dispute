from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...contracts import CaseInput, CaseState, EvidenceKind
from ..base import DecisionOutcome


def _evidence(state: CaseState, kind: EvidenceKind) -> list:
    return [item for item in state.evidence.values() if item.kind == kind]


@dataclass(frozen=True)
class ReturnEligibilityStrategy:
    def decide(self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        orders = _evidence(state, EvidenceKind.ORDER)
        items = _evidence(state, EvidenceKind.ORDER_ITEM)
        requests = _evidence(state, EvidenceKind.RETURN_REQUEST)
        policies = _evidence(state, EvidenceKind.POLICY)
        rules = policies[0].facts["rules"]
        requested = datetime.fromisoformat(requests[0].facts["requested_at"])
        created = datetime.fromisoformat(orders[0].facts["created_at"])
        if (requested - created).total_seconds() / 86400 > rules["return_window_days"]:
            return DecisionOutcome("user", "return_window_expired", "退货申请已超过政策期限", False)
        if items[0].facts["category"] in rules["excluded_categories"]:
            return DecisionOutcome("none", "return_category_excluded", "商品品类不适用无理由退货", False)
        if requests[0].facts["item_condition"] not in {"unopened", "resalable"}:
            return DecisionOutcome("user", "return_condition_ineligible", "商品状况不满足退货条件", False)
        return DecisionOutcome("none", "return_eligible", "按政策受理退货申请", False)


@dataclass(frozen=True)
class WrongItemStrategy:
    def decide(self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        ordered = {item.facts["sku_id"] for item in _evidence(state, EvidenceKind.ORDER_ITEM)}
        packed = {item.facts["sku_id"] for item in _evidence(state, EvidenceKind.WAREHOUSE_PACK)}
        if ordered != packed:
            return DecisionOutcome("warehouse", "wrong_item_warehouse_mismatch", "补发正确商品并核验仓库分拣", True)
        return DecisionOutcome("undetermined", "wrong_item_not_verified", "仓库记录与订单一致，结合附件人工复检", True)


@dataclass(frozen=True)
class MissingItemStrategy:
    def decide(self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        ordered = sum(int(item.facts["quantity"]) for item in _evidence(state, EvidenceKind.ORDER_ITEM))
        packed = sum(int(item.facts["packed_quantity"]) for item in _evidence(state, EvidenceKind.WAREHOUSE_PACK))
        if packed < ordered:
            return DecisionOutcome("warehouse", "missing_item_warehouse_shortage", "补发缺少商品并核验打包工位", True)
        return DecisionOutcome("undetermined", "missing_item_not_verified", "打包数量与订单一致，结合开箱凭证复检", True)


@dataclass(frozen=True)
class DamagedItemStrategy:
    def decide(self, case: CaseInput, state: CaseState, missing_evidence: tuple[str, ...]) -> DecisionOutcome:
        if missing_evidence:
            return DecisionOutcome()
        attachments = _evidence(state, EvidenceKind.CLAIM_ATTACHMENT)
        if attachments:
            return DecisionOutcome("undetermined", "damaged_item_evidence_confirmed", "附件已收集，结合包装和物流记录人工定责", True)
        warehouse = _evidence(state, EvidenceKind.WAREHOUSE_PACK)
        if warehouse:
            return DecisionOutcome("user", "damaged_item_attachment_missing", "请用户补充商品和外包装照片", True)
        return DecisionOutcome("undetermined", "damaged_item_insufficient_evidence", "补充图片和仓库记录后复检", True)
