from app.rag.retriever import Filters, RetrievedChunk
from app.tools.search import NOT_FOUND, make_search_tool, search_knowledge_base


class FakeRetriever:
    def __init__(self, chunks=()):
        self.chunks = list(chunks)
        self.calls = []

    def retrieve(self, query, k=5, filters=None):
        self.calls.append((query, k, filters))
        return self.chunks


def chunk(section="Design", id="1"):
    return RetrievedChunk(
        id=id, content="Cor anglais\nThe cor anglais is a double reed.", score=0.8312, title="Cor anglais",
        section=section, url="https://example.org/Cor_anglais", license="CC BY-SA 4.0", revision_id="1",
        source_type="encyclopedia",
    )


def test_filters_are_mapped():
    fake = FakeRetriever([chunk()])
    search_knowledge_base(fake, " English horn ", "textbook", "Woodwinds", "Cor anglais", k=3)
    query, k, filters = fake.calls[0]
    assert (query, k) == ("English horn", 3)
    assert filters == Filters(source_type="textbook", topics=("woodwinds",), title="Cor anglais")


def test_no_filters_given():
    fake = FakeRetriever([chunk()])
    search_knowledge_base(fake, "cadence")
    assert fake.calls[0][2] == Filters()


def test_chunk_format_has_what_a_citation_needs():
    text = search_knowledge_base(FakeRetriever([chunk()]), "English horn")
    assert text.startswith('<document source="Cor anglais > Design">\n[Cor anglais > Design]')
    assert "https://example.org/Cor_anglais" in text
    assert "CC BY-SA 4.0" in text and "0.831" in text
    assert "The cor anglais is a double reed." in text


def test_lead_chunk_has_no_section_arrow():
    assert search_knowledge_base(FakeRetriever([chunk("")]), "x").startswith('<document source="Cor anglais">\n[Cor anglais]')


def test_empty_result_is_explicit():
    assert search_knowledge_base(FakeRetriever(), "zzz") == NOT_FOUND


def test_invalid_arguments_return_errors_without_searching():
    fake = FakeRetriever([chunk()])
    assert search_knowledge_base(fake, "  ").startswith("Error")
    assert fake.calls == []
    tool = make_search_tool(fake)
    message = tool.invoke({"query": "x", "source_type": "blog"})  # validated by LangChain, not raised
    assert message.startswith("Error") and "encyclopedia" in message
    assert fake.calls == []


def test_tool_is_named_and_described_for_the_agent():
    tool = make_search_tool(FakeRetriever([chunk()]))
    assert tool.name == "search_knowledge_base"
    assert "Do NOT use it for calculations" in tool.description
    assert set(tool.args) == {"query", "source_type", "topic", "title"}
    assert "Cor anglais" in tool.invoke({"query": "English horn"})


def stream_events(chunks, replies=None):
    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import InMemorySaver

    from app.agent.agent import build_agent
    from app.agent.streaming import agent_events
    from tests.test_chat_api import StreamingToolModel
    import asyncio

    call = AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "clarinet"}, "id": "1"}])
    model = StreamingToolModel(messages=iter([call, AIMessage("A reed vibrates.")]), seen=[], bound=[])
    agent = build_agent(model, FakeRetriever(chunks), InMemorySaver())

    async def collect():
        return [event async for event in agent_events(agent, "t", "How does a clarinet work?")]

    return asyncio.run(collect())


def test_citations_and_queries_arrive_between_tool_call_and_tool_result():
    events = stream_events([chunk("Design", "1"), chunk("History", "2")])
    types = [e["type"] for e in events if e["type"] != "token"]
    assert types == ["tool_call", "citations", "queries", "tool_result", "done"]
    citations = next(e for e in events if e["type"] == "citations")
    stored = chunk("Design")
    assert citations["items"][0] == {
        "id": stored.id, "title": stored.title, "section": "Design", "url": stored.url,
        "score": stored.score, "license": stored.license, "content": stored.content,
    }
    assert [i["section"] for i in citations["items"]] == ["Design", "History"]
    assert next(e for e in events if e["type"] == "queries")["items"] == ["clarinet"]


def test_empty_search_emits_no_citations_or_queries():
    types = [e["type"] for e in stream_events([])]
    assert "citations" not in types and "queries" not in types


class PerQueryRetriever:
    def __init__(self, by_query):
        self.by_query = by_query
        self.calls = []

    def retrieve(self, query, k=5, filters=None):
        self.calls.append(query)
        return self.by_query.get(query, [])


def chunk_with_id(id, score=0.5):
    stored = chunk()
    stored.id, stored.score = id, score
    return stored


def test_rewrites_are_searched_and_merged_without_duplicates():
    fake = PerQueryRetriever({
        "middle C": [chunk_with_id("a"), chunk_with_id("b")],
        "C4": [chunk_with_id("b"), chunk_with_id("c")],
    })
    events = []
    text = search_knowledge_base(fake, "middle C", k=3, emit=events.append, rewriter=lambda q: ["C4"])
    assert fake.calls == ["middle C", "C4"]
    assert text.count("[Cor anglais") == 3
    citations = next(e for e in events if e["type"] == "citations")
    assert [i["id"] for i in citations["items"]] == ["a", "b", "c"]
    assert next(e for e in events if e["type"] == "queries")["items"] == ["middle C", "C4"]


def test_merge_keeps_k_chunks_overall():
    fake = PerQueryRetriever({"q": [chunk_with_id("a"), chunk_with_id("b")], "r": [chunk_with_id("c"), chunk_with_id("d")]})
    events = []
    search_knowledge_base(fake, "q", k=2, emit=events.append, rewriter=lambda q: ["r"])
    assert [i["id"] for i in events[0]["items"]] == ["a", "c"]


def test_without_a_rewriter_only_the_query_is_searched():
    fake = PerQueryRetriever({"q": [chunk_with_id("a")]})
    search_knowledge_base(fake, "q")
    assert fake.calls == ["q"]
