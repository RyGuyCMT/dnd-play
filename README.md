# dnd-play

> A real-time multiplayer D&D session server built with FastAPI + WebSockets.

## Index

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Key Flows](#key-flows)
- [Future Features](#future-features)

---

## Quick Start

### Prerequisites

- Python 3.11+
- `uv` (recommended) or `pip`

### Setup

```bash
# Clone the repo
git clone https://github.com/RyGuyCMT/dnd-play.git
cd dnd-play

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
cd /home/hermesadmin/dnd-play
PYTHONPATH=. DATA_PATH=./data SECRET_KEY=your-secret-key .venv/bin/uvicorn src.main:app --reload --port 8000
```

The API docs are available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

### Run Smoke Tests

```bash
source .venv/bin/activate
python smoke_test.py      # Core campaign + message flows
python smoke_registry.py  # Registry + Session Zero finalization
python smoke_game_loop.py # Game loop state machine transitions
```

---

## Architecture

### Packages

| Package | Path | Purpose |
|---------|------|---------|
| **dnd-play** | `src/dnd_play/` | FastAPI server — HTTP REST API, WebSocket coordinator, persistence |
| **dnd-core** | `src/dnd_core/` | Campaign Manager — domain models, state machines, LLM interfaces |

### Key Components

**dnd-play server (`src/dnd_play/`)**
- `main.py` — FastAPI bootstrap, CORS, routing, lifespan
- `websocket.py` — `WSManager` singleton; WebSocket rooms per campaign; scope-aware broadcast
- `auth.py` — HMAC-SHA256 token generation (DM token returned only at creation time)
- `models/` — `Campaign`, `Character`, `GameSession`, `Message` (with `RecipientScope`), `CampaignRegistry`
- `api/` — REST endpoints for campaigns, sessions, characters, messages, registries
- `persistence/` — `LocalStorageAdapter` (JSON files), `Repository`, `RegistryService`

**dnd-core (`src/dnd_core/`)**
- `models/` — Domain entities (`Entity` base, `Campaign`, `GameSession`, `WorldState`, `NPC`, `CharacterSheet`, `SessionZero`, `Breadcrumb`)
- `state_machine/` — `GameStateMachine` (mode transitions), `CombatStateMachine` (phase loop), `GameEngine` (deterministic mechanics)
- `llm_interface/` — `PlayerInterface` (filtered lens), `DMInterface` (full access), `Narrator`
- `persistence/` — `StorageAdapter` ABC + `LocalStorageAdapter`; JSON to `~/.hermes/dnd-sessions/`

### Session Zero Flow

1. DM creates a campaign → receives a `dm_token`
2. Players submit characters → marked `PENDING`
3. DM reviews/approves/rejects characters
4. DM activates campaign → `CampaignPhase.REVIEW` → `CampaignPhase.ACTIVE`
5. Registry is finalized → points to campaign, world state, and character JSON files

### Game Loop States

The server manages a state machine per active session. States include:

- `EXPLORING` — overworld travel, dungeon navigation
- `SOCIAL` — NPC conversations, intrigue
- `COMBAT` — initiative-based encounter, round loop
- `DOWNTIME` — session-end rest, shopping, training
- `SESSION_ZERO` — pre-campaign setup

See `docs/game-loop-states.md` for the full 12-state research model.

### Real-time Messaging

WebSocket broadcasts support three scopes:
- **`BROADCAST`** — DM → all players
- **`SINGLE`** — DM → one player (whisper)
- **`PARTY`** — DM → subset of players

---

## Key Flows

### Create a Campaign + Run Session Zero

```bash
# 1. Create campaign
curl -X POST "http://localhost:8000/campaigns?title=The+Lost+Mines"

# Response: { "id": "...", "dm_token": "..." }
# Save the dm_token — it's shown only once

# 2. Register characters (as DM)
curl -X POST "http://localhost:8000/campaigns/{id}/characters?role=dm&campaign_id={id}" \
  -H "Authorization: Bearer {dm_token}" \
  -d '{"name": "Grog", "player_id": "ryan"}'

# 3. Review character
curl -X POST "http://localhost:8000/campaigns/{id}/characters/Grog/review?role=dm&campaign_id={id}&status=approved" \
  -H "Authorization: Bearer {dm_token}"

# 4. Activate campaign (Session Zero complete)
curl -X POST "http://localhost:8000/campaigns/{id}/phase?role=dm&campaign_id={id}&phase=active" \
  -H "Authorization: Bearer {dm_token}"
```

### Start a Session + Advance Game Loop

```bash
# Start session
curl -X POST "http://localhost:8000/campaigns/{id}/sessions/start?role=dm&campaign_id={id}" \
  -H "Authorization: Bearer {dm_token}"

# Transition to COMBAT
curl -X POST "http://localhost:8000/campaigns/{id}/sessions/1/game-loop?role=dm&campaign_id={id}" \
  -H "Authorization: Bearer {dm_token}" \
  -d '{
    "state_type": "COMBAT",
    "surprise": "npc",
    "initiative_order": ["Grog", "Goblin"]
  }'

# Advance round
curl -X POST "http://localhost:8000/campaigns/{id}/sessions/1/game-loop/advance-round?role=dm&campaign_id={id}" \
  -H "Authorization: Bearer {dm_token}"
```

---

## Future Features

| Feature | Description | Issue |
|---------|-------------|-------|
| Initiative tracker UI | Visual turn order + round counter for COMBAT | [#3](https://github.com/RyGuyCMT/dnd-play/issues/3) |
| LLM NPC integration | AI-driven NPCs with structured prompt/response interface | [#4](https://github.com/RyGuyCMT/dnd-play/issues/4) |
| Character sheet UI | Frontend for building and viewing character sheets | [#5](https://github.com/RyGuyCMT/dnd-play/issues/5) |
| Breadcrumb export | Export campaign log to Markdown / JSON / PDF | [#6](https://github.com/RyGuyCMT/dnd-play/issues/6) |
| Persistent world state | DB-backed world state with history | future |

---

## Project Status

**Open issues:** 1 (documentation)

See [GitHub Issues](https://github.com/RyGuyCMT/dnd-play/issues) for full tracker.

Last smoke tests pass: `smoke_test.py`, `smoke_registry.py`, `smoke_game_loop.py` — all green on `master`.

---

## Project Layout

```
dnd-play/
├── src/
│   ├── main.py              # FastAPI app entry point
│   ├── websocket.py          # WS manager + broadcast
│   ├── auth.py               # HMAC token utilities
│   ├── config.py             # Settings
│   ├── api/                  # REST route handlers
│   │   ├── campaigns.py
│   │   ├── session_zero.py   # Session Zero endpoints
│   │   ├── game_loop.py
│   │   └── registries.py
│   ├── models/               # Pydantic request/response + domain dataclasses
│   ├── persistence/          # JSON file storage adapters
│   ├── services/             # Business logic
│   └── dnd_core/             # Campaign Manager (domain models, state machines)
│       ├── models/
│       ├── state_machine/
│       ├── llm_interface/
│       └── persistence/
├── docs/
│   ├── adr/                  # Architectural Decision Records
│   ├── agents/               # Agent skill definitions
│   └── game-loop-states.md  # Game loop state research
├── smoke_test.py             # Core smoke tests
├── smoke_registry.py         # Registry smoke tests
├── smoke_game_loop.py        # Game loop smoke tests
├── CLAUDE.md                 # Agent context
├── CONTEXT.md                # Domain glossary
└── README.md                 # This file
```