from __future__ import annotations

import csv
import json
from pathlib import Path

from Bio import SeqIO


class OutputParser:
    """Parse EvolvePro or MULTI-evolve outputs into a normalized structure."""

    @staticmethod
    def _normalize_variant(row: dict) -> dict:
        sequence = row.get("sequence") or row.get("variant_sequence") or ""
        mutations = row.get("mutations") or row.get("mutation") or row.get("name") or ""
        score_raw = row.get("score") or row.get("predicted_activity") or row.get("fitness") or 0.0
        try:
            score = float(score_raw)
        except (ValueError, TypeError):
            score = None
        return {"sequence": str(sequence), "mutations": str(mutations), "score": score}

    def parse(self, tool_name: str, result_files: list[str]) -> dict:
        """Parse the first existing result file."""
        if not result_files:
            return {"variants": [], "top_variant": {}, "source_tool": tool_name, "result_files": []}

        existing_files = [Path(item) for item in result_files if Path(item).exists()]
        if not existing_files:
            return {"variants": [], "top_variant": {}, "source_tool": tool_name, "result_files": result_files}

        variants = self._parse_path(existing_files[0])
        variants.sort(key=lambda item: float(item.get("score") or float("-inf")), reverse=True)
        top_variant = variants[0] if variants else {}
        return {
            "variants": variants,
            "top_variant": top_variant,
            "source_tool": tool_name,
            "result_files": [str(path) for path in existing_files],
        }

    def _parse_path(self, path: Path) -> list[dict]:
        suffix = path.suffix.lower()
        if suffix in {".csv", ".tsv"}:
            return self._parse_delimited(path, delimiter="\t" if suffix == ".tsv" else ",")
        if suffix in {".fa", ".fasta", ".faa"}:
            return self._parse_fasta(path)
        if suffix == ".json":
            return self._parse_json(path)
        return []

    def _parse_delimited(self, path: Path, *, delimiter: str) -> list[dict]:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            return [self._normalize_variant(row) for row in reader]

    def _parse_fasta(self, path: Path) -> list[dict]:
        variants = []
        for record in SeqIO.parse(path, "fasta"):
            variants.append(
                {
                    "sequence": str(record.seq),
                    "mutations": record.id,
                    "score": None,
                }
            )
        return variants

    def _parse_json(self, path: Path) -> list[dict]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return [self._normalize_variant(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            items = payload.get("variants")
            if isinstance(items, list):
                return [self._normalize_variant(item) for item in items if isinstance(item, dict)]
        return []
