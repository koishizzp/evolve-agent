"""解析工具输出为统一格式。"""

from __future__ import annotations

import csv
from pathlib import Path


class OutputParser:
    """统一解析 EvolvePro 与 MULTI-evolve 的输出。"""

    @staticmethod
    def _normalize_variant(row: dict) -> dict:
        """兼容不同列名。"""
        sequence = row.get("sequence") or row.get("variant_sequence") or ""
        mutations = row.get("mutations") or row.get("mutation") or ""
        score_raw = row.get("score") or row.get("predicted_activity") or row.get("fitness") or 0.0
        try:
            score = float(score_raw)
        except (ValueError, TypeError):
            score = 0.0
        return {"sequence": str(sequence), "mutations": str(mutations), "score": score}

    def parse(self, tool_name: str, result_files: list[str]) -> dict:
        """根据工具类型解析输出文件。"""
        if not result_files:
            return {"variants": [], "top_variant": {}}

        csv_path = Path(result_files[0])
        if not csv_path.exists():
            return {"variants": [], "top_variant": {}}

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            variants = [self._normalize_variant(row) for row in reader]

        variants.sort(key=lambda x: x["score"], reverse=True)
        return {
            "variants": variants,
            "top_variant": variants[0] if variants else {},
            "source_tool": tool_name,
        }
