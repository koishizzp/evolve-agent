from fastapi.testclient import TestClient

from api.main import app
from evolve_agent.settings import Settings


class DummyService:
    def available_tools(self):
        return ["evolvepro", "multievolve", "both"]

    def status_payload(self):
        return {
            "app_name": "Evolve Agent",
            "default_strategy": "multievolve",
            "upload_dir": "/tmp/uploads",
            "available_tools": self.available_tools(),
        }

    def run_evolution(self, fasta_path, *, task, activity_csv_path=None, strategy=None, params=None):
        return {
            "tool": strategy or "multievolve",
            "request": {
                "fasta_path": fasta_path,
                "task": task,
                "activity_csv_path": activity_csv_path,
                "strategy": strategy or "multievolve",
            },
            "success": True,
            "summary": {
                "count": 1,
                "variant_count": 1,
                "top_variant": {"mutations": "A25V", "sequence": "MKT", "score": 1.23},
            },
            "parsed_result": {"top_variant": {"mutations": "A25V", "sequence": "MKT", "score": 1.23}},
        }

    def execute_plan(self, plan):
        return self.run_evolution(
            plan["params"]["fasta_path"],
            task=plan["task"],
            activity_csv_path=plan["params"].get("activity_csv_path"),
            strategy=plan["tool"],
            params=plan.get("params"),
        )

    def format_execution_reply(self, result):
        return f"top={result['summary']['top_variant']['mutations']}"


class DummyPlanner:
    def __init__(self, plan):
        self._plan = plan

    def plan(self, message, available_tools, previous_request=None):
        return dict(self._plan)


class DummyReasoner:
    def reply(self, **kwargs):
        return "reasoned"


def test_run_evolution_endpoint(monkeypatch):
    monkeypatch.setattr("api.main.get_evolution_service", lambda: DummyService())
    client = TestClient(app)

    response = client.post(
        "/run_evolution",
        json={"fasta_path": "/tmp/query.fasta", "task": "optimize", "strategy": "multievolve"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["top_variant"]["mutations"] == "A25V"


def test_home_returns_html():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Evolve Agent" in response.text


def test_upload_endpoint(monkeypatch, tmp_path):
    settings = Settings(upload_dir=str(tmp_path / "uploads"))
    monkeypatch.setattr("api.main.get_settings", lambda: settings)
    client = TestClient(app)

    response = client.post(
        "/ui/upload",
        files={"file": ("query.fasta", b">seq\nMKT\n", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "query.fasta"
    assert payload["path"].endswith("query.fasta")
    assert (tmp_path / "uploads").exists()


def test_chat_completions_execution(monkeypatch):
    monkeypatch.setattr("api.main.get_evolution_service", lambda: DummyService())
    monkeypatch.setattr(
        "api.main.get_evolve_planner",
        lambda: DummyPlanner(
            {
                "action": "execute",
                "tool": "multievolve",
                "params": {"fasta_path": "/tmp/query.fasta"},
                "needs_input": False,
                "question": None,
                "rationale": "fallback",
            }
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "请优化 /tmp/query.fasta"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_mode"] == "execution"
    assert payload["top_variant"]["mutations"] == "A25V"
    assert payload["choices"][0]["message"]["content"] == "top=A25V"


def test_chat_completions_reasoning(monkeypatch):
    monkeypatch.setattr("api.main.get_result_reasoner", lambda: DummyReasoner())
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "为什么这个变体更好"}],
            "latest_result": DummyService().run_evolution("/tmp/query.fasta", task="optimize"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_mode"] == "reasoning"
    assert payload["choices"][0]["message"]["content"] == "reasoned"


def test_tools_endpoint(monkeypatch):
    monkeypatch.setattr("api.main.get_evolution_service", lambda: DummyService())
    client = TestClient(app)

    response = client.get("/evolve/tools")

    assert response.status_code == 200
    payload = response.json()
    assert "multievolve" in payload["tools"]


def test_ui_status_contains_upload_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("api.main.get_evolution_service", lambda: DummyService())
    monkeypatch.setattr("api.main.get_settings", lambda: Settings(upload_dir=str(tmp_path / "uploads")))
    client = TestClient(app)

    response = client.get("/ui/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["upload_dir"] == "/tmp/uploads"
