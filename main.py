from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from evolve_agent import EvolveAgent
from evolve_agent.service import EvolutionService
from evolve_agent.settings import Settings


SUBCOMMANDS = {"run", "evolvepro", "multievolve", "status", "list-tools"}


def build_common_run_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("fasta", help="Path to FASTA file")
    parser.add_argument("--task", required=True, help="Natural-language optimization goal")
    parser.add_argument("--activity-csv", default=None, help="Optional activity CSV path")
    parser.add_argument("--json-out", default=None, help="Optional JSON output path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evolve Agent CLI")
    parser.add_argument("--config", default="config/config.yaml", help="Config yaml path")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Auto-plan and run the workflow")
    build_common_run_parser(run_parser)

    evolvepro_parser = subparsers.add_parser("evolvepro", help="Force EvolvePro execution")
    build_common_run_parser(evolvepro_parser)

    multievolve_parser = subparsers.add_parser("multievolve", help="Force MULTI-evolve execution")
    build_common_run_parser(multievolve_parser)

    subparsers.add_parser("status", help="Show runtime configuration")
    subparsers.add_parser("list-tools", help="List supported tools")
    return parser


def build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evolve Agent CLI")
    parser.add_argument("--config", default="config/config.yaml", help="Config yaml path")
    build_common_run_parser(parser)
    return parser


def _service(config_path: str) -> EvolutionService:
    settings = Settings.from_env(config_path)
    return EvolutionService(settings)


def _dump_payload(payload: Any, json_out: str | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _run(agent: EvolveAgent, args: argparse.Namespace, strategy: str | None = None) -> None:
    result = agent.run_with_details(
        user_input=args.task,
        fasta_path=args.fasta,
        activity_csv_path=args.activity_csv,
        strategy=strategy,
    )
    _dump_payload(result, getattr(args, "json_out", None))


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        args = build_legacy_parser().parse_args(argv)
        _run(EvolveAgent(config_path=args.config), args)
        return

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    if args.command == "run":
        _run(EvolveAgent(config_path=args.config), args)
        return

    if args.command == "evolvepro":
        _run(EvolveAgent(config_path=args.config), args, strategy="evolvepro")
        return

    if args.command == "multievolve":
        _run(EvolveAgent(config_path=args.config), args, strategy="multievolve")
        return

    if args.command == "status":
        _dump_payload(_service(args.config).status_payload())
        return

    if args.command == "list-tools":
        print("\n".join(_service(args.config).available_tools()))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
