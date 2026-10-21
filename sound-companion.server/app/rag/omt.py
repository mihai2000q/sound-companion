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

# Topics per page, from the book's table of contents mapped to the project's topics (docs/DOMAIN.md).
# Every page that is not excluded needs an entry; `parse_omt` raises on a missing one.
_FUNDAMENTALS = {
    "basicNotation": ["notation"],
    "meter": ["rhythm-and-meter"],
    "protonotation": ["notation", "rhythm-and-meter"],
    "rhythmicValues": ["rhythm-and-meter", "notation"],
    "beams": ["rhythm-and-meter", "notation"],
    "pitches": ["notes-and-intervals", "notation"],
    "scales": ["scales-and-modes"],
    "keySignatures": ["scales-and-modes", "notation"],
    "intervals": ["notes-and-intervals"],
    "triads": ["chords-and-harmony"],
    "motionTypes": ["counterpoint-and-voice-leading"],
    "whiteKeyMethod": ["notes-and-intervals"],
    "sightSinging": ["notes-and-intervals"],
    "chromaticSolfege": ["notes-and-intervals", "scales-and-modes"],
    "trinket": ["notation"],
    "analyzingPoetry": ["rhythm-and-meter"],
}
_VOICE_LEADING = {
    slug: ["counterpoint-and-voice-leading"]
    for slug in (
        "speciesIntro cantusFirmus firstSpecies secondSpecies thirdSpecies fourthSpecies "
        "thoroughbassFigures bassoContinuo-history bassoContinuo tendency "
        "tendencyTonesFunctionalDissonances melodicKeyboardStyle KBVLschemata unfiguredBass "
        "embellishingTones melodicSequentials"
    ).split()
}
_VOICE_LEADING["RNfromFB"] = ["counterpoint-and-voice-leading", "chords-and-harmony"]
_HARMONY = {
    slug: ["chords-and-harmony"]
    for slug in (
        "functions harmonicFunctions harmonicSyntax1 harmonicSyntax2 harmonicAnalysis cadenceTypes "
        "alteredSubdominants appliedChords modalMixture"
    ).split()
}
_HARMONY["Modulation"] = ["chords-and-harmony", "form"]
_FORM = {
    slug: ["form"]
    for slug in (
        "thematicStructureInTheClassicalStyle sentence period hybridThemes compoundPeriod "
        "compoundSentence smallTernary smallBinary classicalThemes themeFunctions externalExpansions "
        "internalExpansions SonataTheory-intro SonataTheory-exposition SonataTheory-modules "
        "sonataStructuralPointsOfArrival sonataThematicModules sonataRecap sonataDevelopment "
        "sonataFramingModules rondo thematicFunctionInRondo fivePartRondo sonataRondo minuet MinuetForm "
        "schemataOpensAndCloses schemataContinuationPatterns schemataSummary schemata-improv "
        "popRockForm popRockForm-terms popRockForm-containers popRockForm-functions popRockForm-notation"
    ).split()
}
_POST_TONAL = {
    slug: ["post-tonal"]
    for slug in (
        "pitch(Class) interval(Class) mod12 scales2 symmetryAndCentricity normalOrder transposition "
        "inversion setClassAndPrimeForm1 setClassAndPrimeForm2 complements commonTonesUnderTransposition "
        "twelveToneBasics twelveToneOperations twelveToneIntervallicStructure twelveToneMusicDerivation "
        "twelveToneMusicInvariance postTonalAnalysis atonal twelveTone atonalGlossary"
    ).split()
}
_POP_ROCK = {"syncopation": ["rhythm-and-meter"]}
_POP_ROCK.update(
    {
        slug: ["chords-and-harmony"]
        for slug in (
            "popRockHarmony popRockHarmony-dooWop popRockHarmony-sscp popRockHarmony-puff "
            "popRockHarmony-blues popRockHarmony-lament popRockHarmony-fifths popRockHarmony-plagal "
            "popRockHarmony-pachelbel popRockHarmony-minor"
        ).split()
    }
)
_POP_ROCK.update(
    {f"popRockHarmony-EverettSystem{n}": ["chords-and-harmony", "scales-and-modes"] for n in range(2, 6)}
)
TOPICS = {
    **_FUNDAMENTALS, **_VOICE_LEADING, **_HARMONY, **_FORM, **_POST_TONAL, **_POP_ROCK,
}

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
    topics: list[str]


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
        if slug not in TOPICS:
            raise ValueError(f"no topics for the Open Music Theory page '{slug}', add it to TOPICS")
        documents.append(
            OmtDocument(
                slug=slug,
                title=title,
                url=f"{SITE_URL}/{quote(slug, safe='()')}.html",
                license=LICENSE,
                commit=commit,
                sections=_split_sections(body),
                topics=TOPICS[slug],
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
