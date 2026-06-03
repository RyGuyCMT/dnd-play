# D&D Campaign Manager — Development Context

## Project overview

`dnd-play` is a multiplayer D&D session server with two packages:

- **`src/dnd_play/`** — FastAPI server. HTTP REST API + WebSocket game loop coordinator.
- **`src/dnd_core/`** — Campaign Manager. Pure domain models, state machine, persistence contract. No HTTP, no WebSocket.

`dnd-play` owns campaigns, registries, sessions, and messages. `dnd-core` holds the domain model and session management logic. Session Zero in dnd-play creates registries that dnd-core consumes.

## Agent skills

See `docs/agents/` for issue tracker, triage labels, and domain doc layout.

Available skills:
- **grill-with-docs** — relentless questioning to sharpen plans + update CONTEXT.md / ADRs on the fly
- **to-issues** — break a plan into tracer-bullet vertical slices filed as GitHub issues
- **triage** — move issues through the bug/enhancement × needs-triage/needs-info/ready-for-agent/ready-for-human/wontfix state machine
- **to-prd** — write a PRD from current context and publish to issue tracker
- **diagnose** — disciplined debugging: repro → minimize → hypothesise → instrument → fix → regression-test
- **tdd** — red-green-refactor with vertical tracer-bullet slices
- **zoom-out** — give me a map of the relevant modules in domain glossary terms

Skills that must be loaded before running the engineering skills above:
- **setup-matt-pocock-skills** — scaffolds `docs/agents/` (issue tracker, triage labels, domain doc layout); run once before first use of the above skills, or if they appear to be missing context.

## Domain glossary

See `CONTEXT.md` for the shared domain language — terms, concepts, entity relationships. No implementation details.

## Architectural decisions

See `docs/adr/` for ADRs — architectural decisions that were hard to reverse, surprising without context, and the result of real trade-offs.
