from app.rag.rewrite import MAX_REWRITES, Rewrites, clean_rewrites, make_rewriter


class FakeModel:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.prompts = result, error, []

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt, config=None):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.result


def test_rewrites_come_from_the_model():
    model = FakeModel(Rewrites(queries=["German note names", "B-flat in Germany"]))
    assert make_rewriter(model)("What do Germans call B-flat?") == ["German note names", "B-flat in Germany"]
    assert "What do Germans call B-flat?" in model.prompts[0]


def test_model_failure_gives_no_rewrites():
    assert make_rewriter(FakeModel(error=RuntimeError("boom")))("x") == []


def test_empty_result_gives_no_rewrites():
    assert make_rewriter(FakeModel(Rewrites(queries=[])))("x") == []


def test_clean_drops_blanks_copies_of_the_query_and_extras():
    cleaned = clean_rewrites("Clarinet", ["  ", "clarinet", "B-flat clarinet", "b-flat Clarinet", "reed", "a", "b"])
    assert cleaned == ["B-flat clarinet", "reed"][:MAX_REWRITES]


class StubRetriever:
    def __init__(self, by_query):
        self.by_query = by_query

    def retrieve(self, query, k=5, filters=None):
        return self.by_query.get(query, [])


def test_rewriting_retriever_merges_and_records_the_queries():
    from app.rag.rewrite import RewritingRetriever
    from tests.test_search_tool import chunk_with_id

    inner = StubRetriever({"q": [chunk_with_id("a")], "r": [chunk_with_id("b"), chunk_with_id("a")]})
    retriever = RewritingRetriever(inner, lambda query: ["r"])
    assert [c.id for c in retriever.retrieve("q", 5)] == ["a", "b"]
    assert retriever.queries_by_question == {"q": ["q", "r"]}
