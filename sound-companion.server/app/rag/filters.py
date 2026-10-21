"""Metadata filters for `PGVectorStore`. `topics` is a pipe-delimited TEXT column (`|a|b|`), so a
topic is matched with `$like '%|topic|%'`: the pipes keep `form` from matching `formal`."""

from typing import Literal


def topic_filter(topics: list[str], match: Literal["any", "all"] = "all") -> dict:
    """Chunks tagged with one topic, any of several, or all of several."""
    clauses = [{"topics": {"$like": f"%|{topic}|%"}} for topic in topics]
    if len(clauses) == 1:
        return clauses[0]
    return {"$or" if match == "any" else "$and": clauses}


def combine(*filters: dict | None) -> dict | None:
    """AND the given filters together, skipping the empty ones."""
    present = [f for f in filters if f]
    if not present:
        return None
    return present[0] if len(present) == 1 else {"$and": present}
