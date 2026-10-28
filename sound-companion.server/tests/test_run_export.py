import asyncio
import json
from datetime import datetime

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent
from app.agent.run_export import answerable, build_export, collect, export_run, save_export
from app.rag.evaluation import GoldenQuestion
from tests.test_chat_api import StreamingToolModel
from tests.test_search_tool import FakeRetriever, chunk


def golden(id="q01", behaviour="answer") -> GoldenQuestion:
    return GoldenQuestion(
        id=id, question="How does a cor anglais work?", category="c", difficulty="easy", expected_sources=[],
        expected_behaviour=behaviour, reference_answer="A double reed vibrates.",
    )


def call(name: str, args: dict, id: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": id}])


def agent_for(replies, chunks=()):
    return build_agent(StreamingToolModel(messages=iter(replies), seen=[], bound=[]), FakeRetriever(chunks), InMemorySaver())


def test_chunks_and_music_tool_results_are_stored_apart():
    agent = agent_for(
        [
            call("search_knowledge_base", {"query": "cor anglais"}, "1"),
            call("note_frequency", {"note": "A4"}, "2"),
            AIMessage("A reed vibrates, and A4 is 440 Hz."),
        ],
        [chunk()],
    )
    [entry] = asyncio.run(export_run(agent, [golden()]))
    assert entry.contexts == ["Cor anglais\nThe cor anglais is a double reed."]
    assert [(r["name"], r["args"]) for r in entry.tool_results] == [("note_frequency", {"note": "A4"})]
    assert "440" in entry.tool_results[0]["content"] and "<tool_result" not in entry.tool_results[0]["content"]
    assert entry.answer.strip() == "A reed vibrates, and A4 is 440 Hz."
    assert entry.reference == "A double reed vibrates." and entry.queries == ["cor anglais"] and entry.error is None


def test_a_chunk_found_twice_counts_once_and_an_answer_without_a_search_has_no_contexts():
    twice = agent_for(
        [call("search_knowledge_base", {"query": "a"}, "1"), call("search_knowledge_base", {"query": "b"}, "2"), AIMessage("ok")],
        [chunk()],
    )
    assert len(asyncio.run(export_run(twice, [golden()]))[0].contexts) == 1
    [entry] = asyncio.run(export_run(agent_for([AIMessage("Which guitar?")]), [golden()]))
    assert entry.contexts == [] and entry.tool_results == []


def test_every_question_gets_its_own_thread():
    agent = agent_for([AIMessage("one"), AIMessage("two")])
    entries = asyncio.run(export_run(agent, [golden("q01"), golden("q02")]))
    assert [e.answer.strip() for e in entries] == ["one", "two"]


def test_clarify_and_decline_questions_are_skipped():
    kept, skipped = answerable([golden("q01"), golden("q15", "clarify"), golden("q20", "decline")])
    assert [q.id for q in kept] == ["q01"] and skipped == ["q15", "q20"]


def test_a_failed_run_keeps_its_entry_with_the_error():
    async def events():
        yield {"type": "token", "text": "partial"}
        yield {"type": "error", "code": "agent_error", "message": "boom"}

    result = asyncio.run(collect(events()))
    assert result["answer"] == "partial" and result["error"] == "boom"


def test_the_export_is_saved_once_per_timestamp(tmp_path):
    export = build_export({"model": "m"}, [], ["q15"], datetime(2026, 10, 28, 9, 30, 5))
    path = save_export(export, tmp_path / "runs")
    assert path.name == "2026-10-28T09-30-05.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["skipped"] == ["q15"] and saved["entries"] == []
    with pytest.raises(FileExistsError):
        save_export(export, tmp_path / "runs")
