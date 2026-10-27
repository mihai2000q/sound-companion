import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.rag.embeddings import OpenRouterEmbeddings
from app.rag.retriever import Filters, RetrievedChunk
from app.rag.vector_store import CHUNKS_TABLE, HnswIterative

RRF_CONSTANT = 60
CANDIDATES = 20  # taken from each half before fusing

QUERY = """
WITH vec AS (
  SELECT langchain_id AS id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(qvec)s::vector) AS r
  FROM {table}
  WHERE {where}
  ORDER BY embedding <=> %(qvec)s::vector
  LIMIT %(candidates)s
), kw AS (
  SELECT langchain_id AS id, ROW_NUMBER() OVER (ORDER BY ts_rank(content_tsv, q) DESC) AS r
  FROM {table}, websearch_to_tsquery('english', %(qtext)s) q
  WHERE content_tsv @@ q AND {where}
  ORDER BY ts_rank(content_tsv, q) DESC
  LIMIT %(candidates)s
)
SELECT c.langchain_id::text AS id, c.content, c.title, c.section, c.url, c.license, c.revision_id,
       c.source_type, c.topics, c.aliases,
       COALESCE(1.0 / (%(rrf)s + vec.r), 0) + COALESCE(1.0 / (%(rrf)s + kw.r), 0) AS score
FROM {table} c
LEFT JOIN vec ON vec.id = c.langchain_id
LEFT JOIN kw ON kw.id = c.langchain_id
WHERE vec.id IS NOT NULL OR kw.id IS NOT NULL
ORDER BY score DESC, c.langchain_id
LIMIT %(k)s
"""

# `topics` is the pipe-delimited column (`|a|b|`), see app/rag/filters.py
FILTER_WHERE = """(%(source_type)s::text IS NULL OR source_type = %(source_type)s)
  AND (%(title)s::text IS NULL OR title = %(title)s)
  AND (cardinality(%(topics)s::text[]) = 0 OR topics LIKE {quantifier} (%(topics)s::text[]))"""


class HybridRetriever:
    """Dense and keyword search over the chunk table, fused with reciprocal rank fusion. Our own
    SQL through psycopg (docs/DATABASE-SCHEMA.md), and the same `Filters` as `VectorRetriever`.
    `score` is the RRF score, not a similarity."""

    def __init__(
        self,
        embeddings: OpenRouterEmbeddings,
        conninfo: str,
        table: str = CHUNKS_TABLE,
        candidates: int = CANDIDATES,
    ) -> None:
        self._embeddings = embeddings
        self._conninfo = conninfo
        self._table = table
        self._candidates = candidates

    @classmethod
    def from_settings(cls) -> "HybridRetriever":
        embeddings = OpenRouterEmbeddings(
            settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_embedding_model
        )
        return cls(embeddings, settings.database_url)

    @property
    def embedding_cost(self) -> float:
        """Credits spent embedding queries so far, 0 when the embeddings do not report cost."""
        return getattr(self._embeddings, "cost", 0.0)

    def retrieve(self, query: str, k: int = 5, filters: Filters | None = None) -> list[RetrievedChunk]:
        filters = filters or Filters()
        quantifier = "ANY" if filters.topic_match == "any" else "ALL"
        sql = QUERY.format(table=self._table, where=FILTER_WHERE.format(quantifier=quantifier))
        params = {
            "qvec": "[" + ",".join(str(x) for x in self._embeddings.embed_query(query)) + "]",
            "qtext": query,
            "k": k,
            "candidates": self._candidates,
            "rrf": RRF_CONSTANT,
            "source_type": filters.source_type,
            "title": filters.title,
            "topics": [f"%|{like_escape(topic)}|%" for topic in filters.topics],
        }
        # SET LOCAL lasts for this transaction, so the dense half sees the iterative scan setting
        with psycopg.connect(self._conninfo, row_factory=dict_row) as connection:
            for setting in HnswIterative().to_parameter():
                connection.execute(f"SET LOCAL {setting}")
            rows = connection.execute(sql, params).fetchall()
        return [to_chunk(row) for row in rows]


def like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def to_chunk(row: dict) -> RetrievedChunk:
    return RetrievedChunk(
        id=row["id"],
        content=row["content"],
        score=float(row["score"]),
        title=row["title"],
        section=row["section"],
        url=row["url"],
        license=row["license"],
        revision_id=row["revision_id"],
        source_type=row["source_type"],
        topics=[t for t in row["topics"].split("|") if t],
        aliases=[a for a in row["aliases"].split("|") if a],
    )
