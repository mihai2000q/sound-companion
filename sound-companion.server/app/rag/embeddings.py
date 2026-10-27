import httpx
from langchain_core.embeddings import Embeddings

from app.db.usage import Usage, record_usage

BATCH_SIZE = 100  # the endpoint accepts up to 2,048 inputs (docs/research/embeddings-sample.md)


class OpenRouterEmbeddings(Embeddings):
    """Embeddings straight from OpenRouter's `POST /embeddings`, because `OpenAIEmbeddings` returns
    only vectors and the response body is where `usage.cost` is (decision 50). The totals add up
    over the instance's life, so a run can log what it spent."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._client = httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=120
        )
        self._model = model
        self.tokens = 0
        self.cost = 0.0  # credits

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(self._embed(texts[start:start + BATCH_SIZE]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post("/embeddings", json={"model": self._model, "input": texts})
        response.raise_for_status()
        body = response.json()
        usage = body["usage"]
        self.tokens += usage["total_tokens"]
        self.cost += usage["cost"]
        record_usage(  # this call's cost, not the running total; a no-op outside a request
            Usage("embed", self._model, usage.get("prompt_tokens", usage["total_tokens"]), 0, usage["cost"])
        )
        # `data` carries an `index` per vector, so do not rely on the order.
        return [item["embedding"] for item in sorted(body["data"], key=lambda item: item["index"])]
