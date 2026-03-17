"""Result explanation for protein engineering runs."""
from __future__ import annotations

import json
import logging
from typing import Any

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None

from evolve_agent.chat import top_variant_from_result
from evolve_agent.settings import Settings

LOGGER = logging.getLogger(__name__)


class ResultReasoner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = None
        if settings.openai_api_key:
            if OpenAI is None:
                LOGGER.warning("openai package unavailable; using fallback evolve reasoner.")
            else:
                self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    def reply(
        self,
        message: str,
        latest_result: dict[str, Any] | None = None,
        conversation: list[dict[str, str]] | None = None,
    ) -> str:
        fallback = self._fallback_reply(latest_result)
        if not self.client:
            return fallback

        payload = {
            "message": message,
            "conversation": conversation or [],
            "latest_result": self._compact_result(latest_result),
        }
        try:
            response = self.client.responses.create(
                model=self.settings.llm_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a protein engineering analysis copilot. "
                            "Reply in concise Simplified Chinese. "
                            "Ground the answer in the provided result object. "
                            "If you infer beyond the data, label it as 推断."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            text = (response.output_text or "").strip()
            return text or fallback
        except Exception:  # noqa: BLE001
            LOGGER.exception("Evolve reasoning request failed; using fallback.")
            return fallback

    def _compact_result(self, latest_result: dict[str, Any] | None) -> dict[str, Any] | None:
        if not latest_result:
            return None
        request = latest_result.get("request") if isinstance(latest_result.get("request"), dict) else {}
        summary = latest_result.get("summary") if isinstance(latest_result.get("summary"), dict) else {}
        parsed = latest_result.get("parsed_result") if isinstance(latest_result.get("parsed_result"), dict) else {}
        return {
            "tool": latest_result.get("tool"),
            "request": request,
            "summary": summary,
            "top_variant": top_variant_from_result(latest_result),
            "variant_count": len(parsed.get("variants") or []),
        }

    def _fallback_reply(self, latest_result: dict[str, Any] | None) -> str:
        if not latest_result:
            return "我现在还没有可引用的演化结果。先执行一次任务，或者在请求里附带 latest_result。"

        top_variant = top_variant_from_result(latest_result)
        summary = latest_result.get("summary") if isinstance(latest_result.get("summary"), dict) else {}
        tool = str(latest_result.get("tool") or "multievolve")

        if not top_variant:
            return f"当前结果已经执行了 {tool}，但没有解析出可用变体。建议先检查输出文件格式和命令参数。"

        score = top_variant.get("score")
        score_text = "未知" if score is None else f"{float(score):.4f}"
        lines = [
            f"当前最值得优先验证的结果来自 {tool}。",
            f"Top 变体: mutations={top_variant.get('mutations') or '-'}, score={score_text}。",
        ]
        if top_variant.get("sequence"):
            lines.append(f"序列长度为 {len(str(top_variant['sequence']))} aa。")
        variant_count = summary.get("variant_count")
        if variant_count is not None:
            lines.append(f"本次共解析出 {variant_count} 个候选变体。")
        lines.append("需要注意，这里只是模型排序结果，不等于实验上一定最优。")
        return "\n".join(lines)
