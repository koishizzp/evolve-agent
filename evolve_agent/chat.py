"""Helpers for OpenAI-compatible chat handling."""
from __future__ import annotations

from time import time
from typing import Any


def latest_user_content(messages: list[dict[str, Any]] | None) -> str:
    for item in reversed(messages or []):
        if str(item.get("role") or "") == "user":
            return str(item.get("content") or "").strip()
    return ""


def normalize_chat_context(
    latest_result: dict[str, Any] | None,
    reasoning_context: dict[str, Any] | None,
) -> dict[str, Any]:
    result = latest_result or {}
    reasoning_context = reasoning_context or {}
    if not result and isinstance(reasoning_context.get("latest_result"), dict):
        result = reasoning_context["latest_result"]
    return result


def top_variant_from_result(latest_result: dict[str, Any] | None) -> dict[str, Any]:
    latest_result = latest_result or {}
    summary = latest_result.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("top_variant"), dict):
        return summary["top_variant"]
    parsed = latest_result.get("parsed_result")
    if isinstance(parsed, dict) and isinstance(parsed.get("top_variant"), dict):
        return parsed["top_variant"]
    return {}


def build_reasoning_context(chat_mode: str, latest_result: dict[str, Any] | None) -> dict[str, Any]:
    context = {
        "version": 1,
        "chat_mode": chat_mode,
        "latest_result": latest_result or {},
    }
    top_variant = top_variant_from_result(latest_result)
    if top_variant:
        context["top_variant"] = top_variant
    return context


def extras_from_result(latest_result: dict[str, Any] | None) -> dict[str, Any]:
    latest_result = latest_result or {}
    summary = latest_result.get("summary") if isinstance(latest_result.get("summary"), dict) else {}
    parsed = latest_result.get("parsed_result") if isinstance(latest_result.get("parsed_result"), dict) else {}
    top_variant = top_variant_from_result(latest_result)
    request = latest_result.get("request") if isinstance(latest_result.get("request"), dict) else {}
    extra: dict[str, Any] = {"strategy": latest_result.get("tool")}
    if top_variant:
        extra["top_variant"] = top_variant
    if summary:
        extra["summary"] = summary
    if parsed:
        extra["parsed_result"] = parsed
    if request:
        extra["request"] = request
    return extra


def is_reasoning_query(content: str) -> bool:
    text = content.lower().strip()
    if not text:
        return False
    reasoning_keywords = ("why", "explain", "compare", "reason", "为什么", "解释", "比较", "分析", "差别")
    execution_keywords = ("run", "optimize", "evolve", "evolvepro", "multievolve", "执行", "优化", "突变")
    if any(keyword in text for keyword in reasoning_keywords):
        return True
    return False if any(keyword in text for keyword in execution_keywords) else False


def build_chat_completion(
    content: str,
    *,
    model: str = "evolve-agent",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": f"chatcmpl-{int(time())}",
        "object": "chat.completion",
        "created": int(time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
    for key, value in (extra or {}).items():
        payload[key] = value
    return payload
