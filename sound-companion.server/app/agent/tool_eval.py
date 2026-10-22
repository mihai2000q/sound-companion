"""Tool-calling accuracy on the tool golden file (docs/EVALUATION.md, layer 2).

Runs the agent on each question, takes the tool calls it made and scores them against the expected
calls. The scoring is plain functions over plain data, so it is tested without a model. No retrieval
happens here unless the caller passes a real `Retriever`: `StubRetriever` answers every search."""

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from app.agent.prompt import SYSTEM_PROMPT
from app.rag.eval_results import differing_settings
from app.rag.retriever import Filters, RetrievedChunk, Retriever
from app.tools.registry import build_tools

# Arguments that name things: compared ignoring case. Every other argument (notes, numbers) is exact.
CASE_INSENSITIVE = {"instrument", "scale", "direction", "source_type", "topic", "title"}
KIND = "tool-calling"


@dataclass
class ExpectedCall:
    name: str
    # Only the arguments that matter are listed. A value is a literal, or {"any_of": [...]} for accepted spellings.
    args: dict = field(default_factory=dict)


@dataclass
class ToolCase:
    id: str
    question: str
    category: str
    difficulty: str
    expected_tools: list[ExpectedCall]  # empty: the agent must call no tool


@dataclass
class CaseResult:
    id: str
    question: str
    category: str
    difficulty: str
    expected: list[dict]
    actual: list[dict]  # [{"name", "args"}] in call order
    selection_ok: bool
    args_expected: int
    args_matched: int
    error: str | None = None  # the agent run failed
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def parameters_ok(self) -> bool | None:
        """None when the case expects no arguments to check."""
        return None if self.args_expected == 0 else self.args_matched == self.args_expected


@dataclass
class Summary:
    group: str  # "overall" or a difficulty
    cases: int
    selection: float  # share of cases whose tool set is right
    parameter_cases: int  # cases that expect arguments
    parameter: float | None  # share of those with every expected argument right


def load_cases(path: Path) -> list[ToolCase]:
    return [
        ToolCase(
            id=entry["id"], question=entry["question"], category=entry["category"], difficulty=entry["difficulty"],
            expected_tools=[ExpectedCall(**call) for call in entry["expected_tools"]],
        )
        for entry in json.loads(path.read_text(encoding="utf-8"))
    ]


def value_matches(key: str, expected, actual) -> bool:
    if isinstance(expected, dict) and "any_of" in expected:
        return any(value_matches(key, option, actual) for option in expected["any_of"])
    if isinstance(expected, str) and isinstance(actual, str) and key in CASE_INSENSITIVE:
        return expected.strip().casefold() == actual.strip().casefold()
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(value_matches(key, e, a) for e, a in zip(expected, actual))
    return expected == actual


def args_matched(expected: dict, actual: dict) -> int:
    return sum(1 for key, value in expected.items() if key in actual and value_matches(key, value, actual[key]))


def score_case(case: ToolCase, calls: list[dict]) -> tuple[bool, int, int]:
    """(tool selection right, expected arguments, expected arguments matched).

    Selection compares the tool names as a multiset: order is ignored, repeated calls count. Each
    expected call is paired with the unused actual call of the same name that matches most of its
    arguments, and an expected call without a partner matches none of its arguments."""
    selection_ok = Counter(c.name for c in case.expected_tools) == Counter(c["name"] for c in calls)
    unused = list(range(len(calls)))
    expected_args = matched = 0
    for expected in case.expected_tools:
        expected_args += len(expected.args)
        candidates = [i for i in unused if calls[i]["name"] == expected.name]
        if not candidates:
            continue
        best = max(candidates, key=lambda i: args_matched(expected.args, calls[i]["args"]))
        unused.remove(best)
        matched += args_matched(expected.args, calls[best]["args"])
    return selection_ok, expected_args, matched


def tool_calls_of(messages: list) -> list[dict]:
    return [
        {"name": call["name"], "args": call["args"]}
        for message in messages
        for call in getattr(message, "tool_calls", None) or []
    ]


def tokens_of(messages: list, kind: str = "total_tokens") -> int:
    return sum((getattr(m, "usage_metadata", None) or {}).get(kind, 0) for m in messages)


def run_case(agent, case: ToolCase) -> CaseResult:
    error = None
    messages: list = []
    try:
        messages = agent.invoke({"messages": [{"role": "user", "content": case.question}]})["messages"]
    except Exception as exc:  # a failed run is a failed case, not a stopped evaluation
        error = f"{type(exc).__name__}: {exc}"
    calls = tool_calls_of(messages)
    selection_ok, expected_args, matched = score_case(case, calls)
    return CaseResult(
        id=case.id, question=case.question, category=case.category, difficulty=case.difficulty,
        expected=[asdict(c) for c in case.expected_tools], actual=calls,
        selection_ok=selection_ok and error is None, args_expected=expected_args, args_matched=matched,
        error=error, tokens=tokens_of(messages),
        input_tokens=tokens_of(messages, "input_tokens"), output_tokens=tokens_of(messages, "output_tokens"),
    )


def evaluate(agent, cases: list[ToolCase]) -> list[CaseResult]:
    return [run_case(agent, case) for case in cases]


def summarize(results: list[CaseResult]) -> list[Summary]:
    """Overall first, then one row per difficulty (easy, medium, hard, then any other)."""
    order = {"easy": 0, "medium": 1, "hard": 2}
    groups = [("overall", results)] + [
        (d, [r for r in results if r.difficulty == d])
        for d in sorted({r.difficulty for r in results}, key=lambda d: (order.get(d, 3), d))
    ]
    summaries = []
    for name, rows in groups:
        checked = [r for r in rows if r.parameters_ok is not None]
        summaries.append(Summary(
            group=name, cases=len(rows),
            selection=sum(r.selection_ok for r in rows) / len(rows),
            parameter_cases=len(checked),
            parameter=sum(bool(r.parameters_ok) for r in checked) / len(checked) if checked else None,
        ))
    return summaries


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def prompt_and_tools(retriever: Retriever) -> dict:
    """Hashes of the system prompt and of every tool description and argument schema, so two runs show
    which of them changed."""
    return {
        "prompt_sha256": sha(SYSTEM_PROMPT),
        "tools": {
            tool.name: sha(tool.description + json.dumps(tool.args, sort_keys=True))
            for tool in build_tools(retriever)
        },
    }


def build_run(label: str, settings: dict, results: list[CaseResult], when: date | None = None) -> dict:
    return {
        "kind": KIND,
        "label": label,
        "date": (when or date.today()).isoformat(),
        "settings": settings,
        "summary": [asdict(s) for s in summarize(results)],
        "cost_tokens": sum(r.tokens for r in results),
        "input_tokens": sum(r.input_tokens for r in results),
        "output_tokens": sum(r.output_tokens for r in results),
        "questions": [asdict(r) | {"parameters_ok": r.parameters_ok} for r in results],
    }


def compare(a: dict, b: dict) -> dict:
    """Change from run `a` to run `b`: the summary rows, the cases that flipped and the settings that differ."""
    in_b = {q["id"]: q for q in b["questions"]}
    rows = [
        {
            "id": q["id"],
            "selection": (q["selection_ok"], in_b[q["id"]]["selection_ok"]),
            "parameters": (q["parameters_ok"], in_b[q["id"]]["parameters_ok"]),
        }
        for q in a["questions"]
        if q["id"] in in_b
    ]
    b_summary = {s["group"]: s for s in b["summary"]}
    return {
        "summary": [(s, b_summary.get(s["group"])) for s in a["summary"]],
        "questions": rows,
        "changed": [r for r in rows if r["selection"][0] != r["selection"][1] or r["parameters"][0] != r["parameters"][1]],
        "only_in_a": [q["id"] for q in a["questions"] if q["id"] not in in_b],
        "only_in_b": [i for i in in_b if i not in {q["id"] for q in a["questions"]}],
        "settings": differing_settings(a, b),
    }


class StubRetriever:
    """Answers every search with one placeholder chunk, so the evaluation needs no database and no
    embeddings. The chunk says it is enough, so a search is not repeated for lack of results."""

    def retrieve(self, query: str, k: int = 5, filters: Filters | None = None) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                id="stub", content=f"(Evaluation stub, not real text.) The knowledge base covers: {query}. "
                "This is all there is, so answer from it without searching again.",
                score=0.9, title="Stub page", section="", url="https://example.org/stub", license="CC BY-SA 4.0",
                revision_id="0", source_type="encyclopedia",
            )
        ]
