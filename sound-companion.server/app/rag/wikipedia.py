import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import httpx

REST_HTML_URL = "https://en.wikipedia.org/api/rest_v1/page/html/"
# Wikimedia User-Agent policy: client name, version, contact and no generic agent
# (docs/research/ingestion-sources-facts.md).
USER_AGENT = (
    "SoundCompanionBot/0.1 (https://github.com/cristimihailfilipgreenbay/sound-companion) "
    f"httpx/{httpx.__version__}"
)
MIN_INTERVAL_SECONDS = 1.0  # serial requests, well under the 200 per minute limit for bots
MAX_ATTEMPTS = 4
DEFAULT_RETRY_SECONDS = 5.0  # the policy page's wait when a 429 has no Retry-After

_REVISION_IN_ETAG = re.compile(r'^(?:W/)?"(\d+)/')
# A redirect lands on `/w/rest.php/v1/page/<title>/html`, a direct hit stays on `/page/html/<title>`.
_TITLE_IN_PATH = re.compile(r"/page/(?:html/(.+)|(.+)/html)$")


@dataclass
class CachedPage:
    """One fetched page. `canonical_title` and `revision_id` are None when the page is missing."""

    requested_title: str
    canonical_title: str | None
    revision_id: int | None
    url: str | None
    fetched_at: str
    status: str  # "ok" or "missing"

    @property
    def redirect_alias(self) -> str | None:
        """The name the Seed entry used, when Wikipedia redirected it to another title."""
        if self.canonical_title and self.requested_title != self.canonical_title:
            return self.requested_title
        return None


class WikipediaCache:
    """REST HTML pages cached as `<slug>.html` plus `<slug>.json`, keyed by the requested title.

    Keying by the requested title means a re-run makes no request even for redirected entries.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _stem(self, title: str) -> Path:
        return self.cache_dir / quote(title.replace(" ", "_"), safe="")

    def get(self, title: str) -> CachedPage | None:
        meta = self._stem(title).with_suffix(".json")
        if not meta.exists():
            return None
        return CachedPage(**json.loads(meta.read_text()))

    def html_path(self, title: str) -> Path:
        return self._stem(title).with_suffix(".html")

    def put(self, page: CachedPage, html: str | None) -> None:
        # HTML first: the metadata file is what marks an entry as cached.
        if html is not None:
            self.html_path(page.requested_title).write_text(html, encoding="utf-8")
        self._stem(page.requested_title).with_suffix(".json").write_text(
            json.dumps(asdict(page), ensure_ascii=False, indent=2) + "\n"
        )


class WikipediaFetcher:
    def __init__(self, cache: WikipediaCache, client: httpx.Client | None = None):
        self.cache = cache
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0
        )
        self.requests_made = 0
        self._last_request_at = 0.0

    def fetch(self, title: str) -> CachedPage:
        """Return the cached page, requesting it from Wikipedia only when it is not cached."""
        cached = self.cache.get(title)
        if cached is not None:
            return cached
        response = self._get(title)
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if response.status_code == 404:
            page = CachedPage(title, None, None, None, fetched_at, "missing")
            self.cache.put(page, None)
            return page
        response.raise_for_status()
        canonical = _canonical_title(response)
        page = CachedPage(
            requested_title=title,
            canonical_title=canonical,
            revision_id=_revision_id(response),
            url=f"https://en.wikipedia.org/wiki/{quote(canonical.replace(' ', '_'), safe='()_,')}",
            fetched_at=fetched_at,
            status="ok",
        )
        self.cache.put(page, response.text)
        return page

    def _get(self, title: str) -> httpx.Response:
        url = REST_HTML_URL + quote(title.replace(" ", "_"), safe="")
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_for_turn()
            response = self.client.get(url)
            self.requests_made += 1
            if response.status_code != 429 or attempt == MAX_ATTEMPTS:
                return response
            time.sleep(_retry_after(response, attempt))
        raise AssertionError("unreachable")

    def _wait_for_turn(self) -> None:
        wait = self._last_request_at + MIN_INTERVAL_SECONDS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()


def _canonical_title(response: httpx.Response) -> str:
    """Title from the final URL, which is the canonical one after any redirect."""
    match = _TITLE_IN_PATH.search(urlparse(str(response.url)).path)
    if match is None:
        raise ValueError(f"cannot read a title from {response.url}")
    return unquote(match.group(1) or match.group(2)).replace("_", " ")


def _revision_id(response: httpx.Response) -> int:
    match = _REVISION_IN_ETAG.match(response.headers.get("etag", ""))
    if match is None:
        raise ValueError(f"no revision id in etag for {response.url}")
    return int(match.group(1))


def _retry_after(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("retry-after", "")
    if header.isdigit():
        return float(header)
    return DEFAULT_RETRY_SECONDS * 2 ** (attempt - 1)
