# Context — D&D Campaign Manager

A glossary of shared domain terms across `dnd-play` and `dnd-core`. No implementation details here.

---

## Core Entities

**Campaign**
The overarching container for a D&D campaign. Holds the world, characters, NPCs, plot skeleton, breadcrumbs, and campaign-level settings (constraints, content preferences).

**CampaignSkeleton**
The DM's planned roadmap — plot hooks, NPC arcs, anticipated encounters, timeline of events. Written by the DM in advance; does not represent what has happened, only what was planned. Never shown to players.

**WorldState**
The realized world as it exists in play — locations visited, factions active, world events that have occurred, NPC states after player interaction.

**Entity**
Base class for anything that acts in the world: `CharacterSheet` (player characters) and `NPC` (non-player characters). Covers stats, action economy, conditions, death saves.

**CharacterSheet** (extends Entity)
A player character — ability scores, class, level, spell slots, skill proficiencies, equipment, known spells. Synonym: "character."

**NPC** (extends Entity)
A non-player character — role in the world (ally, merchant, quest-giver, antagonist), quest hooks, DM notes, monster stat block if combat-eligible. Synonym: "DMPC" when the DM plays it as a full participant.

**Breadcrumb**
A story history record created when characters experience something — an arc concluded, a location visited, an NPC met, a plot hook resolved or transformed. NOT a raw log; a Cliffs Notes version of what happened.

- `trigger_summary`: what mechanically happened
- `narrative`: the story the table wrote together
- `hide_from_players`: visibility flag
- `breadcrumb_log_level`: GLOBAL per campaign (off / major / minor / verbose)
- A plot hook going unexplored never becomes a breadcrumb

**CampaignSetup**
Campaign-level configuration — tone, pacing, safety settings, session zero config, and content generation preferences.

---

## Content Generation

**ContentSettings**
Per-user preferences controlling how LLM content is generated and how much the table relies on it.

- `generation_mode`: MANUAL | LLM_AUTO | LLM_ASK | USER_FILL — per user, orthogonal to log level
- `breadcrumb_log_level`: off | major | minor | verbose — global per campaign

**UserLLMSettings**
Per-user LLM provider configuration — which provider, model, API key, temperature, system prompt.

**LLM_SUGGESTED_REJECTED**
A draft/rejected content suggestion. Never persisted — discarded immediately after evaluation.

---

## Session Zero

**SessionZero**
Pre-campaign collaborative setup phase that creates a Campaign and collects player characters. Distinct from in-play game sessions. Phases: TONE → SAFETY → LOGISTICS → CHARACTER → REVIEW → ACTIVE.

**Participant**
A player in a Session Zero — name, role, their SessionZeroPhase responses, safety line / safety veil options.

**PhaseStatus**
Per-phase completion state: NOT_STARTED | IN_PROGRESS | COMPLETE | SKIPPED.

---

## Game State Machine

**GameLoop**
The top-level campaign state machine spanning all sessions. States: SESSION_ZERO → ACTIVE ↔ COMBAT | SOCIAL | EXPLORATION | DOWNTIME → CLOSED.

**GameSession**
A single play session — linked to a Campaign, tracks start/end time, associated breadcrumbs, notes. A session belongs to exactly one GameLoop state.

**Initiative**
Tracks turn order within COMBAT rounds. Rolled once at combat start; participants act in order each round.

---

## Architecture

**dnd-play** (`src/dnd_play/`)
FastAPI multiplayer server — HTTP REST API + WebSocket game loop coordinator. Owns campaigns, registries, sessions, messages. Thin persistence layer over SQLite.

**dnd-core** (`src/dnd_core/`)
Campaign Manager — pure domain models, state machine, persistence contract. No HTTP, no WebSocket. Consumed by dnd-play.

**Session Zero creates registries; dnd-core consumes them.**
