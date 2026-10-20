# Music theory as a RAG subject: data verification

> **Status note:** the corpus findings (sections 1 to 3 and 5) still apply. The tool-layer findings about `tonal` (section 4) were superseded when the backend moved to Python, see [python-stack-spike.md](python-stack-spike.md) Part B for the Python libraries actually used.

Checked on 2026-10-19 against primary sources only (site pages, licence pages, official APIs, npm registry, package source). No API keys used, no paid calls, no existing files modified. Scratch work lives under the session scratchpad, not in the repo.

## Verdict table

| Item | Verdict | One-line reason |
|---|---|---|
| Open Music Theory v1 (GitHub markdown) | verified | CC BY-SA 4.0 (stated in site footer), 129 .md files, ~78k words, clonable |
| Open Music Theory 2e (current edition) | partly | CC BY-SA 4.0 confirmed via LibreTexts mirror; the original host (viva.pressbooks.pub) returned HTTP 403 to curl, so fetchability from source is unverified |
| Wikipedia articles | verified | CC BY-SA 4.0, `action=parse&prop=sections` and REST html both return headings; 40/40 seed titles exist |
| Wikibooks "Music Theory/" | partly | Licence and API verified, but only 64 subpages / ~47k words, 21 under 300 words, many stubs |
| Other open textbooks (LibreTexts) | verified | Licence tag read per book; only CC BY / CC BY-SA ones are usable without NC limits |
| `tonal` npm package | verified | v6.5.1, MIT, installed and ran 15 calls successfully |
| Free keyless non-local API | partly | Open Opus (classical metadata, keyless) and MusicBrainz work; no keyless chord/theory API found (Uberchord returned 525, Hooktheory needs login) |
| Overall corpus for ~150 docs / few thousand chunks | partly | Enough volume and structure; thin-page and licence share-alike caveats below |

## 1. Open Music Theory (OMT)

- Two editions exist. v1 is the GitHub Jekyll site `openmusictheory/openmusictheory.github.io`; 2e is a newer edition (Gotham et al.) hosted at viva.pressbooks.pub/openmusictheory and mirrored on LibreTexts.
- v1 licence: every page footer says "CC BY-SA 4.0" and links https://creativecommons.org/licenses/by-sa/4.0/ (source: `_includes/footer.html` in the repo, and the live footer at https://openmusictheory.github.io/triads.html). The about page states the reuse terms: attribute, and license derivatives the same way (https://openmusictheory.github.io/about.html).
- The GitHub repo has no LICENSE file; the GitHub API reports `license: null` (https://api.github.com/repos/openmusictheory/openmusictheory.github.io). The licence is therefore only declared in the page footer and about page, not in a repo licence file.
- Fetching: the repo is clonable (`git clone --depth 1 https://github.com/openmusictheory/openmusictheory.github.io.git`). All text is Markdown with Jekyll front matter (`layout`, `title`). The about page confirms "all text is in the very user-friendly Markdown format" and that single files can be downloaded.
- Size (measured on my clone): 129 `.md` files at repo root, ~78,112 words in total including non-content files (404, README, how-to stubs such as addCC.md, trinket.md). Per-file median 480 words, max 1,945. A sensible content subset is roughly 100 pages. `contents.md` lists the chapter order and `sitemap.xml` exists.
- Structure: pages use `##` / `###` headings (triads.md has "Identifying and labeling triads", "Triad roots", "Triad qualities", "Lead-sheet symbols", "Roman numerals", "Building a triad", "Seventh chords"). Images are reference-style `![..][name]` with link definitions at file bottom, so image text must be stripped.
- Currency: last commit in my clone is 2022-07-20 ("Update _config.yml"); GitHub reports `pushed_at` 2024-07-10 (the repo's last push). v1 is the older edition; LibreTexts lists both "Open Music Theory 1e (Wharton and Shaffer Eds)" and "2e (Gotham et al.)". So v1 is stable but not actively developed.
- 2e: LibreTexts page says "shared under a CC BY-SA 4.0 license ... Mark Gotham, Kyle Gullings, Chelsey Hamm, Bryn Hughes, Brian Jarvis, Megan Lavengood, John Peterson", source tag `https://viva.pressbooks.pub/openmusictheory/` (https://human.libretexts.org/Bookshelves/Music/Music_Theory/Open_Music_Theory_2e_(Gotham_et_al.)). Its chapters include Fundamentals, Counterpoint and Galant Schemas, Form, Diatonic Harmony, Chromaticism, Jazz, Popular Music, 20th/21st-Century Techniques, Twelve-Tone, Orchestration, Rhythm and Meter. Not confirmed: size, and whether the pressbooks host allows scripted fetching (HTTP 403 with two user agents).

## 2. Wikipedia and Wikibooks

- Licence: `meta=siteinfo&siprop=rightsinfo` returns "Creative Commons Attribution-Share Alike 4.0" for both en.wikipedia.org and en.wikibooks.org (https://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=rightsinfo&format=json, same path on en.wikibooks.org).
- Attribution rule (Terms of Use): credit by hyperlink or URL to the page (each page's history lists authors), or to a stable alternative copy that credits authors equivalently. Derivatives must be CC BY-SA compatible; GFDL-only imports are not allowed. Non-text media follow their own licences. (https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)
- Fetching with headings, both confirmed:
  - `https://en.wikipedia.org/w/api.php?action=parse&page=Circle_of_fifths&prop=sections&format=json&formatversion=2` returned 20 sections with `level` and `line` (e.g. level 2 "Definition", level 3 "Diatonic key signatures").
  - `https://en.wikipedia.org/api/rest_v1/page/html/Circle_of_fifths` returned 200, ~186 KB, with `<h2 id="Definition">`, `<h3 ...>` and 21 `<section>` elements.
  - `action=query&prop=extracts&explaintext=1` returns plain text with `== Heading ==` markers (3,416 words for Circle of fifths).
  - Same `parse` call on Wikibooks (`Music_Theory/Scales_and_Intervals`) returned 15 sections; Wikibooks REST html returned 200.
- Category sizes (en.wikipedia categoryinfo): Category:Music theory 72 pages + 21 subcats; Intervals (music) 30 pages + 24 subcats; Musical scales 43 + 16; Rhythm and meter 87 + 13; Musical forms 28 + 5. A 150-article seed list is easily reachable (these top-level pages alone sum to ~260 before subcategories, with overlaps).
- 40 seed titles tested, all exist (word counts from the extracts API; `->` marks a redirect):
  Interval (music) 7,230; Chord (music) 1,359; Scale (music) 2,842; Major scale 1,784; Minor scale 738; Mode (music) 5,665; Dorian mode 1,180; Circle of fifths 3,416; Key signature 3,169; Cadence 3,591 (Perfect cadence redirects here); Roman numeral analysis 1,360; Seventh chord 1,482; Function (music) 1,944 (from "Diatonic function"); Voice leading 990; Counterpoint 3,530; Sonata form 7,626; Rondo 2,413; Time signature 3,994; Syncopation 1,564; Equal temperament 1,667; Just intonation 1,418; Pythagorean tuning 2,230; Pitch class 1,308; Set theory (music) 2,176; Twelve-tone technique 2,973; Tritone 3,251; Neapolitan chord 2,341; Secondary chord 1,963; Modulation (music) 2,855; Figured bass 1,880; Solfège 2,232; Tonic (music) 690; Dominant (music) 777; Augmented sixth chord 2,418; Enharmonic equivalence 1,505 (from "Enharmonic"); Jazz chord 2,401; Chord progression 2,473; Twelve-bar blues 836; Polyrhythm 3,811; plus Scientific pitch notation 1,219, Musical note 2,742, Quarter note 316. Mean for the 40 core titles is roughly 2,400 words, 5 to 21 `==` sections each.
- Wikibooks: `Music Theory/` prefix has 64 pages totalling ~46,900 words (search `prefix:"Music Theory/"` wordcounts); median 476 words, 21 pages under 300 words, 16 pages over 1,000. The root page "Music Theory" itself is 198 words. The `Music Theory/Metal` page (4,901 words) is the largest. Wikibooks is usable for chapter-style text (Scales and Intervals 2,509; Blues 1,956; Fundamentals of Common Practice Music/Notation 1,925) but many subpages are stubs (several returned empty extracts, e.g. Triads, Syncopation, Serialism).

## 3. Other open textbooks (licence read on each LibreTexts book page, shelf https://human.libretexts.org/Bookshelves/Music/Music_Theory)

| Book | Licence read | Reuse note |
|---|---|---|
| Open Music Theory 2e (Gotham et al.) | CC BY-SA 4.0 | same as v1 |
| Open Music Theory 1e (Wharton, Shaffer) | CC BY-SA (tag `ccbysa`) | the GitHub v1 |
| Music Fundamentals (Ewell, Schmidt-Jones) | CC BY 3.0 | no share-alike |
| Understanding Basic Music Theory (Schmidt-Jones) | CC BY 3.0 | no share-alike |
| Sound Reasoning (Brandt, McClure; OpenStax CNX) | CC BY | no share-alike |
| Fundamentals, Function, and Form (Mount, Rothfarb) | CC BY-NC 4.0 | non-commercial only |
| A Practical Approach to Understanding Music Theory (Brooks) | CC BY-NC 4.0 | non-commercial only |
| Music Theory for the 21st-Century Classroom (Hutchinson) | GNU FDL 1.3 | copyleft, awkward to combine |
| Music Theory (LibreTexts) | tag `ccbyncsa` | NC + SA |

- LibreTexts robots.txt asks for `Crawl-delay: 5` (https://human.libretexts.org/robots.txt), so bulk fetching is slow but permitted; I did not test per-chapter extraction or a LibreTexts API.
- The CC BY books (Schmidt-Jones, Ewell, Brandt) are the most permissive and are worth adding for plain-language explanations. For a student project, NC books are probably still acceptable (non-commercial) but should be flagged.

## 4. Tools

### `tonal` (npm)
- Registry: `tonal` latest 6.5.1, MIT, published 2026-10-14, not deprecated, repo https://github.com/tonaljs/tonal (https://registry.npmjs.org/tonal). `tonaljs` (unscoped) does not exist on the registry ("Not found"). `@tonaljs/tonal` is the old scope, last at 4.10.0 (2023-01-12).
- Installed in a fresh scratch dir; `tonal` bundles sub-packages: abc-notation, array, chord, chord-detect, chord-type, collection, core, duration-value, interval, key, midi, mode, note, pcset, pitch, pitch-distance, pitch-interval, pitch-note, progression, range, rhythm-pattern, roman-numeral, scale, scale-type, time-signature, voice-leading, voicing, voicing-dictionary. ESM and CJS builds ship (`main`/`module`). 107 chord types and 92 scale types were available at runtime.
- 15 sample calls, real output (Node, ESM import from "tonal"):

| Call | Output |
|---|---|
| `Scale.get("C major").notes` | C D E F G A B |
| `Chord.get("Cmaj7").notes` | C E G B (name "C major seventh") |
| `Interval.distance("C4","G4")` | 5P (7 semitones) |
| `Chord.transpose("Dm7","5P")` | Am7 |
| `Chord.detect(["C","E","G","B"])` | [Cmaj7] |
| `Chord.detect(["D","F","A","C"])` | [Dm7, F6/D] (ambiguity, interesting for citations) |
| `Key.majorKey("C").chords` | Cmaj7 Dm7 Em7 Fmaj7 G7 Am7 Bm7b5 |
| `Progression.fromRomanNumerals("C",["IIm7","V7","Imaj7"])` | Dm7 G7 Cmaj7 |
| `Progression.toRomanNumerals("C",["Dm7","G7","Cmaj7"])` | IIm7 V7 Imaj7 |
| `Mode.names()` / `Scale.get("D dorian")` | seven modes / D E F G A B C |
| `Scale.detect(["C","D","E","F#","G","A","B"])` | [C lydian, C ichikosucho, C chromatic] |
| `Note.midi("C4")`, `Note.freq("A4")`, `Note.enharmonic("C#")` | 60, 440, Db |
| `Key.minorKey("A").natural.scale`; `Key.majorKey("Eb").minorRelative` | A B C D E F G; C |
| `Chord.get("Xyz")`, `Note.get("H4").empty` | empty object, true (invalid input does not throw; H is not accepted) |
| `RomanNumeral.get("bVII")` | interval 7m, alt -1 |

- Coverage of the requested areas: note (Note), interval (Interval), chord (Chord, ChordType, chord-detect), scale (Scale, ScaleType), key (Key), progression (Progression, RomanNumeral), transposition (Note/Chord/Interval.transpose), modes (Mode), plus pcset, voice-leading, voicing, rhythm-pattern, time-signature.
- Quirks worth knowing: `Scale.detect` returns exotic scale names alongside common ones; spelling is in tonal's own conventions (C4 = MIDI 60, "M7"/"maj7" aliases, `5P` interval notation). No audio or notation rendering.

### Non-local keyless APIs
- Open Opus (classical composers and works): `https://api.openopus.org/composer/list/search/beethoven.json` returned HTTP 200 with JSON; `.../work/list/composer/145/genre/all.json` returned 344 works. Official site says "free and open source", "requires no registration at all", data "in the public domain" (https://openopus.org/). Useful for history-of-theory style questions (composer, epoch, works), not for theory itself. Operated by a small project funded on Patreon, so expect no SLA.
- MusicBrainz: `https://musicbrainz.org/ws/2/artist/?query=bach&fmt=json&limit=1` returned 200 with JSON today. (Already known; usage requires a meaningful User-Agent per their docs, which I did not re-read.)
- Not usable: Uberchord API `https://api.uberchord.com/v1/chords/Am` returned HTTP 525 (down); Hooktheory API docs say it authenticates with a Bearer token obtained with a hooktheory.com username and password, so not keyless (https://www.hooktheory.com/api/trends/docs).
- Conclusion: `tonal` is the real tool layer (local, deterministic). A keyless remote tool exists only for classical metadata.

## 5. Overall verdict, risks

Verdict: usable. OMT v1 (~100 content pages) + ~150 Wikipedia articles (~360k words) + optionally ~47k Wikibooks words and one or two CC BY books gives roughly 450k to 550k words. At 200 to 300 words per chunk that is about 1,800 to 2,800 chunks, with real `##`/`###` section structure in every source. That meets "150 documents, a few thousand chunks" without needing 2e.

Risks:
- Share-alike: Wikipedia, Wikibooks and OMT are CC BY-SA 4.0. A chatbot that quotes passages must attribute (link to the article/page) and, if the corpus is redistributed, the redistributed corpus stays CC BY-SA. Mixing in BY-NC or GFDL books complicates redistribution. Keep a per-document `source_url`, `licence`, `revision_id` field.
- Duplicated content: Wikipedia articles overlap each other (Cadence vs Perfect cadence redirect; Interval vs Tritone), and OMT overlaps Wikipedia conceptually. Dedupe by canonical title after redirect resolution.
- Thin pages: Wikipedia stubs (Tonic 690, Dominant 777, Quarter note 316) and many Wikibooks subpages under 300 words; set a minimum length and prefer Wikipedia plus OMT.
- Notation and media: OMT is full of images and audio for examples (reference-style image links, no text alternative), and Wikipedia has music glyphs and `{{Music}}` rendered as images; text-only chunks will sometimes lack the example being discussed. Unicode accidentals (♭, ♯) appear in extracts.
- Regional/convention differences: OMT picks ISO register naming (middle C = C4, pitches.md); Wikipedia's Musical note notes that Germany and Czechia use H for B and that quarter note is crotchet in British English (confirmed in the extracts). tonal rejects "H4" as a note.
- Sources that disagree (good for citations): chord symbol styles (OMT lead-sheet "Caug"/C+ vs Wikipedia's "Chord notation"), tritone/augmented fourth vs diminished fifth naming, major seventh symbols, modal names vs church modes, Roman numeral case conventions, American vs British duration names, `Chord.detect` returning multiple answers (Dm7 vs F6/D).
- Volatility: Wikipedia text changes; pin revision ids at fetch time. OMT v1 is frozen since 2022/2024; OMT 2e could not be fetched from its host.
- Not confirmed: Wikipedia API rate-limit and User-Agent policy page (I sent a descriptive User-Agent and had no throttling on ~100 requests, but did not read the policy); Open Opus uptime; OMT 2e size; LibreTexts per-chapter text extraction.

## 6. Eight golden-set questions

| # | Question | Type | Expected source |
|---|---|---|---|
| 1 | What is the circle of fifths and how does it relate to key signatures? | descriptive | Wikipedia "Circle of fifths" (sections Definition, Diatonic key signatures); OMT keySignatures.md |
| 2 | Which notes are in the C major scale, and what are the notes of Cmaj7? | rule-based, tool | tonal `Scale.get`, `Chord.get`; text from Wikipedia "Major scale", "Seventh chord" |
| 3 | What interval is it from C4 to G4, and how many semitones? | rule-based, tool | tonal `Interval.distance`; OMT intervals.md, Wikipedia "Interval (music)" |
| 4 | Transpose Dm7 up a perfect fifth; what chord do I get? | tool | tonal `Chord.transpose` (Am7); OMT transposition.md |
| 5 | Which chord is made of the notes D, F, A, C? | tool with ambiguity | tonal `Chord.detect` (Dm7 or F6/D); Wikipedia "Seventh chord", "Chord notation" |
| 6 | Compare the perfect authentic cadence with the half cadence and the plagal cadence. | comparison | Wikipedia "Cadence"; OMT cadenceTypes.md |
| 7 | Compare the Dorian and Mixolydian modes: which scale degrees differ from major and minor? | comparison, tool-aided | Wikipedia "Mode (music)", "Dorian mode"; tonal `Scale.get("D dorian")` |
| 8 | In the key of C, what is "middle C" called, and what do German speakers call B-flat and B natural? | conflicting conventions | OMT pitches.md (C4 = middle C, ISO); Wikipedia "Musical note" (H/B naming), "Scientific pitch notation" |

## Recommendation

Choose music theory, with this corpus: OMT v1 markdown (git clone, CC BY-SA) + Wikipedia seed list via the `parse`/REST html endpoints (CC BY-SA) as the backbone; add Schmidt-Jones/Ewell (CC BY 3.0) if more plain-language text is needed. Use `tonal` as the tool-calling layer (local, MIT, verified), and optionally Open Opus for a non-local tool. Treat Wikibooks as optional. Record licence and revision per document, and put at least three of the convention-conflict questions in the golden set. Before committing to OMT 2e, test fetching from viva.pressbooks.pub in a browser or via the LibreTexts mirror.
