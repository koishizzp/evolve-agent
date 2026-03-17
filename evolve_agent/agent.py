"""High-level orchestrator for evolve-agent."""
from __future__ import annotations

from typing import Any

from evolve_agent.planner import EvolvePlanner
from evolve_agent.reasoner import ResultReasoner
from evolve_agent.service import EvolutionService
from evolve_agent.settings import Settings
from evolve_agent.utils import validate_fasta


class EvolveAgent:
    """Natural-language protein engineering agent."""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.settings = Settings.from_env(config_path)
        self.service = EvolutionService(self.settings)
        self.planner = EvolvePlanner(self.settings)
        self.reasoner = ResultReasoner(self.settings)

    def run_with_details(
        self,
        user_input: str,
        fasta_path: str,
        activity_csv_path: str | None = None,
        strategy: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not validate_fasta(fasta_path):
            return {
                "success": False,
                "error": f"Invalid FASTA file: {fasta_path}",
                "request": {
                    "task": user_input,
                    "fasta_path": fasta_path,
                    "activity_csv_path": activity_csv_path,
                },
            }

        if strategy:
            plan = {
                "action": "execute",
                "tool": strategy,
                "params": {
                    "fasta_path": fasta_path,
                    "activity_csv_path": activity_csv_path,
                    **(params or {}),
                },
                "needs_input": False,
                "question": None,
                "rationale": "CLI explicit strategy override.",
            }
        else:
            plan = self.planner.plan(
                user_input,
                self.service.available_tools(),
                previous_request={
                    "fasta_path": fasta_path,
                    "activity_csv_path": activity_csv_path,
                    **(params or {}),
                },
            )

        if plan.get("needs_input"):
            return {
                "success": False,
                "error": str(plan.get("question") or "Missing required input."),
                "request": {"task": user_input, "fasta_path": fasta_path, "activity_csv_path": activity_csv_path},
                "operation_plan": plan,
            }

        return self.service.execute_plan(
            {
                "tool": plan["tool"],
                "task": user_input,
                "params": {
                    "fasta_path": fasta_path,
                    "activity_csv_path": activity_csv_path,
                    **(params or {}),
                    **dict(plan.get("params") or {}),
                },
                "rationale": plan.get("rationale"),
            }
        )

    def run(
        self,
        user_input: str,
        fasta_path: str,
        activity_csv_path: str | None = None,
        strategy: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        result = self.run_with_details(
            user_input=user_input,
            fasta_path=fasta_path,
            activity_csv_path=activity_csv_path,
            strategy=strategy,
            params=params,
        )
        if not result.get("success"):
            return str(result.get("error") or "Execution failed.")
        return self.service.format_execution_reply(result)

    @property
    def config(self) -> dict[str, Any]:
        return self.settings.to_agent_config()
