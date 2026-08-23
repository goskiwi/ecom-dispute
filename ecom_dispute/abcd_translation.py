from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .llm import ResponsesClient


class TranslatedTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["user", "agent"]
    text: str = Field(min_length=1)


class TranslatedConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turns: list[TranslatedTurn]


def translate_annotation_forms(
    client: ResponsesClient,
    rater1_path: Path,
    rater2_path: Path,
    cache_path: Path,
    workers: int = 4,
) -> dict:
    first = json.loads(rater1_path.read_text(encoding="utf-8"))
    second = json.loads(rater2_path.read_text(encoding="utf-8"))
    first_items = {item["external_id"]: item for item in first["items"]}
    second_items = {item["external_id"]: item for item in second["items"]}
    if set(first_items) != set(second_items):
        raise ValueError("ABCD rater forms contain different records")
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    cache_lock = threading.Lock()

    def translate_one(external_id: str) -> dict:
        if external_id in cache and "translation" in cache[external_id]:
            return cache[external_id]
        conversation = first_items[external_id]["conversation"]
        prompt = (
            "你是逐句翻译器。将下面英文客服对话忠实翻译成简体中文。"
            "保持turn数量、顺序和speaker完全一致；保留金额、时间、订单号、SKU和专有名词。"
            "只翻译，不总结、不分类、不判断业务Route、不补充原文没有的信息。\n"
            f"对话：{json.dumps(conversation, ensure_ascii=False)}"
        )
        payload = {
            "model": client.model,
            "input": prompt,
            "max_output_tokens": 2000,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "translated_conversation",
                    "strict": True,
                    "schema": TranslatedConversation.model_json_schema(),
                }
            },
        }
        started = time.perf_counter()
        response = client.create_response(payload)
        translated = TranslatedConversation.model_validate_json(
            ResponsesClient._output_text(response)
        )
        if len(translated.turns) != len(conversation):
            raise ValueError(f"translation turn count mismatch: {external_id}")
        for source, target in zip(conversation, translated.turns, strict=True):
            if source["speaker"] != target.speaker:
                raise ValueError(f"translation speaker mismatch: {external_id}")
        usage = response.get("usage") or {}
        return {
            "translation": [item.model_dump() for item in translated.turns],
            "telemetry": {
                "model": response.get("model", client.model),
                "response_id": response.get("id"),
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "latency_ms": round((time.perf_counter() - started) * 1000),
            },
        }

    errors = {}
    pending = [item for item in sorted(first_items) if "translation" not in cache.get(item, {})]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(translate_one, external_id): external_id for external_id in pending
        }
        for future in as_completed(futures):
            external_id = futures[future]
            try:
                result = future.result()
            except (RuntimeError, ValueError) as exc:
                errors[external_id] = str(exc)
                continue
            with cache_lock:
                cache[external_id] = result
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
                )

    for form, items in ((first, first_items), (second, second_items)):
        for external_id, item in items.items():
            if external_id not in cache or "translation" not in cache[external_id]:
                continue
            item["translation"] = cache[external_id]["translation"]
            item["translation_meta"] = {
                "source": cache[external_id]["telemetry"]["model"],
                "human_verified": False,
            }
            item["annotation"].setdefault("translation_uncertain", False)
        target = rater1_path if form["rater_id"] == first["rater_id"] else rater2_path
        target.write_text(json.dumps(form, ensure_ascii=False, indent=2), encoding="utf-8")

    valid = [item for item in cache.values() if "translation" in item]
    return {
        "case_count": len(first_items),
        "translated": len(valid),
        "errors": len(errors),
        "error_items": errors,
        "input_tokens": sum(item["telemetry"]["input_tokens"] for item in valid),
        "output_tokens": sum(item["telemetry"]["output_tokens"] for item in valid),
        "latency_ms": sum(item["telemetry"]["latency_ms"] for item in valid),
    }
