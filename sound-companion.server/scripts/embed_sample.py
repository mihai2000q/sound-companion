"""One-off check of real embeddings (Story 3, issue 16). Run from the server folder:
`uv run python -m scripts.embed_sample`.

Embeds about 50 rough chunks of the stored Corpus through OpenRouter and prints what the full run
needs: dimension, accepted batch sizes, rate-limit headers, whether `usage.cost` comes back, the
cost per chunk and the extrapolated cost for the whole Corpus. The splitter here is a rough
stand-in (800 characters, 100 overlap, per section), the real one is issue 17. Spends well under a
cent.
"""

import httpx
import psycopg

from app.config import settings

CHUNK_CHARS, OVERLAP = 800, 100
SAMPLE = 50
BATCH_PROBES = [1, 16, 64, 128, 256, 512]  # real chunks
COUNT_PROBES = [1024, 2048, 4096]  # one-word inputs, only to find a count limit cheaply


def rough_chunks(title: str, aliases: list[str], sections: list[dict]) -> list[str]:
    header = " | ".join([title, *aliases])
    chunks = []
    for section in sections:
        text, step = section["text"], CHUNK_CHARS - OVERLAP
        for start in range(0, max(len(text), 1), step):
            chunks.append(f"{header}\n{text[start:start + CHUNK_CHARS]}")
            if start + CHUNK_CHARS >= len(text):
                break
    return chunks


def embed(client: httpx.Client, inputs: list[str]) -> httpx.Response:
    return client.post(
        f"{settings.openrouter_base_url}/embeddings",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        json={"model": settings.openrouter_embedding_model, "input": inputs},
        timeout=120,
    )


def main() -> None:
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute("SELECT title, aliases, sections FROM documents ORDER BY id").fetchall()
    chunks = [c for title, aliases, sections in rows for c in rough_chunks(title, aliases, sections)]
    total_chars = sum(len(c) for c in chunks)
    print(f"Corpus: {len(rows)} documents, {len(chunks)} rough chunks, {total_chars} chars")
    stride = len(chunks) // SAMPLE
    sample = chunks[::stride][:SAMPLE]  # spread over every document

    with httpx.Client() as client:
        response = embed(client, sample)
        response.raise_for_status()
        body = response.json()
        usage = body["usage"]
        print(f"\nSample: {len(sample)} chunks -> {len(body['data'])} vectors, "
              f"dimension {len(body['data'][0]['embedding'])}")
        print(f"usage: {usage}")
        print("rate-limit headers:", {k: v for k, v in response.headers.items()
                                       if "ratelimit" in k.lower() or "retry" in k.lower()} or "none")
        tokens, cost = usage["prompt_tokens"], usage.get("cost")
        print(f"tokens per chunk: {tokens / len(sample):.1f}, chars per token: "
              f"{sum(len(c) for c in sample) / tokens:.2f}")
        if cost is not None:
            per_chunk = cost / len(sample)
            print(f"cost per chunk: {per_chunk:.3e}, whole Corpus ({len(chunks)} chunks): "
                  f"{per_chunk * len(chunks):.4f}")

        print("\nBatch probes (real chunks):")
        for size in BATCH_PROBES:
            response = embed(client, (chunks * (size // len(chunks) + 1))[:size])
            print(f"  {size}: HTTP {response.status_code}"
                  + ("" if response.is_success else f" {response.text[:200]}"))
        print("Count probes (one-word inputs):")
        for size in COUNT_PROBES:
            response = embed(client, ["note"] * size)
            print(f"  {size}: HTTP {response.status_code}"
                  + ("" if response.is_success else f" {response.text[:200]}"))


if __name__ == "__main__":
    main()
