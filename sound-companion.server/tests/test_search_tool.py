from app.rag.retriever import Filters, RetrievedChunk
from app.tools.search import NOT_FOUND, make_search_tool, search_knowledge_base


class FakeRetriever:
    def __init__(self, chunks=()):
        self.chunks = list(chunks)
        self.calls = []

    def retrieve(self, query, k=5, filters=None):
        self.calls.append((query, k, filters))
        return self.chunks


def chunk(section="Design"):
    return RetrievedChunk(
        id="1", content="Cor anglais\nThe cor anglais is a double reed.", score=0.8312, title="Cor anglais",
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
    assert text.startswith("[Cor anglais > Design]")
    assert "https://example.org/Cor_anglais" in text
    assert "CC BY-SA 4.0" in text and "0.831" in text
    assert "The cor anglais is a double reed." in text


def test_lead_chunk_has_no_section_arrow():
    assert search_knowledge_base(FakeRetriever([chunk("")]), "x").startswith("[Cor anglais]")


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
