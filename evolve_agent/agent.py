"""EvolveAgent 主逻辑。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from anthropic import Anthropic

from evolve_agent.parser import OutputParser
from evolve_agent.planner import EvolvePlanner
from evolve_agent.tools import EvolveProTool, MultiEvolveTool
from evolve_agent.utils import validate_fasta


class EvolveAgent:
    """自然语言驱动蛋白质定向进化工具。"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.planner = EvolvePlanner(self.config)
        self.evolvepro = EvolveProTool(self.config)
        self.multievolve = MultiEvolveTool(self.config)
        self.parser = OutputParser()

        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm = Anthropic(api_key=api_key) if api_key else None

    @staticmethod
    def _load_config(config_path: str) -> dict:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _summarize(self, parsed_result: dict, plan: dict, user_input: str) -> str:
        """调用 LLM 生成用户友好总结。"""
        if not self.llm:
            top = parsed_result.get("top_variant", {})
            return (
                f"任务: {user_input}\n"
                f"策略: {plan.get('tool')}\n"
                f"推荐 Top 变体: {top}\n"
                "建议下一步：合成 Top 变体并进行湿实验验证，随后将新数据回流继续优化。"
            )

        prompt = (
            "请基于以下执行结果，输出中文摘要：包含推荐突变体、预期改善、下一步建议。\n"
            f"计划: {json.dumps(plan, ensure_ascii=False)}\n"
            f"解析结果: {json.dumps(parsed_result, ensure_ascii=False)}\n"
            f"用户任务: {user_input}"
        )
        resp = self.llm.messages.create(
            model=self.config["model"],
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    def run(self, user_input: str, fasta_path: str, activity_csv_path: str | None = None) -> str:
        """执行端到端流程。"""
        if not validate_fasta(fasta_path):
            return "输入 FASTA 文件无效，请检查格式是否正确。"

        plan = self.planner.plan(user_input, has_activity_data=bool(activity_csv_path))
        tool_choice = plan.get("tool", "multievolve")

        payload = {
            "fasta_path": fasta_path,
            "activity_csv_path": activity_csv_path,
            "task": user_input,
            "params": plan.get("params", {}),
        }

        if tool_choice == "evolvepro":
            result = self.evolvepro.run(payload)
        elif tool_choice == "both":
            first = self.multievolve.run(payload)
            second = self.evolvepro.run(payload)
            if second.get("success"):
                result = second
            else:
                result = first
        else:
            result = self.multievolve.run(payload)

        if not result.get("success"):
            return (
                f"执行失败：{result.get('error')}\n"
                "排查建议：1) 检查 conda run 环境名称；2) 检查工具路径；3) 校验输入文件列名与格式。"
            )

        parsed = self.parser.parse(tool_choice, result.get("result_files", []))
        return self._summarize(parsed, plan, user_input)
