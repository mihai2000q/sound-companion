import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from app.rag.documents import Section

REPO_URL = "https://github.com/openmusictheory/openmusictheory.github.io.git"
SITE_URL = "https://openmusictheory.github.io"
LICENSE = "CC BY-SA 4.0"  # page footer and about page, the repo has no LICENSE file

# Site plumbing and how-to videos about tools, not music theory. Reasons are shown in the report.
EXCLUDED = {
    "404": "site plumbing: error page",
    "README": "site plumbing: repository readme",
    "index": "site plumbing: home page",
    "contents": "site plumbing: table of contents",
    "contents-hidden": "site plumbing: draft table of contents",
    "about": "about the book, not music theory",
    "addCC": "stub: video on adding a licence to a blog post",
    "linkToTwitter": "stub: video on posting a link to Twitter",
    "GDrive": "stub: how to use Google Drive",
    "TBDemo": "stub: demo of the Trinket notation modules",
    "createGraphic": "stub: video on making a graphic in MuseScore",
    "typesettingKBStyle": "stub: how to typeset keyboard style",
    "VAT": "stub: video on Variations Audio Timeliner",
    "melodicKB": "stub: video only",
    "melodicDictationDemo": "stub: video demo of the author's dictation process",
}
MIN_PROSE_WORDS = 60  # any other page this short is a stub too

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---[ \t]*\n", re.DOTALL)
_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
# `[keyboard]: {{ site.url }}/Graphics/keyboard.png` (image targets) and plain `[VAT]: http://...`
_LINK_DEFINITION = re.compile(r"^\[[^\]\n]+\]:[ \t]*\S.*\n?", re.MULTILINE)
# `{{ page.title }}` followed by its `====` underline, a leftover of the Jekyll template
_TEMPLATE_TITLE = re.compile(r"^\{\{ page\.title \}\}[ \t]*\n[=\-]{3,}[ \t]*\n?", re.MULTILINE)
_HEADING = re.compile(r"^(#{1,3})[ \t]+(.*?)[ \t]*#*[ \t]*$")


@dataclass
class OmtDocument:
    slug: str
    title: str
    url: str
    license: str
    commit: str
    sections: list[Section]


@dataclass
class OmtParse:
    documents: list[OmtDocument]
    excluded: dict[str, str]  # slug -> reason


def clone_omt(dest: Path) -> str:
    """Shallow clone into `dest` (inside the ignored cache), or reuse it. Returns the commit."""
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(dest)], check=True)
    result = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def parse_omt(clone_dir: Path, commit: str) -> OmtParse:
    documents: list[OmtDocument] = []
    excluded: dict[str, str] = {}
    for path in sorted(clone_dir.glob("*.md")):
        slug = path.stem
        if slug in EXCLUDED:
            excluded[slug] = EXCLUDED[slug]
            continue
        title, body = _split_front_matter(path.read_text(encoding="utf-8"), slug)
        body = _clean(body)
        if len(body.split()) < MIN_PROSE_WORDS:
            excluded[slug] = "stub: under %d words of text" % MIN_PROSE_WORDS
            continue
        documents.append(
            OmtDocument(
                slug=slug,
                title=title,
                url=f"{SITE_URL}/{quote(slug, safe='()')}.html",
                license=LICENSE,
                commit=commit,
                sections=_split_sections(body),
            )
        )
    return OmtParse(documents, excluded)


def _split_front_matter(text: str, slug: str) -> tuple[str, str]:
    match = _FRONT_MATTER.match(text)
    if match is None:
        return slug, text
    title = _TITLE.search(match.group(1))
    return (title.group(1).strip("\"' ") if title else slug), text[match.end():]


def _clean(body: str) -> str:
    body = _LINK_DEFINITION.sub("", body)
    return _TEMPLATE_TITLE.sub("", body).strip()


def _split_sections(body: str) -> list[Section]:
    """Split on `#`, `##` and `###` headings; the heading path holds the enclosing headings."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (level, heading) of the enclosing headings
    lines: list[str] = []

    def flush() -> None:
        text = "\n".join(lines).strip()
        if text:
            sections.append(Section([heading for _, heading in stack], text))
        lines.clear()

    for line in body.splitlines():
        match = _HEADING.match(line)
        if match is None or not match.group(2):
            lines.append(line)
            continue
        flush()
        level = len(match.group(1))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, match.group(2)))
    flush()
    return sections
