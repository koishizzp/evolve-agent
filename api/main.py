"""REST and OpenAI-compatible chat API for evolve-agent."""
from __future__ import annotations

from functools import lru_cache
import logging
from pathlib import Path
import re
from secrets import token_hex
import shutil
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from evolve_agent.chat import (
    build_chat_completion,
    build_reasoning_context,
    extras_from_result,
    is_reasoning_query,
    latest_user_content,
    normalize_chat_context,
)
from evolve_agent.planner import EvolvePlanner
from evolve_agent.reasoner import ResultReasoner
from evolve_agent.service import EvolutionService
from evolve_agent.settings import get_settings

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)
app = FastAPI(title="Evolve Agent", version="0.2.0")
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


@lru_cache(maxsize=1)
def load_chat_ui() -> str:
    return Path(__file__).with_name("chat_ui.html").read_text(encoding="utf-8")


class EvolutionRequest(BaseModel):
    fasta_path: str = Field(..., description="Path to the FASTA file")
    task: str = Field(default="Optimize the protein sequence")
    activity_csv_path: str | None = None
    strategy: str | None = Field(default=None, pattern="^(evolvepro|multievolve|both)?$")
    params: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatReasoningRequest(BaseModel):
    message: str
    conversation: list[ChatMessage] = Field(default_factory=list)
    latest_result: dict[str, Any] | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    latest_result: dict[str, Any] | None = None
    reasoning_context: dict[str, Any] | None = None


def get_evolution_service() -> EvolutionService:
    return EvolutionService(get_settings())


def get_evolve_planner() -> EvolvePlanner:
    return EvolvePlanner(get_settings())


def get_result_reasoner() -> ResultReasoner:
    return ResultReasoner(get_settings())


def get_upload_dir() -> Path:
    settings = get_settings()
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_upload_name(filename: str | None) -> str:
    raw = Path(filename or "upload.bin").name
    sanitized = SAFE_FILENAME_PATTERN.sub("_", raw).strip("._")
    return sanitized or "upload.bin"


def _store_upload(file: UploadFile) -> dict[str, Any]:
    upload_dir = get_upload_dir()
    safe_name = _safe_upload_name(file.filename)
    destination = upload_dir / f"{token_hex(6)}_{safe_name}"
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        size = destination.stat().st_size
    finally:
        file.file.close()
    return {
        "filename": safe_name,
        "content_type": file.content_type or "application/octet-stream",
        "path": str(destination.resolve()),
        "size": size,
    }


def _wrap(handler):
    try:
        return handler()
    except Exception as exc:
        LOGGER.exception("Evolve API call failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return load_chat_ui()


@app.get("/chat", response_class=HTMLResponse)
def chat_page() -> str:
    return load_chat_ui()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/evolve/tools")
def list_tools() -> dict[str, Any]:
    service = get_evolution_service()
    return {"tools": service.available_tools()}


@app.get("/ui/status")
def ui_status() -> dict[str, Any]:
    settings = get_settings()
    service = get_evolution_service()
    return {
        "agent": {"status": "ok", "app_name": settings.app_name},
        "llm": {
            "configured": bool(settings.openai_api_key),
            "model": settings.llm_model,
            "base_url_configured": bool(settings.openai_base_url),
        },
        "runtime": service.status_payload(),
    }


@app.post("/ui/upload")
def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
    return _wrap(lambda: _store_upload(file))


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {"data": [{"id": "evolve-agent", "object": "model"}]}


@app.post("/run_evolution")
def run_evolution(req: EvolutionRequest) -> dict[str, Any]:
    service = get_evolution_service()
    return _wrap(
        lambda: service.run_evolution(
            req.fasta_path,
            task=req.task,
            activity_csv_path=req.activity_csv_path,
            strategy=req.strategy,
            params=req.params,
        )
    )


@app.post("/run_evolvepro")
def run_evolvepro(req: EvolutionRequest) -> dict[str, Any]:
    service = get_evolution_service()
    return _wrap(
        lambda: service.run_evolution(
            req.fasta_path,
            task=req.task,
            activity_csv_path=req.activity_csv_path,
            strategy="evolvepro",
            params=req.params,
        )
    )


@app.post("/run_multievolve")
def run_multievolve(req: EvolutionRequest) -> dict[str, Any]:
    service = get_evolution_service()
    return _wrap(
        lambda: service.run_evolution(
            req.fasta_path,
            task=req.task,
            activity_csv_path=req.activity_csv_path,
            strategy="multievolve",
            params=req.params,
        )
    )


@app.post("/chat_reasoning")
def chat_reasoning(req: ChatReasoningRequest) -> dict[str, Any]:
    reasoner = get_result_reasoner()
    return _wrap(
        lambda: {
            "reply": reasoner.reply(
                message=req.message,
                latest_result=req.latest_result,
                conversation=[item.model_dump() for item in req.conversation],
            )
        }
    )


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
    content = latest_user_content([item.model_dump() for item in req.messages])
    latest_result = normalize_chat_context(req.latest_result, req.reasoning_context)

    if is_reasoning_query(content):
        if latest_result:
            reasoner = get_result_reasoner()
            reply = reasoner.reply(
                message=content,
                latest_result=latest_result,
                conversation=[item.model_dump() for item in req.messages],
            )
            extra = extras_from_result(latest_result)
            extra["chat_mode"] = "reasoning"
            extra["reasoning_context"] = build_reasoning_context("reasoning", latest_result)
            return build_chat_completion(reply, extra=extra)

        return build_chat_completion(
            "请先执行一次演化任务，或在请求里附带 latest_result / reasoning_context。",
            extra={
                "chat_mode": "reasoning",
                "reasoning_context": build_reasoning_context("reasoning", None),
            },
        )

    planner = get_evolve_planner()
    service = get_evolution_service()
    previous_request = latest_result.get("request") if isinstance(latest_result.get("request"), dict) else {}
    plan = planner.plan(content, service.available_tools(), previous_request=previous_request)

    if plan.get("needs_input"):
        return build_chat_completion(
            str(plan.get("question") or "请补充执行所需的输入参数。"),
            extra={
                "chat_mode": "execution",
                "operation_plan": plan,
                "reasoning_context": build_reasoning_context("execution", latest_result),
            },
        )

    execution_plan = {
        "tool": plan["tool"],
        "task": content,
        "params": dict(plan.get("params") or {}),
        "rationale": plan.get("rationale"),
    }
    result = _wrap(lambda: service.execute_plan(execution_plan))
    extra = extras_from_result(result)
    extra["chat_mode"] = "execution"
    extra["operation_plan"] = plan
    extra["operation_result"] = result
    extra["reasoning_context"] = build_reasoning_context("execution", result)
    return build_chat_completion(service.format_execution_reply(result), extra=extra)
