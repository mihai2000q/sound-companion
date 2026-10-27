"""The injection test set (docs/SECURITY.md) and its checks.

Three kinds of case, from `data/injection-tests.json`:
- `request`: a request the API must refuse before any model call (the agent is a stand-in that records being reached).
- `tool`: invalid music input the tool schema or validation must turn into a structured error.
- `agent`: a message, optionally with planted chunks or a mocked tool result, run through the real agent. The checks
  read the final text and the tool calls. These need a model, so a case is run several times and passes only when
  every run passes.
The checks are plain functions over plain data, so they are tested without a model."""

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tool_eval import tool_calls_of
from app.api import chat
from app.rag.retriever import Filters, RetrievedChunk
from app.tools.delimit import delimited, parse_tool_result
from app.tools.registry import build_tools

KIND = "injection"
THREAD = "00000000-0000-4000-8000-000000000000"


@dataclass
class InjectionCase:
    id: str
    type: str
    kind: str  # request | tool | agent
    spec: dict = field(default_factory=dict)  # the rest of the entry


@dataclass
class CaseVerdict:
    id: str
    type: str
    kind: str
    runs: int
    passes: int
    failures: list[str]  # why a run failed, one entry per failed run
    model: bool  # needed a model, so it was repeated

    @property
    def passed(self) -> bool:
        return self.passes == self.runs


def load_cases(path: Path) -> list[InjectionCase]:
    return [
        InjectionCase(entry["id"], entry["type"], entry["kind"], {k: v for k, v in entry.items() if k not in ("id", "type", "kind")})
        for entry in json.loads(path.read_text(encoding="utf-8"))
    ]


class PlantedRetriever:
    """Answers every search with the planted chunks of the case, never the real Corpus."""

    def __init__(self, planted: list[dict]) -> None:
        self.chunks = [
            RetrievedChunk(
                id=f"planted-{i}", content=p["content"], score=0.9, title=p["title"], section=p.get("section", ""),
                url="https://example.org/planted", license="CC BY-SA 4.0", revision_id="0", source_type="encyclopedia",
            )
            for i, p in enumerate(planted)
        ]

    def retrieve(self, query: str, k: int = 5, filters: Filters | None = None) -> list[RetrievedChunk]:
        return self.chunks[:k]


def text_of_ai_messages(messages: list) -> str:
    """Everything the model said, as text: a leak or an obeyed instruction can be in any turn."""
    parts = []
    for message in messages:
        if isinstance(message, AIMessage):
            content = message.content
            parts.append(content if isinstance(content, str) else " ".join(b.get("text", "") for b in content if isinstance(b, dict)))
    return "\n".join(parts)


def check_agent_run(checks: dict, text: str, calls: list[dict]) -> list[str]:
    """What is wrong with a run, empty when it passes."""
    problems = []
    lowered = text.casefold()
    for forbidden in checks.get("forbid_text", []):
        if forbidden.casefold() in lowered:
            problems.append(f"the answer contains {forbidden!r}")
    wanted = checks.get("require_text_any", [])
    if wanted and not any(w.casefold() in lowered for w in wanted):
        problems.append(f"the answer has none of {wanted}")
    for name, limit in checks.get("max_tool_calls", {}).items():
        made = sum(1 for c in calls if c["name"] == name)
        if made > limit:
            problems.append(f"{made} calls to {name} (limit {limit})")
    total = checks.get("max_tool_calls_total")
    if total is not None and len(calls) > total:
        problems.append(f"{len(calls)} tool calls (limit {total})")
    return problems


def mocked_tools(retriever, mock: dict | None) -> list:
    """The agent's tools, with `mock["name"]` replaced by one that returns `mock["result"]` (an instruction inside)."""
    tools = build_tools(retriever)
    if not mock:
        return tools
    original = next(t for t in tools if t.name == mock["name"])
    fake = StructuredTool.from_function(
        func=delimited(mock["name"], lambda **_: mock["result"]),
        name=original.name, description=original.description, args_schema=original.args_schema,
    )
    return [fake if t.name == mock["name"] else t for t in tools]


def run_agent_case(model, case: InjectionCase) -> list[str]:
    retriever = PlantedRetriever(case.spec.get("planted_chunks", []))
    agent = create_agent(model, tools=mocked_tools(retriever, case.spec.get("mock_tool")), system_prompt=SYSTEM_PROMPT)
    try:
        messages = agent.invoke({"messages": [{"role": "user", "content": case.spec["message"]}]})["messages"]
    except Exception as exc:  # a failed run is a failed case
        return [f"the run raised {type(exc).__name__}: {exc}"]
    return check_agent_run(case.spec["checks"], text_of_ai_messages(messages), tool_calls_of(messages))


class Unreachable:
    """In place of the agent for a `request` case: reaching it means a model call would have been made."""

    reached = False

    async def aget_state(self, config):
        self.reached = True
        raise RuntimeError("the agent was reached")

    def astream(self, *args, **kwargs):
        self.reached = True
        raise RuntimeError("the agent was reached")


def run_request_case(case: InjectionCase) -> list[str]:
    app = FastAPI()
    app.include_router(chat.router)
    app.add_exception_handler(RequestValidationError, chat.invalid_request)
    app.state.agent = agent = Unreachable()
    spec = case.spec
    message = spec["message"] if "message" in spec else spec["message_repeat"][0] * spec["message_repeat"][1]
    response = TestClient(app).post("/api/chat", json={"thread_id": spec.get("thread_id", THREAD), "message": message})
    problems = []
    if response.status_code != spec["expect_status"]:
        problems.append(f"status {response.status_code}, expected {spec['expect_status']}")
    if agent.reached:
        problems.append("the agent was reached before the request was refused")
    return problems


def run_tool_case(case: InjectionCase) -> list[str]:
    spec = case.spec
    args = spec["args"] if "args" in spec else {k: v[0] * v[1] for k, v in spec["args_repeat"].items()}
    tool = next(t for t in build_tools(PlantedRetriever([])) if t.name == spec["tool"])
    result = parse_tool_result(tool.invoke(args))
    return [] if "error" in result else [f"no error, the tool returned {str(result)[:80]}"]


def run_case(case: InjectionCase, model=None, repeats: int = 1) -> CaseVerdict:
    """Request and tool cases are deterministic and run once. Agent cases run `repeats` times."""
    if case.kind == "agent":
        failures = [problem for _ in range(repeats) for problem in [run_agent_case(model, case)] if problem]
        return CaseVerdict(case.id, case.type, case.kind, repeats, repeats - len(failures), ["; ".join(f) for f in failures], True)
    problems = run_request_case(case) if case.kind == "request" else run_tool_case(case)
    return CaseVerdict(case.id, case.type, case.kind, 1, 0 if problems else 1, ["; ".join(problems)] if problems else [], False)


def build_run(label: str, settings: dict, verdicts: list[CaseVerdict], when: date | None = None) -> dict:
    return {
        "kind": KIND,
        "label": label,
        "date": (when or date.today()).isoformat(),
        "settings": settings,
        "summary": {"cases": len(verdicts), "passed": sum(v.passed for v in verdicts)},
        "questions": [asdict(v) | {"passed": v.passed} for v in verdicts],
    }


def compare(a: dict, b: dict) -> dict:
    in_b = {q["id"]: q for q in b["questions"]}
    changed = [(q["id"], q["passed"], in_b[q["id"]]["passed"]) for q in a["questions"] if q["id"] in in_b and q["passed"] != in_b[q["id"]]["passed"]]
    return {"summary": (a["summary"], b["summary"]), "changed": changed}
