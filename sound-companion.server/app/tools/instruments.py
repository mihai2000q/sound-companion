"""The transposition table for transpose_for_instrument.

Source of every row: the Wikipedia page "List of transposing instruments", column "The note C4 written down
produces" (revision 1333051777, read from the cached page on 2026-10-22). `sounding_c4` is that cell, so the
table is checked against the page instead of against memory, and `interval` (music21 notation, written to
sounding) is derived from it: sounding minus written C4. Most rows are cross-checked against the "Transposing
instrument" article, which has prose only (see docs/research/ingestion-sources-facts.md).
"""
import re
from dataclasses import dataclass

TRANSPOSING_LIST_URL = "https://en.wikipedia.org/wiki/List_of_transposing_instruments"
LICENSE = "CC BY-SA 4.0"


@dataclass(frozen=True)
class Instrument:
    key: str
    name: str
    family: str  # the "Instrument family" cell of the source row, used as the Citation section
    sounding_c4: str  # what a written C4 sounds like
    interval: str  # written to sounding, in music21 notation
    aliases: tuple[str, ...] = ()

    @property
    def citation(self) -> dict:
        return {
            "title": "List of transposing instruments",
            "section": self.family,
            "url": TRANSPOSING_LIST_URL,
            "license": LICENSE,
        }


INSTRUMENTS = [
    Instrument("bb_clarinet", "B-flat clarinet", "Clarinet", "Bb3", "M-2", ("clarinet in bb", "soprano clarinet")),
    Instrument("a_clarinet", "A clarinet", "Clarinet", "A3", "m-3", ("clarinet in a",)),
    Instrument("eb_clarinet", "E-flat clarinet", "Clarinet", "Eb4", "m3", ("clarinet in eb",)),
    Instrument("bass_clarinet", "bass clarinet", "Clarinet", "Bb2", "M-9"),
    Instrument("bb_trumpet", "B-flat trumpet", "Trumpet", "Bb3", "M-2", ("trumpet in bb", "trumpet")),
    Instrument("soprano_sax", "soprano saxophone", "Saxophone", "Bb3", "M-2", ("soprano sax",)),
    Instrument("alto_sax", "alto saxophone", "Saxophone", "Eb3", "M-6", ("alto sax",)),
    Instrument("tenor_sax", "tenor saxophone", "Saxophone", "Bb2", "M-9", ("tenor sax",)),
    Instrument("baritone_sax", "baritone saxophone", "Saxophone", "Eb2", "M-13", ("baritone sax", "bari sax")),
    Instrument("f_horn", "F horn", "Horn", "F3", "P-5", ("horn", "french horn", "horn in f")),
    Instrument("english_horn", "English horn", "Cor anglais", "F3", "P-5", ("cor anglais",)),
    Instrument("piccolo", "piccolo", "Flute", "C5", "P8"),
    Instrument("guitar", "guitar", "Guitar", "C3", "P-8", ("acoustic guitar", "electric guitar", "classical guitar")),
    Instrument("double_bass", "double bass", "Viol", "C3", "P-8", ("contrabass", "upright bass", "string bass")),
]


def normalise_name(text: str) -> str:
    """Lowercase, 'B-flat' and 'B♭' to 'bb', drop punctuation and 'in'."""
    text = text.lower().replace("♭", " flat ")
    text = re.sub(r"\b([a-g])[ -]flat\b", r"\1b", text)
    return " ".join(w for w in re.sub(r"[^a-z0-9]+", " ", text).split() if w != "in")


_BY_NAME = {
    normalise_name(label): instrument
    for instrument in INSTRUMENTS
    for label in (instrument.name, instrument.key.replace("_", " "), *instrument.aliases)
}


def find_instrument(text: str) -> Instrument | None:
    return _BY_NAME.get(normalise_name(text))
