"""Natural-language planner for EvolvePro and MULTI-evolve routing."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None

from evolve_agent.settings import Settings

LOGGER = logging.getLogger(__name__)

FASTA_PATTERN = re.compile(r"""["']?((?:[A-Za-z]:\\|/|\.{1,2}[\\/])?[^\s"'`]+?\.(?:fa|faa|fasta|fas))["']?""", re.IGNORECASE)
CSV_PATTERN = re.compile(r"""["']?((?:[A-Za-z]:\\|/|\.{1,2}[\\/])?[^\s"'`]+?\.csv)["']?""", re.IGNORECASE)
NUM_SAMPLES_PATTERN = re.compile(r"""(?:sample|samples|采样|候选)[^\d]{0,8}(\d{1,4})""", re.IGNORECASE)
NUM_MUT_PATTERN = re.compile(r"""(?:突变数|mutation[s]?|mutants?)[^\d]{0,8}(\d{1,2})""", re.IGNORECASE)
RESIDUE_PATTERN = re.compile(r"""(?:residues?_to_mutate|位点|残基)[=:：\s]+([A-Za-z0-9_, -]+)""", re.IGNORECASE)
PROTEIN_NAME_PATTERN = re.compile(r"""(?:protein_name|蛋白名称|蛋白名)[=:：\s]+([A-Za-z0-9_.-]+)""", re.IGNORECASE)


def _strip_code_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, count=1).strip()
        if value.endswith("```"):
            value = value[:-3].strip()
    return value


def _first_match(pattern: re.Pattern[str], message: str) -> str | None:
    match = pattern.search(message)
    if not match:
        return None
    return match.group(1).strip()


class EvolvePlanner:
    """Route user requests to evolvepro, multievolve, or both."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = None
        if settings.openai_api_key:
            if OpenAI is None:
                LOGGER.warning("openai package unavailable; using heuristic evolve planner.")
            else:
                self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    def plan(
        self,
        message: str,
        available_tools: list[str],
        previous_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fallback = self._fallback_plan(message, available_tools, previous_request)
        if not self.client:
            return fallback

        prompt = {
            "task": message,
            "available_tools": available_tools,
            "previous_request": previous_request or {},
            "output_format": {
                "action": "execute or clarify",
                "tool": "one of available_tools",
                "params": "object",
                "needs_input": "bool",
                "question": "string or null",
                "rationale": "string",
            },
        }
        try:
            response = self.client.responses.create(
                model=self.settings.llm_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You route protein engineering requests to evolvepro, multievolve, or both. "
                            "Use only the provided tool names. Output valid JSON only. "
                            "If FASTA input is missing, set action=clarify and needs_input=true."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
            )
            raw = _strip_code_fences(response.output_text or "")
            decoded = json.loads(raw)
            return self._sanitize_plan(decoded, available_tools, fallback)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Evolve planner failed; using heuristic fallback.")
            return fallback

    def _fallback_plan(
        self,
        message: str,
        available_tools: list[str],
        previous_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous_request = previous_request or {}
        fasta_path = _first_match(FASTA_PATTERN, message) or previous_request.get("fasta_path")
        activity_csv_path = _first_match(CSV_PATTERN, message) or previous_request.get("activity_csv_path")
        tool = self._infer_tool(message, activity_csv_path, available_tools)

        params: dict[str, Any] = {
            "fasta_path": fasta_path,
            "activity_csv_path": activity_csv_path,
            "protein_name": _first_match(PROTEIN_NAME_PATTERN, message) or previous_request.get("protein_name"),
            "residues_to_mutate": _first_match(RESIDUE_PATTERN, message) or previous_request.get("residues_to_mutate"),
        }

        num_samples = _first_match(NUM_SAMPLES_PATTERN, message)
        if num_samples:
            params["num_samples"] = int(num_samples)
        elif previous_request.get("num_samples"):
            params["num_samples"] = previous_request["num_samples"]

        num_mutations = _first_match(NUM_MUT_PATTERN, message)
        if num_mutations:
            params["number_mutations_per_variant"] = int(num_mutations)
        elif previous_request.get("number_mutations_per_variant"):
            params["number_mutations_per_variant"] = previous_request["number_mutations_per_variant"]

        question = None
        if not fasta_path:
            question = "请提供 FASTA 文件路径，例如 /path/to/query.fasta。"

        rationale = (
            "检测到活性数据，优先走 EvolvePro few-shot 主动学习。"
            if tool == "evolvepro"
            else "任务更适合冷启动或单轮探索，优先走 MULTI-evolve。"
        )
        if tool == "both":
            rationale = "任务包含迭代优化意图，先用 MULTI-evolve 探索，再尝试 EvolvePro 精修。"

        return {
            "action": "clarify" if question else "execute",
            "tool": tool,
            "params": params,
            "needs_input": bool(question),
            "question": question,
            "rationale": rationale,
        }

    def _infer_tool(self, message: str, activity_csv_path: str | None, available_tools: list[str]) -> str:
        text = message.lower()
        if any(keyword in text for keyword in ("both", "串联", "迭代", "先", "再", "active learning")) and "both" in available_tools:
            return "both"
        if activity_csv_path and "evolvepro" in available_tools:
            return "evolvepro"
        if any(keyword in text for keyword in ("evolvepro", "few-shot", "主动学习")) and "evolvepro" in available_tools:
            return "evolvepro"
        if any(keyword in text for keyword in ("multi-evolve", "multievolve", "冷启动", "多突变")) and "multievolve" in available_tools:
            return "multievolve"
        if self.settings.default_strategy in available_tools:
            return self.settings.default_strategy
        return available_tools[0]

    def _sanitize_plan(
        self,
        decoded: dict[str, Any],
        available_tools: list[str],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(decoded, dict):
            return fallback
        tool = str(decoded.get("tool") or fallback["tool"]).strip()
        if tool not in available_tools:
            tool = fallback["tool"]
        params = decoded.get("params") if isinstance(decoded.get("params"), dict) else dict(fallback["params"])
        if not params.get("fasta_path"):
            params["fasta_path"] = fallback["params"].get("fasta_path")
        if not params.get("activity_csv_path"):
            params["activity_csv_path"] = fallback["params"].get("activity_csv_path")
        if not params.get("protein_name"):
            params["protein_name"] = fallback["params"].get("protein_name")
        if not params.get("residues_to_mutate"):
            params["residues_to_mutate"] = fallback["params"].get("residues_to_mutate")

        for name in ("num_samples", "number_mutations_per_variant"):
            value = params.get(name)
            if value in (None, ""):
                params[name] = fallback["params"].get(name)
                continue
            try:
                params[name] = int(value)
            except (TypeError, ValueError):
                params[name] = fallback["params"].get(name)

        needs_input = bool(decoded.get("needs_input")) or not params.get("fasta_path")
        action = str(decoded.get("action") or ("clarify" if needs_input else "execute")).strip().lower()
        if action not in {"execute", "clarify"}:
            action = fallback["action"]
        if needs_input:
            action = "clarify"

        question = decoded.get("question")
        if not isinstance(question, str) or not question.strip():
            question = fallback.get("question")

        rationale = decoded.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            rationale = fallback.get("rationale", "")

        return {
            "action": action,
            "tool": tool,
            "params": params,
            "needs_input": needs_input,
            "question": question,
            "rationale": rationale,
        }
