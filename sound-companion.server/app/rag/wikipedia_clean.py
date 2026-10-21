import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from app.rag.documents import Section

# Elements that carry no prose: images and media, references, navigation and maintenance boxes.
_DROP = [
    "style", "script", "link", "meta", "figure", "img", "audio", "video",
    "sup.mw-ref", "sup.reference", "sup.citation", "span.mw-editsection", "ol.references", "div.reflist",
    "div.hatnote", "div.shortdescription", "div.side-box", "div.navigation-not-searchable",
    "div.navbox", "table.navbox", "table.ambox", "table.infobox", "table.sidebar",
    "table.metadata", "span.mw-empty-elt",
]
# Sections that only hold references, links or lists of other pages.
_SKIPPED_HEADINGS = {
    "references", "notes", "footnotes", "citations", "sources", "bibliography",
    "further reading", "external links", "see also", "notes and references", "works cited",
    "gallery", "discography", "recordings",
}
_BLOCKS = {"p", "ul", "ol", "dl", "blockquote", "pre", "table"}
_MATH_WRAPPER = re.compile(r"^\{\\displaystyle\s*(.*)\}$", re.DOTALL)


@dataclass
class CleanedPage:
    sections: list[Section]
    is_disambiguation: bool


def clean_wikipedia_html(html: str) -> CleanedPage:
    """Prose and readable tables of a REST HTML page, split into sections on h2 and h3 headings."""
    soup = BeautifulSoup(html, "html.parser")
    is_disambiguation = soup.select_one('meta[property="mw:PageProp/disambiguation"]') is not None
    for selector in _DROP:
        for tag in soup.select(selector):
            tag.decompose()
    # Tables other than `wikitable` are boxes (infobox, sidebar, layout), not data.
    for table in soup.select("table:not(.wikitable)"):
        table.decompose()
    _inline_markup_to_text(soup)
    builder = _SectionBuilder()
    builder.walk(soup.body or soup)
    return CleanedPage(builder.finish(), is_disambiguation)


def _inline_markup_to_text(soup: BeautifulSoup) -> None:
    for math in soup.select("span.mwe-math-element"):
        alttext = math.find("math")
        text = alttext.get("alttext", "") if alttext else ""
        wrapped = _MATH_WRAPPER.match(text)
        math.replace_with(wrapped.group(1) if wrapped else text)
    for sup in soup.find_all("sup"):
        sup.replace_with("^" + sup.get_text())
    for br in soup.find_all("br"):
        br.replace_with(" ")


def _text(tag: Tag) -> str:
    text = tag.get_text().replace("\xa0", " ").replace("\u2060", "")  # no-break space, word joiner
    return re.sub(r"\s+", " ", text).strip()


class _SectionBuilder:
    def __init__(self) -> None:
        self.sections: list[Section] = []
        self._stack: list[tuple[int, str]] = []  # (level, heading) of the enclosing headings
        self._blocks: list[str] = []
        self._skip_level: int | None = None

    def walk(self, node: Tag) -> None:
        for child in node.children:
            if not isinstance(child, Tag):
                continue
            if child.name in ("h2", "h3"):
                self._heading(int(child.name[1]), _text(child))
            elif child.name in ("h4", "h5", "h6"):
                self._add(_text(child))
            elif child.name in _BLOCKS:
                self._add(_render_block(child))
            else:
                self.walk(child)

    def finish(self) -> list[Section]:
        self._flush()
        return self.sections

    def _heading(self, level: int, text: str) -> None:
        self._flush()
        if self._skip_level is not None and level <= self._skip_level:
            self._skip_level = None
        if self._skip_level is None and text.lower() in _SKIPPED_HEADINGS:
            self._skip_level = level
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, text))

    def _add(self, text: str) -> None:
        if text and self._skip_level is None:
            self._blocks.append(text)

    def _flush(self) -> None:
        text = "\n\n".join(self._blocks).strip()
        if text:
            self.sections.append(Section([heading for _, heading in self._stack], text))
        self._blocks = []


def _render_block(tag: Tag) -> str:
    if tag.name == "table":
        return _render_table(tag)
    if tag.name in ("ul", "ol", "dl"):
        return _render_list(tag)
    return _text(tag)


def _render_list(tag: Tag) -> str:
    lines = []
    for item in tag.find_all(["li", "dt", "dd"]):
        # Own text only: a nested list is a separate item further down the iteration.
        own = " ".join(
            _text(child) if isinstance(child, Tag) else child.strip()
            for child in item.children
            if not (isinstance(child, Tag) and child.name in ("ul", "ol", "dl"))
        )
        own = re.sub(r"\s+", " ", own).strip()
        if own:
            depth = len(item.find_parents(["ul", "ol", "dl"])) - 1
            lines.append("  " * depth + "- " + own)
    return "\n".join(lines)


def _render_table(table: Tag) -> str:
    """Rows of cells joined with ` | `, with `rowspan` and `colspan` expanded so columns line up."""
    grid: dict[tuple[int, int], str] = {}
    rows = table.find_all("tr")
    for r, tr in enumerate(rows):
        c = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            while (r, c) in grid:
                c += 1
            rowspan, colspan = _span(cell, "rowspan"), _span(cell, "colspan")
            text = _text(cell)
            for i in range(rowspan):
                for j in range(colspan):
                    grid[(r + i, c + j)] = text
            c += colspan
    width = max((c for _, c in grid), default=-1) + 1
    lines = [
        " | ".join(grid.get((r, c), "") for c in range(width)).strip()
        for r in range(len(rows))
    ]
    lines = [line for line in lines if line.strip(" |")]
    caption = table.find("caption")
    if caption is not None and _text(caption):
        lines.insert(0, _text(caption))
    return "\n".join(lines)


def _span(cell: Tag, attribute: str) -> int:
    value = str(cell.get(attribute, "1"))
    return int(value) if value.isdigit() and int(value) > 0 else 1
