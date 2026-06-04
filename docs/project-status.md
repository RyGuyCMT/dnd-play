# Project Status

**Last updated:** 2026-06-04 (automated cron run)

---

## Open Issues

| # | Title | Labels |
|---|-------|--------|
| — | No open issues | — |

All issues resolved.

---

## This Run

| Issue | Action | Commit | Status |
|-------|--------|--------|--------|
| #1 — `_pending_characters` typo | Fixed `_pending_characters` → `pending_characters` at 3 locations in `src/api/session_zero.py`. All 3 smoke tests pass. | `5ab13ea` | Closed |
| #2 — Missing README.md | Created `README.md` with Quick Start, architecture overview, key flows, future features table, project layout. All acceptance criteria met. | `fa41fd6` | Closed |

---

## Smoke Tests

All passing on `master`:

```
smoke_test.py      ✓ Core campaign + message flows
smoke_registry.py  ✓ Registry + Session Zero finalization
smoke_game_loop.py ✓ Game loop state machine transitions
```

Run with:
```bash
.venv/bin/python smoke_test.py
.venv/bin/python smoke_registry.py
.venv/bin/python smoke_game_loop.py
```

---

## Active Development

**Current focus:** COMBAT initiative tracker and WebSocket game-loop broadcasts.

### Module Status

| Module | Status | Notes |
|--------|--------|-------|
| `dnd-play` server | Active | FastAPI + WebSocket real-time messaging |
| Session Zero | Complete | SETUP→REVIEW→ACTIVE phase model |
| GameLoop state machine | Complete | Fully built and smoke-tested |
| `dnd-core` Campaign Manager | Active | Phase 3: Session Zero system |
| LLM interface | Partial | Scaffold complete, some methods return `{"status": "pending"}` |

### Stub Directories (pending implementation)

- `src/dnd_core/effects/`
- `src/dnd_core/engine/`
- `src/dnd_core/rules/`

### Open Questions

- [ ] dnd-core README missing — should document purpose, setup, and architecture
- [ ] Effects/engine/rules stubs — what goes here?
- [ ] LLM interface wiring incomplete — some methods return `{"status": "pending"}`
- [ ] Breadcrumb export (Markdown, JSON, PDF) — deferred
- [ ] Frontend testing — no test infrastructure visible

---

## Git Log (recent)

```
fa41fd6 docs: add README.md to project root closes #2
5ab13ea fix: _pending_characters → pending_characters in session_zero.py
9e68f6a chore: remove cached .pyc/__pycache__ from git index
decdfb4 docs: CLAUDE.md, CONTEXT.md, agents/ scaffold, .scratch/
65a9cca chore: add .gitignore
576e7b0 feat(dnd-core): initial commit of Campaign Manager
8f9822e feat: WS game-loop broadcasts + Initiative model
```

---

## Conventions

- **Commit format:** `type: short description closes #N`
- **Standing order:** commit+push after every good-sized dev chunk
- **Persistence:** JSON file storage (no database)
- **Session Zero output:** `CampaignRegistry` — pointer document to external JSON files