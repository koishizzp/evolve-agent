"""抽象 Tool 基类。"""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """所有工具的抽象父类。"""

    name: str = "base"
    description: str = ""

    @abstractmethod
    def run(self, input_data: dict) -> dict:
        """执行工具逻辑并返回统一结果格式。"""
        raise NotImplementedError
