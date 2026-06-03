# Domain Docs

Single-context repository. One `CONTEXT.md` and one `docs/adr/` at the repo root.

## File structure

```
/
├── CONTEXT.md              ← project glossary (terms, concepts)
├── docs/
│   ├── adr/                ← architectural decision records
│   │   └── NNNN-title.md
│   └── agents/             ← agent configuration (issue tracker, triage labels)
└── src/
    ├── dnd_play/           ← FastAPI multiplayer server
    └── dnd_core/           ← Campaign Manager (models, state machine)
```

## Reading rules

- `grill-with-docs`, `triage`, `to-issues`, `diagnose`, `tdd` read `CONTEXT.md` first
- ADRs in `docs/adr/` encode hard-to-reverse decisions that surprised without context
- See `CONTEXT.md` for the domain glossary
