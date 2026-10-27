"""The request limits of docs/SECURITY.md, all checked before any model call."""
import math
import re
import time
import unicodedata
from collections import deque
from collections.abc import Callable

MAX_MESSAGE_LENGTH = 1000
RATE_LIMIT = 10  # requests per window, per process
RATE_WINDOW_SECONDS = 60
MAX_TOOL_CALLS = 8  # per request
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"  # what `crypto.randomUUID()` makes


def clean_message(text: str) -> str:
    """Reject control characters (newline and tab are fine), then collapse runs of spaces and blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in text):
        raise ValueError("message must not contain control characters")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class RateLimiter:
    """Sliding window over the whole process (one user, no authentication). `retry_after` is 0 when the request may go on."""

    def __init__(self, limit: int = RATE_LIMIT, window: float = RATE_WINDOW_SECONDS, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.hits: deque[float] = deque()

    def retry_after(self) -> int:
        now = self.clock()
        while self.hits and now - self.hits[0] >= self.window:
            self.hits.popleft()
        if len(self.hits) >= self.limit:
            return max(1, math.ceil(self.window - (now - self.hits[0])))
        self.hits.append(now)
        return 0
