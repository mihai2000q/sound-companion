"""Export of an agent run on the golden set, the input of the RAGAs runner (docs/EVALUATION.md, layer 3).

Each `answer` question goes through the real agent (`agent_events`, the same stream the UI reads). The entry keeps
the final text, the retrieved chunks (`contexts`, from the `citations` events) and the results of the music tools
(`tool_results`) apart, so a later scorer can pass them to RAGAs either way (decision pending in story 16).
Questions the agent should not answer (clarify, decline) are left out, because they have no contexts to score."""

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from app.agent.streaming import agent_events
from app.rag.evaluation import GoldenQuestion
from app.tools.delimit import unwrap_tool_result

SEARCH_TOOL = "search_knowledge_base"


@dataclass
class ExportEntry:
    id: str
    question: str
    answer: str
    contexts: list[str]  # text of every chunk the searches returned, in order, each once
    tool_results: list[dict]  # music tool calls: {"name", "args", "content"}, never search results
    reference: str
    queries: list[str] = field(default_factory=list)  # every query the searches ran
    cost: float = 0.0  # credits of this question
    error: str | None = None  # the agent run failed, the entry is kept so the run is complete


async def collect(events) -> dict:
    """Fold the events of one turn into the parts of an entry."""
    tokens: list[str] = []
    contexts: dict[str, str] = {}  # chunk id -> text, so the same chunk found twice counts once
    calls: dict[str, dict] = {}
    tool_results: list[dict] = []
    queries: list[str] = []
    cost, error = 0.0, None
    async for event in events:
        kind = event["type"]
        if kind == "token":
            tokens.append(event["text"])
        elif kind == "citations":
            for item in event["items"]:
                contexts.setdefault(item["id"], item["content"])
        elif kind == "queries":
            queries.extend(q for q in event["items"] if q not in queries)
        elif kind == "tool_call":
            calls[event["id"]] = event
        elif kind == "tool_result" and event["name"] != SEARCH_TOOL:
            call = calls.get(event["id"], {})
            tool_results.append(
                {"name": event["name"], "args": call.get("args", {}), "content": unwrap_tool_result(event["content"])}
            )
        elif kind == "usage":
            cost = event["cost"]  # the turn's cost so far, the last one is the total
        elif kind == "error":
            error = event["message"] if error is None else error
    return {
        "answer": "".join(tokens), "contexts": list(contexts.values()), "tool_results": tool_results,
        "queries": queries, "cost": cost, "error": error,
    }


async def export_question(agent, question: GoldenQuestion, ledger=None) -> ExportEntry:
    """One question in its own thread, so no answer sees another's history."""
    events = agent_events(agent, str(uuid.uuid4()), question.question, ledger)
    return ExportEntry(id=question.id, question=question.question, reference=question.reference_answer, **await collect(events))


def answerable(questions: list[GoldenQuestion]) -> tuple[list[GoldenQuestion], list[str]]:
    """The questions to export and the ids left out (the agent should clarify or decline them)."""
    kept = [q for q in questions if q.expected_behaviour == "answer"]
    return kept, [q.id for q in questions if q.expected_behaviour != "answer"]


async def export_run(agent, questions: list[GoldenQuestion], ledger=None) -> list[ExportEntry]:
    return [await export_question(agent, q, ledger) for q in questions]


def build_export(settings: dict, entries: list[ExportEntry], skipped: list[str], when: datetime | None = None) -> dict:
    when = when or datetime.now()
    return {
        "timestamp": when.strftime("%Y-%m-%dT%H-%M-%S"),
        "settings": settings,
        "skipped": skipped,
        "cost": sum(e.cost for e in entries),
        "entries": [asdict(e) for e in entries],
    }


def save_export(export: dict, directory: Path) -> Path:
    """Write `<timestamp>.json`. A saved run is never overwritten."""
    import json

    path = directory / f"{export['timestamp']}.json"
    if path.exists():
        raise FileExistsError(f"{path.name} already exists, try again in a second")
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(export, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
