# Metal Archive Assistant

A chatbot that answers questions about metal artists, genres and discographies from a curated corpus and live MusicBrainz lookups. This file is the project's domain language only. Technical terms (RAG, RRF, SSE and so on) live in [docs/GLOSSARY.md](docs/GLOSSARY.md).

## Language

### Subjects

**Entity**:
Anything the corpus has a page for: an Artist, a Genre article or a History article.
_Avoid_: Item, record, subject

**Artist**:
A group or a single person who makes metal, such as Black Sabbath or Ozzy Osbourne.
_Avoid_: Band (excludes solo artists)

**Genre article**:
A page describing a style, such as thrash metal or deathcore.
_Avoid_: Subgenre page

**History article**:
A page about origins, scenes or eras rather than one Artist or one style, such as the history of heavy metal.
_Avoid_: Background page

**Subgenre tag**:
A style label attached to an Artist or article in the seed list. An Artist can carry several (Opeth: death metal, progressive metal). Never attached to a single Release.
_Avoid_: Genre field, category

**Proto-metal**:
A tag for Artists that predate or border the genre, such as Blue Cheer or Iron Butterfly. It does not claim they are metal.
_Avoid_: Pre-metal, early metal

### Discography

**Release**:
One album, EP or single regardless of edition. It corresponds to a MusicBrainz release group.
_Avoid_: Album (too narrow), record, edition

**Edition**:
A specific issue of a Release, such as the 1991 CD or the 2021 remaster. It corresponds to a MusicBrainz release and is ignored by our tools.
_Avoid_: Version, pressing

**Discography**:
The studio albums and EPs of an Artist, one row per Release. Live albums, compilations and demos are excluded unless the user asks.
_Avoid_: Catalogue, full list

### Knowledge base

**Seed list**:
The hand-curated list of Artists, Genre articles and History articles that defines what belongs in the corpus.
_Avoid_: Whitelist, dataset

**Seed entry**:
One line of the seed list: a name, its Subgenre tags, its Entity type, and optionally a MusicBrainz id and a contested flag.
_Avoid_: Record

**Corpus**:
The indexed text produced by ingesting the seed list. It is what the bot retrieves from.
_Avoid_: Database, data, documents

**Provenance**:
Where a piece of corpus text came from, such as `music-wiki` or `wikipedia-api`.
_Avoid_: Source (clashes with Citation)

### Answering

**Citation**:
A reference from a statement in an answer to the corpus text or tool result that supports it.
_Avoid_: Source, reference, footnote

**Disputed claim**:
A question whose retrieved Citations disagree, or whose article is flagged contested in the seed list, such as the first metal song.
_Avoid_: Controversy, conflict

**Candidate**:
One possible answer to a Disputed claim: a song, an album or an Artist, depending on what was asked. Each Candidate carries its own Citation.
_Avoid_: Option, contender

**Conversation**:
One chat session between the user and the bot.
_Avoid_: Thread, session, chat (the technical id is `thread_id`)

## Relationships

- An **Artist** has many **Releases**. A **Release** has many **Editions**, which the tools ignore.
- A **Seed entry** produces one **Entity** in the **Corpus**. A **Seed entry** marked contested makes questions about it **Disputed claims**.
- A **Disputed claim** has two or more **Candidates**, and every **Candidate** has a **Citation**.
- Years come from **Releases** (MusicBrainz), never from **Corpus** text.
