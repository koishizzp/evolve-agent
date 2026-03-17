"""Structured service layer for EvolvePro and MULTI-evolve."""
from __future__ import annotations

from math import isfinite
from typing import Any

from evolve_agent.parser import OutputParser
from evolve_agent.settings import Settings, get_settings
from evolve_agent.tools import EvolveProTool, MultiEvolveTool


def _normalize_number(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            return None
        return value
    return value


class EvolutionService:
    SUPPORTED_TOOLS = ["evolvepro", "multievolve", "both"]

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        config = self.settings.to_agent_config()
        self.evolvepro = EvolveProTool(config)
        self.multievolve = MultiEvolveTool(config)
        self.parser = OutputParser()

    def available_tools(self) -> list[str]:
        return list(self.SUPPORTED_TOOLS)

    def status_payload(self) -> dict[str, Any]:
        return {
            "app_name": self.settings.app_name,
            "default_strategy": self.settings.default_strategy,
            "evolvepro_root": self.settings.evolvepro_root,
            "multievolve_root": self.settings.multievolve_root,
            "multievolve_model_dir": self.settings.multievolve_model_dir,
            "tmp_dir": self.settings.tmp_dir,
            "result_dir": self.settings.result_dir,
            "upload_dir": self.settings.upload_dir,
            "available_tools": self.available_tools(),
        }

    def execute_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        tool = str(plan.get("tool") or self.settings.default_strategy).strip()
        task = str(plan.get("task") or "")
        params = dict(plan.get("params") or {})
        fasta_path = str(params.get("fasta_path") or "")
        activity_csv_path = params.get("activity_csv_path")

        if tool in {"evolvepro", "multievolve", "both"}:
            return self.run_evolution(
                fasta_path,
                task=task,
                activity_csv_path=activity_csv_path,
                strategy=tool,
                params=params,
                rationale=plan.get("rationale"),
            )
        raise ValueError(f"Unsupported evolution tool: {tool}")

    def run_evolution(
        self,
        fasta_path: str,
        *,
        task: str,
        activity_csv_path: str | None = None,
        strategy: str | None = None,
        params: dict[str, Any] | None = None,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        strategy = strategy or self.settings.default_strategy
        params = dict(params or {})
        request = {
            "task": task,
            "fasta_path": fasta_path,
            "activity_csv_path": activity_csv_path,
            "strategy": strategy,
        }
        payload = {
            "fasta_path": fasta_path,
            "activity_csv_path": activity_csv_path,
            "task": task,
            "params": params,
            "result_dir": self.settings.result_dir,
        }

        if strategy == "evolvepro":
            raw = self.evolvepro.run(payload)
            return self._build_result("evolvepro", request, raw, rationale=rationale)

        if strategy == "multievolve":
            raw = self.multievolve.run(payload)
            return self._build_result("multievolve", request, raw, rationale=rationale)

        if strategy == "both":
            first = self.multievolve.run(payload)
            second = self.evolvepro.run(payload) if activity_csv_path else {
                "success": False,
                "output": "",
                "error": "EvolvePro skipped because activity_csv_path is missing.",
                "result_files": [],
            }
            raw = second if second.get("success") else first
            result = self._build_result("both", request, raw, rationale=rationale)
            result["pipeline"] = {
                "multievolve": {
                    "success": bool(first.get("success")),
                    "error": first.get("error", ""),
                    "result_files": first.get("result_files", []),
                },
                "evolvepro": {
                    "success": bool(second.get("success")),
                    "error": second.get("error", ""),
                    "result_files": second.get("result_files", []),
                },
            }
            return result

        raise ValueError(f"Unsupported evolution strategy: {strategy}")

    def _build_result(
        self,
        tool_name: str,
        request: dict[str, Any],
        raw: dict[str, Any],
        *,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        parsed = self.parser.parse(tool_name, list(raw.get("result_files", [])))
        summary = self._summary(parsed, request, tool_name)
        return {
            "tool": tool_name,
            "request": request,
            "success": bool(raw.get("success")),
            "output": raw.get("output", ""),
            "error": raw.get("error", ""),
            "result_files": raw.get("result_files", []),
            "parsed_result": parsed,
            "summary": summary,
            "command": raw.get("command", []),
            "rationale": rationale or "",
        }

    def _summary(self, parsed: dict[str, Any], request: dict[str, Any], tool_name: str) -> dict[str, Any]:
        variants = parsed.get("variants", []) if isinstance(parsed.get("variants"), list) else []
        top_variant = parsed.get("top_variant", {}) if isinstance(parsed.get("top_variant"), dict) else {}
        return {
            "tool": tool_name,
            "strategy": request.get("strategy", tool_name),
            "count": len(variants),
            "variant_count": len(variants),
            "top_variant": {key: _normalize_number(value) for key, value in top_variant.items()},
        }

    def format_execution_reply(self, result: dict[str, Any]) -> str:
        if not result.get("success"):
            return str(result.get("error") or "Execution failed.")

        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        top_variant = summary.get("top_variant", {}) if isinstance(summary.get("top_variant"), dict) else {}
        tool = str(result.get("tool") or summary.get("tool") or "multievolve")

        if not top_variant:
            return f"已执行 {tool}，但没有解析出可用变体。请检查输出文件格式。"

        score = top_variant.get("score")
        score_text = "未知" if score is None else f"{float(score):.4f}"
        mutations = top_variant.get("mutations") or "-"
        count = int(summary.get("count") or 0)
        return (
            f"已完成 {tool}。"
            f" Top 变体为 {mutations}，score={score_text}。"
            f" 本次共解析 {count} 个候选。"
        )
