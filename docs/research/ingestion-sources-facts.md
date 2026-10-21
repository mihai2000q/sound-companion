# Ingestion sources: the three open facts

Checked 2026-10-21 for story 2 (issue 9) against primary sources only: live calls to the Wikipedia REST HTML endpoint, the MediaWiki and Wikimedia policy pages, and the Open Music Theory v1 site. Seven requests to Wikipedia in total, serial, with a descriptive User-Agent. Raw HTML and the throwaway flattening scripts live in the session scratchpad, not in the repo.

## Verdict table

| Item | Verdict | One-line reason |
|---|---|---|
| Transposing-instrument table survives extraction | partly | The data table is not on "Transposing instrument" (prose only) but on "List of transposing instruments". It survives, but only if `rowspan` is expanded; a naive row flatten drops the family column. |
| Tuning tables survive extraction | verified | "Musical tuning" and "Equal temperament" tables flatten to readable rows. Exponents and fractions are damaged if all `<sup>` tags are stripped. |
| Wikipedia rate-limit and User-Agent policy | verified | 200 requests per minute for unauthenticated bots with a compliant User-Agent, 10 per minute without one. We stay at about 1 per second, serial. |
| OMT v1 licence statement | verified | Page footer says "CC BY–SA 4.0" and links the deed. The about page states the reuse terms. No LICENSE file in the repo. |

## 1. Tables from the REST HTML endpoint

Method: `GET https://en.wikipedia.org/api/rest_v1/page/html/<Title>`, parsed with BeautifulSoup, every `<table>` flattened to rows of cells joined with ` | `.

**Revision id.** The response `etag` header starts with the revision id (`W/"1333051777/<uuid>/view"`), and the HTML `<html about="//en.wikipedia.org/wiki/Special:Redirect/revision/1333051777">` carries the same number. Either gives `revision_id` with no extra request.

### "Transposing instrument" has no data table

The article (revision 1381188338, about 12,000 characters of text) has five `<table>` elements, none with data: two "More citations needed" banners, two navboxes and an authority-control box. The instrument information is prose: reasons for transposing, transposition at the octave, mechanical considerations. It names families (clarinets in E♭, B♭, A; piccolo and double bass at the octave) but gives no per-instrument sounding pitch.

The data is on **List of transposing instruments** (revision 1333051777, about 98,000 characters of HTML). It has one `wikitable sortable` with 116 rows and 4 columns: *Instrument family, Instrument name, The note C4 written down produces, Comment*.

### Flattening that works

- **Expand `rowspan` and `colspan` into a grid first.** In the raw table the family cell ("Clarinet", "Trumpet") spans many rows and appears only in the first. Flattening each `<tr>` on its own gives rows like `Arpeggione | C 2 /C 3` (family missing, columns shifted). With the grid expanded, every row reads `Clarinet | B ♭ clarinet | B ♭ 3 | `.
- **Join `<sub>`** into its text, otherwise octave numbers come out as `B ♭ 3` with stray spaces. Spaces around the flat sign (`B ♭`) remain and need normalising to `Bb` before the values are used.
- **Strip citation markers only.** The family cell carries a footnote `<sup class="citation">` that leaks in as "Clarinet a". Remove `sup.reference` and `sup.citation`, not every `<sup>`: on "Equal temperament" the interval table's exponents (2^(n/12)) and fractions live in `<sup>` and `<math>`, and stripping all `<sup>` leaves cells like `2` instead of `2^(1/12)`.
- Drop `ambox` and `navbox` tables (banners and navigation) by class.

### What the list says for the tool's instruments

The column is the **sounding pitch for a written C4** (scientific pitch notation), not a semitone offset. Checked rows: Soprano clarinet (B♭ clarinet) B♭3, A soprano clarinet A3, E♭ clarinet E♭4, Bass clarinet B♭2, Trumpet B♭3, Horn F3, Cor anglais F3, Piccolo C5, Soprano saxophone B♭3, Alto saxophone E♭3, Tenor saxophone B♭2, Baritone saxophone E♭2, Guitar C3, Double bass C3 (listed under the Viol family). The table has no "A clarinet" row under that name (it is "A soprano clarinet"). Offsets for `transpose_for_instrument` are derived: sounding minus written, for example B♭3 − C4 is −2 semitones.

Gotchas for the hand-built table: the list has "Piccolo trumpet" under B♭4 (and C5 and A4 variants), the "Octobass" appears twice (C2 and C0), and Bagpipe has a "variable D♭4–D4" value. Treat only the rows the tool uses.

### Tuning tables

- "Musical tuning": one `wikitable`, 9 rows, columns *Instrument | Tuning* (violin G, D, A, E; guitar E, A, D, G, B, E; ukulele with its reentrant note; and so on). Reads cleanly.
- "Equal temperament": two `wikitable`s (13 and 14 rows). Cents and ratios survive. Superscripts and fractions are damaged if `<sup>` is stripped (see above).

## 2. Wikipedia rate-limit and User-Agent policy

Sources: https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits, https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy and https://www.mediawiki.org/wiki/API:Etiquette (all read 2026-10-21).

- **Limits** (per minute, unauthenticated, across the Action API and the REST API): requests with no identifying characteristics other than IP address, 10; unauthenticated browser requests, 200; unauthenticated bot requests with a compliant User-Agent, 200. The page says these limits are new in 2026 and subject to change.
- **On HTTP 429:** respect the `Retry-After` header. Without one, wait at least 5 seconds or back off exponentially.
- **User-Agent:** required on all requests. Format `<client name>/<version> (<contact information>) <library>/<version>`, with contact as an email or URL; including the string "bot" is recommended. Do not copy a browser's agent. Do not use generic agents such as `curl` or `Python-urllib`: these may be blocked without notice and can get a misleading error or HTTP 403.
- **Etiquette:** no hard speed limit on reads, but send requests in series, not in parallel, and use `maxlag` for non-interactive work.
- **Our setting:** one request at a time, about 1 per second (well under 200 per minute), User-Agent such as `SoundCompanionBot/0.1 (<repo URL>; <contact email>) httpx/<version>`, honour `Retry-After` on 429. The 1 per second figure in the domain document stays.

Not checked: how the limit is enforced in practice (I did not try to exceed it).

## 3. Open Music Theory v1 licence

- Every page footer (`_includes/footer.html` in the repo, and the live footer on https://openmusictheory.github.io/triads.html and `about.html`) ends with "CC BY–SA 4.0." linking `http://creativecommons.org/licenses/by-sa/4.0/`.
- https://openmusictheory.github.io/about.html states the terms: readers may "distribute, even sell its contents provided that you 1) attribute the original to us, and 2) pass on the same rights to others (which includes us!) by licensing your derivative work the same way we license this one", and refers to "the Creative Commons license deed linked on each page".
- The repository has no LICENSE file (`license: null` from the GitHub API, recorded in [music-theory-data.md](music-theory-data.md)). So the stored `license` value for OMT documents is `CC BY-SA 4.0`, and the source of that statement is the page footer and the about page.
- The footer has no author names in the template (`{{ site.owner.name }}`); the about page names the authors. Attribution links should therefore go to the page URL.

## Consequences for story 2

- Add **List of transposing instruments** to the Seed list. It is the citable source for the transposition table; "Transposing instrument" stays as the explanation.
- The ingest flattener must expand `rowspan` and `colspan`, join `<sub>`, keep non-citation `<sup>` and `<math>` text, and skip `ambox` and `navbox` tables.
- `revision_id` comes from the response `etag`, so no extra request per page.
