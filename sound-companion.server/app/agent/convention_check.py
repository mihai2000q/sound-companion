"""Automated check that an answer to a Convention-conflict question names every Convention and cites the
pages behind them. Plain text matching on the final answer, so it flags a missing Convention or Citation
and does not judge the wording."""
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConventionCase:
    id: str
    question: str
    conventions: dict[str, tuple[str, ...]]  # label -> regexes, any one of them matching counts (case-sensitive)
    citations: dict[str, tuple[str, ...]]  # label -> page titles, any one of them cited counts
    differ_words: tuple[str, ...] = ("differ", "whereas", "while", "instead")


@dataclass
class ConventionResult:
    id: str
    missing_conventions: list[str] = field(default_factory=list)
    missing_citations: list[str] = field(default_factory=list)
    says_they_differ: bool = True

    @property
    def ok(self) -> bool:
        return not (self.missing_conventions or self.missing_citations) and self.says_they_differ


def cited(answer: str, title: str) -> bool:
    """The page is cited as (Title > Section) or (Title), or linked by its URL slug."""
    in_parentheses = re.findall(r"\(([^()]*)\)", answer)
    slug = title.replace(" ", "_").casefold()
    return any(title.casefold() in text.casefold() for text in in_parentheses) or slug in answer.casefold()


def check_answer(case: ConventionCase, answer: str) -> ConventionResult:
    text = answer.casefold()  # for the differ words
    return ConventionResult(
        id=case.id,
        missing_conventions=[
            label for label, spellings in case.conventions.items() if not any(re.search(s, answer) for s in spellings)
        ],
        missing_citations=[
            label for label, titles in case.citations.items() if not any(cited(answer, t) for t in titles)
        ],
        says_they_differ=any(word in text for word in case.differ_words),
    )


# Spellings and pages come from what the Corpus says (see decisions 62 and 73): Scientific pitch notation and the
# textbook give C4, the Musical note page gives German B / H. q06 does not require Helmholtz c′ (decision 73).
CASES = [
    ConventionCase(
        id="q06",
        question="What is middle C called, and what do Germans call B-flat and B natural?",
        conventions={
            "scientific C4": (r"\bC4\b",),
            "German B = B-flat": (r"B-flat|B♭|B flat",),
            "German H = B natural": (r"\bH\b",),
        },
        citations={
            "middle C page": ("Scientific pitch notation", "Pitches and octave designations"),
            "German names page": ("Musical note", "Accidental"),
        },
    ),
    ConventionCase(
        id="q12",
        question="What is the difference between concert pitch and written pitch?",
        conventions={
            "concert pitch": (r"(?i)concert pitch",),
            "written pitch": (r"(?i)written",),
        },
        citations={
            "concert pitch page": ("Concert pitch",),
            "transposing page": ("Transposing instrument", "Pitch (music)"),
        },
    ),
]
