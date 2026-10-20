# Musical instruments and tuning: data verification

Checked 2026-10-19 against primary sources only (live API calls, licence pages, npm package). No API keys used, no existing files modified. Scratch scripts and raw outputs live in the session scratchpad.

## Verdict table

| Item | Verdict | One-line reason |
|---|---|---|
| Wikipedia article corpus (about 150 instruments, depth) | verified | 40-article sample: median 27,057 chars, 10 sections; 125 of 190 Hornbostel-Sachs-linked pages are over 5,000 chars |
| Wikipedia licence / reuse terms | verified | CC BY-SA 4.0 (plus GFDL); attribution by link; share-alike applies |
| Clean seed list from categories | partly | Category tree is polluted (musicians, retailers, songs); category pages alone are not clean |
| Clean seed list from Hornbostel-Sachs / List pages | verified | `Hornbostel-Sachs` page has 205 article links and a 40k-char text; works, needs a filter step |
| Wikibooks / open textbooks on instruments | partly | Licence is CC BY-SA 4.0, but only about 4 usable instrument pages (about 25k chars total); no "Orchestration" or "Organology" book |
| Met Museum Open Access API (Musical Instruments) | verified | CC0, keyless, 5,269 object IDs in dept 18 (v1.1 search reports 5,327); metadata only, no prose |
| `tonal` npm package | verified | v6.5.1, MIT; all five sample calls ran correctly |
| Other tools (transposition, cents, harmonics, fret/string length) | verified | Trivial to write by hand (a few lines each); outputs below |
| Combined corpus is enough for a few thousand chunks with section structure | verified | About 2.4M chars in pages over 5k chars, roughly 2,400 chunks at 1,000 chars from Wikipedia alone |
| Wikiversity and other open textbooks | unverified | Not checked; no licence page read, so not included |

## 1. Wikipedia

### Size and depth (official API, 2026-10-19)

Method: `https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1&titles=<one title>` for length, and `action=parse&prop=sections` for section count (all levels). Docs: https://www.mediawiki.org/wiki/API:Query and https://www.mediawiki.org/wiki/Extension:TextExtracts

Gotcha confirmed: with `explaintext` and no `exintro`, the extracts module returns the full text for only ONE page per request (a batch of 20 titles returned empty extracts for most). Fetch one title per request, or use the REST API / `action=parse` instead. Also, a burst of requests got an HTTP 429-style "too many requests" message; use a descriptive User-Agent and about 1 request per second (https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits).

40 representative titles (chars of plain-text extract / total sections):

| Family | Title | Chars | Sections |
|---|---|---|---|
| Strings | Violin | 65,223 | 42 |
| | Viola | 24,570 | 15 |
| | Cello | 50,108 | 32 |
| | Double bass | 103,176 | 59 |
| | Harp | 28,392 | 34 |
| | Acoustic guitar | 16,545 | 14 |
| | Electric guitar | 28,743 | 14 |
| | Banjo | 47,719 | 23 |
| | Mandolin | 34,680 | 39 |
| | Sitar | 13,614 | 11 |
| Woodwinds | Flute | 20,200 | 21 |
| | Oboe | 23,477 | 22 |
| | Clarinet | 29,773 | 20 |
| | Bassoon | 51,824 | 31 |
| | Saxophone | 39,001 | 24 |
| | Piccolo | 6,732 | 8 |
| | Cor anglais (English horn) | 17,782 | 9 |
| | Recorder (musical instrument) | 99,627 | 68 |
| Brass | Trumpet | 25,475 | 19 |
| | Trombone | 51,216 | 58 |
| | French horn | 36,087 | 28 |
| | Tuba | 40,141 | 32 |
| | Cornet | 10,833 | 13 |
| | Euphonium | 27,254 | 24 |
| Percussion | Timpani | 36,556 | 27 |
| | Snare drum | 19,308 | 12 |
| | Xylophone | 14,690 | 17 |
| | Marimba | 23,127 | 21 |
| | Cymbal | 11,743 | 20 |
| | Triangle (musical instrument) | 8,018 | 7 |
| Keyboards | Piano | 61,180 | 26 |
| | Harpsichord | 26,859 | 25 |
| | Pipe organ | 43,028 | 30 |
| | Accordion | 40,269 | 39 |
| | Celesta | 11,156 | 11 |
| Electronic | Synthesizer | 24,040 | 29 |
| | Theremin | 25,843 | 17 |
| | Hammond organ | 43,143 | 22 |
| Folk / world | Didgeridoo | 17,182 | 17 |
| | Shamisen | 20,653 | 21 |

- n = 40, median 27,057 chars, min 6,732, max 103,176, total 1,318,987 chars. Median sections 22 (median top-level sections 10).
- Thinnest 10: Piccolo 6,732; Triangle 8,018; Cornet 10,833; Celesta 11,156; Cymbal 11,743; Sitar 13,614; Xylophone 14,690; Acoustic guitar 16,545; Didgeridoo 17,182; Cor anglais 17,782. Even the thinnest has at least 7 sections.
- Caveat: this sample is deliberately popular instruments. The wider sample below shows the long tail is thinner.

### Wider sample from the Hornbostel-Sachs page

Took all main-namespace links of https://en.wikipedia.org/wiki/Hornbostel%E2%80%93Sachs (via `prop=links`) and fetched each page's extract one by one: 190 pages (includes a few non-instrument pages such as "Bellows" or "Trough (physics)").
- Median 7,400 chars; median 10 headings (counted from `==` lines in the extract).
- 125 of 190 are at least 5,000 chars, 80 are at least 10,000, 28 are under 2,000.
- Total 2,595,202 chars; 2,434,955 chars sit in the pages over 5,000 chars.
- Thinnest examples: Conical drum 340, Gharha 618, Blown idiophone 740, Barrel drum 808, Kubing 892. These are classification stubs and should be excluded by a length threshold (suggest 5,000 chars).

So "about 150 instrument articles with substantial text" is confirmed: roughly 125 qualify at 5k chars, and the 40 popular ones are all well above it.

### Licence and attribution

Wikimedia Terms of Use, section "Licensing of Content": text is CC BY-SA 4.0 and GFDL; reusers may comply with either; attribution can be a hyperlink or URL to the article (the history page lists authors), or a link to a stable alternative copy that credits authors; facts "may be reused freely without attribution". Source: https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use (read in full, section 7). Wikibooks and Wikipedia siteinfo `rightsinfo` both return "Creative Commons Attribution-Share Alike 4.0": https://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=rightsinfo&format=json

### Seed list options

- `Category:Musical instruments`: 46 pages, 55 subcategories (API `list=categorymembers`). Subcategories include non-instrument ones: "Musicians by instrument", "Composers by instrument", "Musical instrument retailers", "Songs about musical instruments", "Effects units". Needs manual pruning; not clean. Useful subtrees: Aerophones (32 pages, 12 subcats), Chordophones (34/3), Idiophones (94/6), Membranophones (69/6), Keyboard instruments (103/9), Transposing instruments (5/8), Electronic musical instruments (134/18). Source: https://en.wikipedia.org/wiki/Category:Musical_instruments
- Hornbostel-Sachs page: 205 article links, 40,508 chars of text, organised by the four top-level classes. Good seed, gives the classification structure for free. https://en.wikipedia.org/wiki/Hornbostel%E2%80%93Sachs
- "Musical instrument classification": 260 links, 23,899 chars. https://en.wikipedia.org/wiki/Musical_instrument_classification
- "List of musical instruments": 1,768 links (it is mostly a list of lists, so the intro text is only 1,099 chars). https://en.wikipedia.org/wiki/List_of_musical_instruments
- Recommended: union of Hornbostel-Sachs links and a hand-picked list of about 60 orchestral and popular instruments, then filter by length at least 5,000 chars.

### Supporting theory-of-instruments pages (all exist, chars)

Transposing instrument 8,771 (sections: Reasons for transposing, Horn crooks, Reconciling pitch standards, Transposition at the octave, Conductor's score); Harmonic series (music) 15,015; Musical acoustics 11,262; Concert pitch 10,177; Organology 10,414; Scordatura 13,735; Overtone 18,861; Brass instrument 25,145; Woodwind instrument 5,426; Horn (instrument) 37,523. Note "Tuning" is only 1,212 chars (a disambiguation page); the real article is "Musical tuning".

### Redirect and naming findings (useful for citation tests)

Redirects confirmed via the API: English horn goes to Cor anglais; Bombardon goes to Tuba; Pianoforte goes to Piano; Bass viol goes to Viol; Bb clarinet goes to Soprano clarinet.

## 2. Other open sources

### Wikibooks (CC BY-SA 4.0, confirmed via `siteinfo&siprop=rightsinfo` on en.wikibooks.org)

- Book "Acoustics": 41 subpages, but mostly engineering (loudspeakers, sonar, mufflers). Instrument-relevant: "Acoustics in Violins" 7,225 chars, "Bessel Functions and the Kettledrum" 7,089, "How an Acoustic Guitar Works" 5,461, "Basic Acoustics of the Marimba" (exists, not measured). "Acoustics/Print version" 148,362 chars overall. https://en.wikibooks.org/wiki/Acoustics
- "Introduction to Classical Music/Instruments" 6,192 chars (introductory level). https://en.wikibooks.org/wiki/Introduction_to_Classical_Music/Instruments
- "Orchestration": missing. "Organology": no pages. "Musical Instruments": only a subject redirect (7 chars). Other hits (Roman Culture/Musical Instruments of Rome 634 words, Harmonica 354 words, Piano 187 words) are tiny.
- Conclusion: Wikibooks adds perhaps 4 to 6 pages worth about 30k chars. Marginal for chunk count, but the acoustics pages (violin, guitar, kettledrum, marimba) add physics depth that Wikipedia lacks.

### Met Museum Open Access API

- Licence: Met "has waived all copyright and related or neighboring rights to this dataset using Creative Commons Zero"; for unrestricted commercial and noncommercial use. Read at https://metmuseum.github.io/ and https://github.com/metmuseum/openaccess (README). Images are covered separately (only `isPublicDomain` objects' images are CC0). Note: the Met's own web page at metmuseum.org/about-the-met/policies-and-documents/open-access could not be read (blocked by a Vercel browser check for scripts), so the licence reading comes from the API docs and the GitHub README, both Met-owned.
- Keyless: docs say "we do not require API users to register or obtain an API key"; limit 80 requests per second. Confirmed by calls without any key.
- IMPORTANT change: `/public/collection/v1/search` was retired on 2026-10-01 (live response says so). Use `/public/collection/v1.1/search` (paginated by offset/limit) or `/public/collection/v1/objects?departmentIds=18` for the full ID list.
- Department: `GET https://collectionapi.metmuseum.org/public/collection/v1/departments` returns `{departmentId: 18, displayName: "Musical Instruments"}`.
- Count: `v1/objects?departmentIds=18` returns total 5,269; `v1.1/search?departmentId=18&q=*` returns total 5,327 (the two endpoints differ; I did not reconcile this).
- Fields (sampled object 500771, Sitar): title, objectName, culture, period, objectDate, medium, dimensions, measurements, creditLine, country, region, classification (for example "Chordophone-Lute-plucked-fretted", a Hornbostel-Sachs style label), tags, objectURL, isPublicDomain, image URLs. There is NO descriptive prose field. Random sample of 40 objects: 16 chordophones, 10 idiophones, 5 membranophones, 5 aerophones; only 15 of 40 flagged `isPublicDomain` (images), 21 had `measurements`, 1 had `tags`.
- Use: good as a structured-data tool (look up museum examples of an instrument, by culture or classification), not as RAG prose.

### Not checked

Wikiversity, other open textbooks (OpenStax etc.), IMSLP, MIMO (Musical Instrument Museums Online): no licence page read, so deliberately excluded.

## 3. Tools

### `tonal`

Installed in an empty scratch directory (`.../scratchpad/tonal`, `npm i tonal`): version 6.5.1, license "MIT" per its `package.json`. Package source: https://www.npmjs.com/package/tonal and https://github.com/tonaljs/tonal. Runs locally, no network, no key. (Not checked: whether its API is stable across majors.)

Five sample calls and real outputs:

| Call | Output |
|---|---|
| `Note.freq("A4")` | `440` |
| `Midi.midiToNoteName(60)` / `(69)` / `(61,{sharps:false})` | `C4` / `A4` / `Db4` |
| Written C4 on a B-flat clarinet sounds: `Note.transpose("C4","-2M")` | `Bb3` (and concert C4 is written `D4` via `"2M"`) |
| `Interval.distance("C4","G5")` and `Interval.semitones(...)` | `12P` (a perfect twelfth) and `19` |
| 450 Hz: `Midi.freqToMidi(450)` then round, cents = (midi - round) x 100 | `A4`, `+39.0` cents (midi 69.39) |

Extra: E-flat alto sax written C5 sounds `Eb4` (`-6M`); F horn written C4 sounds `F3` (`-5P`); `Range.numeric([40,52])` and `Range.chromatic(["C4","E4"])` give `C4 Db4 D4 Eb4 E4`; `Note.enharmonic("D#4")` gives `Eb4`.

Caveats found: `tonal` has no built-in table of instruments (which transposition each instrument uses) and no instrument ranges; the tool layer must hold that table itself. Cents function is not a single call; it takes the 2 lines shown above.

### Trivial to hand-write (a few lines each, no dependency)

- Pitch to frequency: f = 440 x 2^((midi - 69)/12). Cents deviation: 1200 x log2(f / f_ref).
- Transposition by instrument: a table of semitone offsets (B-flat clarinet/trumpet -2, E-flat alto sax -9, F horn -7, A clarinet -3, piccolo +12, double bass +/-12, and so on) plus tonal's `Note.transpose`; the table needs a source (Wikipedia "Transposing instrument" and individual articles).
- Harmonic series: partial n has f x n. Run for a fundamental of 65.406 Hz: 1: C2, 2: C3, 3: G3 (+2c), 4: C4, 5: E4 (-14c), 6: G4 (+2c), 7: Bb4 (-31c), 8: C5 (verified output). This is a good "why is the 7th harmonic flat" answer tool.
- String and fret positions (equal temperament): distance from nut to fret n = L - L / 2^(n/12); verified on a 650 mm scale: fret 12 at 325.0 mm, fret 5 at 486.9 mm from the bridge.
- Pipe length: closed pipe f = v/4L, open pipe f = v/2L (standard physics; not run).

## 4. Verdict on the combined corpus

Good enough. Wikipedia alone: roughly 2.4M chars in about 125 pages over 5k chars, which is on the order of 2,400 chunks at 1,000 chars and about 1,300 chunks from just the 40 sampled popular instruments. Section structure is rich (median 10 top-level and 22 total sections for the 40 popular articles), which supports heading-aware chunking and section citations. Add the 4 Wikibooks acoustics pages and the Wikipedia theory-of-instruments pages above for physics and transposition. The Met API supplies structured, keyless tool data. This corpus is stronger than a patchy-person-data corpus because the data was measured, not assumed.

Risks:
1. Thin articles: the long tail (classification stubs like Conical drum 340 chars) is thin; apply a 5,000-char floor. Even popular ones vary (Piccolo 6.7k vs Double bass 103k), so retrieval will be dominated by long articles unless chunk counts per article are capped.
2. Naming and convention differences: English horn / Cor anglais, French horn / Horn, Bombardon / Tuba, Bb clarinet / Soprano clarinet; American vs British note-value names (quarter note vs crotchet) and pitch naming (B vs H in German) appear in text. Good for testing citations and aliases; need an alias table. Also Wikipedia titles disagree with common usage ("Horn (instrument)" vs the `French horn` redirect).
3. Share-alike: CC BY-SA 4.0 means the chunks (and arguably derived adaptations) must carry attribution and the same licence; a RAG chatbot that quotes sections should link the article and note CC BY-SA. Not legal advice. The Met data is CC0 (no condition). Do not mix in non-free sources.
4. Images and tables lost: `explaintext` drops images, and tables (instrument ranges, transposition tables, tuning tables) come out flattened or dropped. Not verified per page; check Transposing instrument and string-tuning tables before relying on them. Range and tuning facts may need to come from the hand-written tool table instead of retrieved text. Consider `action=parse&prop=text` HTML or the REST API (`/api/rest_v1/page/html/`) to keep tables.
5. API behaviour: one full-extract per request, rate limiting, and the Met v1/search retirement (2026-10-01). A one-off ingest script with caching avoids runtime dependence; Wikimedia dumps also exist (https://dumps.wikimedia.org/enwiki/latest/ returned 200) but I did not download or inspect them.
6. Wikipedia pages change daily; store the revision id and fetch date with each chunk.

## 5. Golden-set questions

| # | Type | Question | Answering page |
|---|---|---|---|
| 1 | Descriptive | How does a clarinet produce sound, and what is the register break? | https://en.wikipedia.org/wiki/Clarinet |
| 2 | Descriptive | What are the four Hornbostel-Sachs classes and which does a violin belong to? | https://en.wikipedia.org/wiki/Hornbostel%E2%80%93Sachs |
| 3 | Rule-based tool | What note does a B-flat clarinet sound when it reads a written C? (expected Bb3, from `Note.transpose("C4","-2M")`) | https://en.wikipedia.org/wiki/Transposing_instrument plus the tonal tool |
| 4 | Rule-based tool | An oboe tunes to 450 Hz instead of 440. How many cents sharp is that? (expected about +39) | https://en.wikipedia.org/wiki/Concert_pitch plus the cents tool |
| 5 | Rule-based tool | For a low C string at 65.4 Hz, what are the first eight harmonics and which are out of tune? | https://en.wikipedia.org/wiki/Harmonic_series_(music) plus the harmonic tool |
| 6 | Comparison | How do the viola and the violin differ in size, tuning and role? | https://en.wikipedia.org/wiki/Viola and https://en.wikipedia.org/wiki/Violin |
| 7 | Comparison | What separates a trumpet from a cornet? | https://en.wikipedia.org/wiki/Trumpet and https://en.wikipedia.org/wiki/Cornet |
| 8 | Different names / conventions | Is a "cor anglais" the same as an "English horn", and what key is it in? | https://en.wikipedia.org/wiki/Cor_anglais (English horn redirects here) |

An optional extra with the Met tool: "Show Indian chordophones in the Met collection" (the `culture` and `classification` fields, https://collectionapi.metmuseum.org/public/collection/v1/objects/500771 is an example).

## Recommendation

Go with instruments as the subject. Ingest about 125 to 150 Wikipedia articles chosen from the Hornbostel-Sachs links plus a hand-picked orchestral list (5k-char floor), plus the Wikipedia theory-of-instruments pages and the 4 Wikibooks acoustics pages; keep the Met API as an optional structured tool, and write the transposition table and the cents, harmonics and fret functions by hand around `tonal`. Fetch once with caching, store revision ids, show CC BY-SA attribution links in answers, and test table extraction early (risk 4) before committing to the design.
