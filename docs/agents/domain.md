# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root: the domain glossary (music terms such as Note, Sounding pitch, Convention, Citation).
- **`docs/GLOSSARY.md`**: technical terms (RAG, RRF, SSE).
- **`docs/DECISIONS.md`**: the decision log, used in place of `docs/adr/`. Read entries that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
/
├── CONTEXT.md                         ← domain language
├── docs/
│   ├── GLOSSARY.md                    ← technical terms
│   └── DECISIONS.md                   ← numbered decision log
├── sound-companion.server/
└── sound-companion.client/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to the synonyms it lists under _Avoid_.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag decision conflicts

If your output contradicts an entry in `docs/DECISIONS.md`, surface it explicitly rather than silently overriding:

> _Contradicts decision 16 (PGVectorStore for core retrieval), but worth reopening because…_
