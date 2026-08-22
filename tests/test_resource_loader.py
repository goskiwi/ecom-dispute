from pathlib import Path
from shutil import copytree

import pytest
import yaml

from ecom_dispute.resource_loader import (
    RESOURCE_ROOT,
    SkillLoader,
    ToolDefinitionLoader,
)
from ecom_dispute.skills import default_strategies


def test_default_resources_are_typed_and_cross_validated() -> None:
    tools = ToolDefinitionLoader().load_all()
    packs = SkillLoader(
        known_tools=set(tools),
        known_strategies=set(default_strategies()),
    ).load_all()

    assert set(packs) == {"funds-dispute", "fulfillment-dispute"}
    refund = packs["funds-dispute"].routes["refund-status"]
    assert refund.match.business_types == ("refund",)
    assert refund.stages["ANALYZE"].mode == "agent"
    assert refund.stages["VERIFY"].mode == "deterministic"
    assert refund.core_tools == (
        "get_order",
        "get_payment_records",
        "get_refund_records",
        "get_after_sales_case",
        "read_policy",
    )


def test_route_cannot_escape_skill_tool_allowlist(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    copytree(RESOURCE_ROOT / "skills", root)
    route_file = root / "funds-dispute" / "routes" / "refund-status.yaml"
    payload = yaml.safe_load(route_file.read_text(encoding="utf-8"))
    payload["core_tools"].append("get_delivery_proof")
    route_file.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="outside skill allowlist"):
        SkillLoader(root).load_all()


def test_route_rejects_missing_stage_instruction(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    copytree(RESOURCE_ROOT / "skills", root)
    route_file = root / "fulfillment-dispute" / "routes" / "delivery-delay.yaml"
    payload = yaml.safe_load(route_file.read_text(encoding="utf-8"))
    payload["stages"]["ANALYZE"]["instruction_file"] = "stages/missing.md"
    route_file.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="missing instruction file"):
        SkillLoader(root).load_all()
