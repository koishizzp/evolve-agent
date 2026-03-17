"""任务规划器：解析用户意图并选择工具。"""

from __future__ import annotations

import json
import os
import re
from anthropic import Anthropic


class EvolvePlanner:
    """使用 LLM 生成结构化执行计划。"""

    def __init__(self, config: dict):
        self.model = config["model"]
        api_key = os.getenv("ANTHROPIC_API_KEY") or config.get("anthropic_api_key", "")
        if isinstance(api_key, str) and api_key.startswith("${"):
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.client = Anthropic(api_key=api_key) if api_key else None

    def _heuristic_plan(self, user_task: str, has_activity_data: bool) -> dict:
        """当 API 不可用时的兜底策略。"""
        if has_activity_data:
            tool = "evolvepro"
            rationale = "检测到已有活性数据，优先选择 few-shot 主动学习的 EvolvePro。"
        elif re.search(r"迭代|主动学习|多轮", user_task):
            tool = "both"
            rationale = "任务描述包含迭代优化，先用 MULTI-evolve 探索，再用 EvolvePro 精修。"
        else:
            tool = "multievolve"
            rationale = "无活性数据时，优先选择适合冷启动的 MULTI-evolve。"
        return {"tool": tool, "params": {}, "rationale": rationale}

    def plan(self, user_task: str, has_activity_data: bool = False) -> dict:
        """返回结构化计划: tool + params + rationale。"""
        if not self.client:
            return self._heuristic_plan(user_task, has_activity_data)

        system_prompt = (
            "你是蛋白质定向进化实验规划器。\n"
            "工具差异：\n"
            "1) EvolvePro：few-shot 主动学习，依赖少量活性数据，每轮推荐 10-16 个变体用于迭代优化。\n"
            "2) MULTI-evolve：一轮 ML 引导多突变体设计，适合无或少量数据的初始探索，强调协同突变。\n"
            "请根据用户任务，输出 JSON，格式严格为:"
            '{"tool":"evolvepro|multievolve|both","params":{"protein_name":"","goal":"","has_activity_data":bool},"rationale":""}'
        )
        user_prompt = (
            f"用户任务: {user_task}\n"
            f"是否提供活性数据: {has_activity_data}\n"
            "请只输出 JSON，不要额外解释。"
        )

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = resp.content[0].text
        return json.loads(text)
