# Sound Companion

A chatbot that teaches music theory and musical instruments from a curated, cited corpus and local calculation tools. This file is the project's domain language only. Technical terms (RAG, RRF, SSE and so on) live in [docs/GLOSSARY.md](docs/GLOSSARY.md).

## Language

### Music

**Note**:
A pitch with its octave, such as C4. C4 is middle C and A4 is 440 Hz.
_Avoid_: Tone, key (a key is something else)

**Pitch class**:
A note name without its octave, such as any C. Chord and scale tools work on pitch classes.
_Avoid_: Note name, chroma

**Written pitch**:
The pitch a player reads on the page for a transposing instrument.
_Avoid_: Notated pitch, fingered pitch

**Sounding pitch**:
The pitch the instrument actually produces. For a B-flat clarinet reading a written C, it is Bb3.
_Avoid_: Concert pitch (also means A=440 tuning), real pitch

**Chord**:
Several pitch classes sounding together, such as D, F, A and C.
_Avoid_: Harmony (broader), triad (a chord of three)

**Chord symbol**:
One way of writing a Chord, such as Cmaj7 or CΔ7. A single Chord can have several symbols.
_Avoid_: Chord name

**Instrument**:
A musical instrument with its own article in the corpus, such as the oboe or the double bass.
_Avoid_: Device, axe

**Alias**:
Another name for the same Instrument or concept, such as English horn for Cor anglais.
_Avoid_: Synonym, redirect

### Conventions

**Convention**:
A naming or notation system that sources can disagree on, such as middle C being C4 or C3, B being called H in German, or the symbol styles for an augmented chord.
_Avoid_: Standard, style

**Convention conflict**:
A case where retrieved Citations use different Conventions for the same thing. The bot shows each with its own Citation and never picks a winner.
_Avoid_: Disputed claim, disagreement

**Candidate**:
One result of an ambiguous analysis. The notes D, F, A, C give two Candidates: Dm7 and F6/D.
_Avoid_: Option, guess

### Knowledge base

**Source type**:
Whether a Corpus document is a Textbook (Open Music Theory) or an Encyclopedia article (Wikipedia).
_Avoid_: Origin, category

**Seed list**:
The hand-curated list of Wikipedia articles and textbook pages that defines what belongs in the Corpus.
_Avoid_: Whitelist, dataset

**Seed entry**:
One line of the Seed list: a title, its Source type, its topic tags, and its Aliases.
_Avoid_: Record

**Corpus**:
The indexed text produced by ingesting the Seed list and Open Music Theory v1: 276 documents, 7,329 chunks (docs/DOMAIN.md, "Corpus facts"). It is what the bot retrieves from.
_Avoid_: Database, data, documents

**Provenance**:
Where and when a piece of Corpus text was fetched, with its revision id and licence.
_Avoid_: Source (clashes with Citation and Source type)

### Answering

**Citation**:
A reference from a statement in an answer to the Corpus text or tool result that supports it.
_Avoid_: Source, reference, footnote

**Conversation**:
One chat session between the user and the bot.
_Avoid_: Thread, session, chat (the technical id is `thread_id`)

## Relationships

- A **Seed entry** produces one document in the **Corpus**, with **Provenance** and a **Source type**.
- An **Instrument** has a **Written pitch** and a **Sounding pitch**, related by its transposition.
- A **Chord** can have several **Chord symbols**, and an ambiguous analysis returns several **Candidates**.
- A **Convention conflict** has two or more **Citations**, one per **Convention**.
- Tool results state which **Convention** they use (scientific pitch notation: C4 is middle C).
