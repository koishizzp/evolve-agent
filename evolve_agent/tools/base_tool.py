from __future__ import annotations

import shlex
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class BaseTool(ABC):
    """Base class for tool integrations."""

    name: str = "base"
    description: str = ""

    def __init__(self, config: dict):
        self.config = config

    @staticmethod
    def ensure_dir(path: str | Path) -> Path:
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def format_command(self, template: list[str], values: Mapping[str, Any]) -> list[str]:
        safe_values = {key: self._stringify(value) for key, value in values.items()}
        return [part.format_map(safe_values) for part in template]

    def command_text(self, command: list[str]) -> str:
        return " ".join(shlex.quote(part) for part in command)

    @abstractmethod
    def run(self, input_data: dict) -> dict:
        """Execute the tool and return a normalized result payload."""
        raise NotImplementedError
