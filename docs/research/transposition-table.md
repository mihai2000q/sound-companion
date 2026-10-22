# Transposition table for transpose_for_instrument (story 49)

Checked on 2026-10-22 against the cached page `data/cache/wikipedia/List_of_transposing_instruments.html` (revision 1333051777, fetched 2026-10-21), the source named in decision 47. The page has one wikitable, "The note C4 written down produces", and `app/tools/instruments.py` copies the cell for each of the 14 instruments. The music21 interval is derived from it (sounding minus written C4), and a test checks every row against its cell.

| Instrument | Page's family row | Written C4 sounds | Interval |
|---|---|---|---|
| B-flat clarinet | Clarinet | Bb3 | M-2 |
| A clarinet | Clarinet (A soprano clarinet) | A3 | m-3 |
| E-flat clarinet | Clarinet | Eb4 | m3 |
| bass clarinet | Clarinet | Bb2 | M-9 |
| B-flat trumpet | Trumpet | Bb3 | M-2 |
| soprano saxophone | Saxophone | Bb3 | M-2 |
| alto saxophone | Saxophone | Eb3 | M-6 |
| tenor saxophone | Saxophone | Bb2 | M-9 |
| baritone saxophone | Saxophone | Eb2 | M-13 |
| F horn | Horn | F3 | P-5 |
| English horn | Cor anglais | F3 | P-5 |
| piccolo | Flute | C5 | P8 |
| guitar | Guitar | C3 | P-8 |
| double bass | Viol | C3 | P-8 |

- The Citation of every row is the list page itself (title, the family as section, URL, CC BY-SA 4.0), since that is where the offset comes from. The instruments' own articles were not used as sources for the offsets.
- The page labels the double bass under "Viol" and the piccolo under "Flute"; the Citation section follows the page.
- The page has more rows than the table (flutes, recorders, other clarinets and so on). Adding one is one line in `INSTRUMENTS`.
- Plain "clarinet", "saxophone" and similar names are deliberately not aliases, because the answer differs by kind. They return `unknown_instrument` with the list, so the bot asks which one.
