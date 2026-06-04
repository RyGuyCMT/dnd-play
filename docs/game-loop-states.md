# Game Loop State Model — Research Summary
# Generated: 2026-05-27

---

## STATE INVENTORY (12 candidate states)

### 1. SESSION-ZERO
**Purpose:** Pre-campaign setup — configure campaign, collect characters, activate.

| Property | Value |
|----------|-------|
| `initiative` | `None` — no turn order |
| `surprise` | `None` — no surprise |
| `infinite` | `False` — runs once, stops at ACTIVE |
| `sequence` | `[SETUP, REVIEW, ACTIVE]` |
| `broadcast_scope` | `DM` only during SETUP/REVIEW; `ALL` on ACTIVE |
| `allowed_actions` | DM: configure, review-characters, approve/reject, activate |
| `exit_trigger` | DM calls activate → transitions to ACTIVE |
| `notes` | No player actions until ACTIVE |

---

### 2. ACTIVE
**Purpose:** General campaign play — free-form, not in any special state.
Acts as the "idle" state between structured states.

| Property | Value |
|----------|-------|
| `initiative` | `None` — no turn order |
| `surprise` | `None` |
| `infinite` | `True` — runs until DM transitions |
| `sequence` | `[PLAYER_ACTION, RESOLUTION, NEXT]` (very loose) |
| `broadcast_scope` | `ALL` — all players see everything |
| `allowed_actions` | Anything: movement, exploration, social, item use, etc. |
| `exit_triggers` | DM initiates → COMBAT (hostile encountered), SOCIAL (NPC interaction), EXPLORATION (travel/hex crawl), DOWNTIME (session end) |
| `notes` | This is the "hub" state. Most session time is here. |

---

### 3. COMBAT
**Purpose:** Structured hostile encounter with initiative and round economy.

| Property | Value |
|----------|-------|
| `initiative` | `True` — rolled once at combat start, used every round |
| `surprise` | `None \| "party" \| "npc"` — resolved once at combat start |
| `infinite` | `True` — loops until all hostiles dead or DM exits |
| `sequence` | `[ROLL_INITIATIVE, RESOLVE_SURPRISE, ROUND_LOOP]` |
| `round_sequence` | Per participant, in initiative order: `[MOVE, STANDARD_ACTION, BONUS_ACTION, REACTION]` |
| `broadcast_scope` | `ACTIVE` — only current initiative character acts; `DM` sees all |
| `allowed_actions` | Per participant class/features: Attack, Cast Spell, Dash, Disengage, Dodge, Help, Hide, Ready Action, Search, Use Object, etc. |
| `exit_triggers` | All NPCs dead → ACTIVE; DM calls retreat/escape → ACTIVE or CHASE |
| `notes` | round_options tags: `move`, `standard_action`, `bonus_action`, `reaction`, `free_action`, `object_interaction`, `defensive_action` |

**Action tags and mutual exclusivity:**
- `full_round_action` greys out: `ready_action`, `defensive_action`, `move_action`, `standard_action`, `attack_action`, `bonus_action`
- `move_action` — does not grey others
- `bonus_action` — greyed by `full_round_action`
- `reaction` — independent, usable anytime

---

### 4. CHASE
**Purpose:** Contested speed/movement — one or more targets fleeing.

| Property | Value |
|----------|-------|
| `initiative` | `True` — rolled at start, order of who acts first |
| `surprise` | `None` or party/npc (pre-resolved before chase start) |
| `infinite` | `True` — loops until chase ends |
| `sequence` | `[ROLL_INITIATIVE, CHASE_ROUND]` |
| `round_sequence` | Each participant in initiative: `[SPEED_CHECK, ACTION, COMPLICATION_CHECK]` |
| `broadcast_scope` | `ACTIVE` (current actor) + `DM` + fleeing target |
| `allowed_actions` | Dash, Disengage, Cast Movement Spell, Hide, Search (complication), Improvised |
| `exit_triggers` | Catchers reach target → COMBAT or capture; Fleers escape hex/area → chase ends |
| `notes` | Distance tracked in feet/rounds. Terrain complications. Prey can do cunning actions (disappear, set trap). |

---

### 5. SOCIAL
**Purpose:** Non-combat interaction with NPC factions, dialog, persuasion.

| Property | Value |
|----------|-------|
| `initiative` | `None` — not turn-based |
| `surprise` | `None` |
| `infinite` | `False` — runs until resolution (success/failure/escalation) |
| `sequence` | `[ENGAGE, SKILL_CHECKS, OUTCOME]` |
| `broadcast_scope` | `DM` + active participant + NPC |
| `allowed_actions` | Persuasion, Deception, Intimidation, Insight, Performance, Search (for social cues) |
| `exit_triggers` | NPC succeeds/fails check threshold → COMBAT, ACTIVE, DOWNTIME |
| `notes` | Can use "social HP" / influence track (DMG skill challenge variant). Multiple checks can be made over multiple rounds. Escalation to COMBAT possible. |

**Social state properties (unique to this state):**
- `npc_disposition` — friendly/neutral/hostile
- `influence_track` — like temporary HP for social standing
- `secrets_known` — what player knows vs what NPC knows
- `context_tags` — bribery, intimidation, charm, diplomacy, deception

---

### 6. EXPLORATION
**Purpose:** Overworld/wilderness movement and discovery.

| Property | Value |
|----------|-------|
| `initiative` | `None` — not turn-based |
| `surprise` | `None` — but random encounters possible |
| `infinite` | `True` — until destination reached or DM transitions |
| `sequence` | `[TRAVEL, EVENT_CHECK, DISCOVERY]` |
| `broadcast_scope` | `ALL` |
| `allowed_actions` | March (speed), Search, Forage, Stealth, Navigate, Rest, Interact |
| `exit_triggers` | Arrive at destination → ACTIVE; random encounter → COMBAT; time-based → DOWNTIME |

**Exploration state properties:**
- `terrain_type` — forest/mountain/swamp/urban etc.
- `travel_speed` — affected by terrain and encumbrance
- `hex_grid` — optional hex-based tracking
- `random_encounter_chance` — per day/hour
- `navigation_dc` — getting lost risk
- `forage_dc` — finding food/water

---

### 7. DUNGEON
**Purpose:** Indoors/structured location with rooms, time pressure, limited resources.

| Property | Value |
|----------|-------|
| `initiative` | `None` or `True` (if time pressure / reactive) |
| `surprise` | relevant — dungeon has ambush potential |
| `infinite` | `True` until dungeon cleared/exited |
| `sequence` | `[EXPLORE_ROOM, TRAP_CHECK, ENCOUNTER_CHECK, RESOURCE_CHECK]` |
| `broadcast_scope` | `ALL` |
| `allowed_actions` | Move, Search, Listen, Disable Device, Stealth, Interact, Rest |
| `exit_triggers` | Objective complete → ACTIVE; short rest → DOWNTIME-ish; long rest exits dungeon |

**Dungeon state properties:**
- `dungeon_floor` — current depth level
- `turns_elapsed` — time pressure (torch duration, monster schedules)
- `rooms_cleared` — progress tracking
- `active_room` — current room/area context
- `trap_density` — per area

**Merge candidate:** Dungeon can be seen as a *constrained variant of EXPLORATION* — the difference is time pressure and room structure vs open hex crawling. Consider merging with `exploration` as a `mode: "dungeon" | "overland"` flag.

---

### 8. TRAVEL
**Purpose:** Overland travel between locations, camping, long-distance movement.

| Property | Value |
|----------|-------|
| `initiative` | `None` |
| `surprise` | relevant — ambushes while traveling |
| `infinite` | `True` until destination reached |
| `sequence` | `[MARCH, CAMP, RANDOM_ENCOUNTER, TRAVEL_EVENT]` |
| `broadcast_scope` | `ALL` |
| `allowed_actions` | Travel pace, Forage, Stealth, Set watch, Craft, Rest |

**Merge candidate:** TRAVEL is essentially a specialized EXPLORATION state. Consider: `exploration` with `travel_mode: True` flag rather than separate state. The difference is that travel has camping, marching order, and long-duration mechanics.

---

### 9. DOWNTIME
**Purpose:** Between sessions or in-town activities — crafting, training, shopping.

| Property | Value |
|----------|-------|
| `initiative` | `None` |
| `surprise` | `None` |
| `infinite` | `False` — runs for N days/weeks then returns to ACTIVE |
| `sequence` | `[SELECT_ACTIVITY, RESOLVE, ADVANCE_TIME]` |
| `broadcast_scope` | `DM` + active player |
| `allowed_actions` | Crafting, Training, Carousing, Trading, Research, Healing, Spell Preparation |
| `exit_triggers` | Time expires → ACTIVE; adventure calls → ACTIVE |

**Downtime state properties:**
- `days_available` — how long before next adventure
- `activities` — each with duration and cost
- `gold_budget` — spending limits
- `available_services` — training, crafting, spell copying

---

### 10. REST
**Purpose:** Short rest (1 hour) or long rest (8 hours) — resource recovery.

| Property | Value |
|----------|-------|
| `initiative` | `None` |
| `surprise` | `None` |
| `infinite` | `False` — ends when rest complete or interrupted |
| `sequence` | `[REST, INTERRUPT_CHECK, RESOURCE_RECOVERY]` |
| `broadcast_scope` | `DM` + resting party |
| `allowed_actions` | Sleep, eat, heal (HD), prepare spells, short conversation |
| `exit_triggers` | Rest complete → prior state; interrupted → COMBAT |

**Merge candidate:** REST is really a *sub-state* of DOWNTIME or ACTIVE, not a top-level loop state. Recommend: `rest_type: "short" | "long"` as a property on DOWNTIME or ACTIVE, not its own state. Exception: if rest needs its own full UI/treatment (like in deadly serious campaigns with interrupt risk).

---

### 11. CUTSCENE
**Purpose:** DM narration — no player mechanical input, story beats.

| Property | Value |
|----------|-------|
| `initiative` | `None` |
| `surprise` | `None` |
| `infinite` | `False` — runs for duration of narration |
| `sequence` | `[NARRATE]` (single step) |
| `broadcast_scope` | `ALL` (read-only) |
| `allowed_actions` | None (DM narrates only) |
| `exit_triggers` | DM ends narration → prior state or next state |
| `notes` | Players watch. No rolls. Could auto-advance to next state when done. |

**Merge candidate:** Cutscenes are really just a DM *tool* for transitioning, not a true game loop state. Could be modeled as `ACTIVE` with a `cutscene: True` flag and player input suppressed.

---

### 12. MASS-COMBAT
**Purpose:** Army vs army — treat groups as units, different scale than PC combat.

| Property | Value |
|----------|-------|
| `initiative` | `True` — per unit/army side |
| `surprise` | relevant — ambushes apply |
| `infinite` | `True` — until one army breaks or DM ends |
| `sequence` | `[ROLL_INITIATIVE, ARMY_ROUND]` |
| `round_sequence` | Each army in initiative: `[MOVE_UNIT, ATTACK, SPECIAL]` |
| `broadcast_scope` | `DM` + army leaders |
| `allowed_actions` | Unit moves, ranged attacks, melee resolution, rout check |
| `exit_triggers` | Army morale breaks → victory/defeat; DM transitions to ACTIVE |

**Mass combat properties:**
- `army_hp` (morale) vs individual HP
- `unit_types` — infantry, cavalry, siege, spellcasters
- `terrain_effects` — choke points, high ground
- `leader_present` — advantage if leader alive

**Merge candidate:** MASS-COMBAT is sufficiently different from COMBAT (unit vs individual, morale vs HP, different actions) that it deserves its own state family, not merged. But it *shares* the initiative/turn structure with COMBAT.

---

## STATE CONSOLIDATION ANALYSIS

### Probable Merge Candidates

| Merge | Reason |
|-------|--------|
| `TRAVEL` → `EXPLORATION` | Travel is just overland exploration with camping. Use `mode: "travel"` flag. |
| `DUNGEON` → `EXPLORATION` | Dungeon is room-constrained exploration with time pressure. Use `mode: "dungeon"` flag. |
| `REST` → `DOWNTIME` | Rest is a downtime activity, not a full loop state. Use `rest_type` property. |
| `CUTSCENE` → `ACTIVE` | Narrative tool, not a real loop. Use `cutscene: True` flag with input suppressed. |

### States That Should Stay Separate

| Keep Separate | Reason |
|---------------|--------|
| `SESSION-ZERO` | Fundamentally different — no gameplay, pure setup |
| `ACTIVE` | Hub state, distinct purpose |
| `COMBAT` | Initiative + round + action economy is unique |
| `CHASE` | Contested movement mechanics not found elsewhere |
| `SOCIAL` | Influence track, no initiative, skill-driven |
| `DOWNTIME` | Time advancement, activity selection, resource spending |
| `MASS-COMBAT` | Army-level mechanics, morale not HP |

### States Requiring More Research

- **SIEGE** — siege equipment, defenders, breach mechanics (could be mode of MASS-COMBAT)
- **UNDERWATER** / **ENVIRONMENTAL** — special movement rules, breathing, pressure (could be environmental flags on any state)
- **HEIST** — pre-planning phase + execution phase (planning = ACTIVE/DOWNTIME, execution = COMBAT/EXPLORATION hybrid)

---

## UNIVERSAL PROPERTIES (all states)

These apply to every state regardless of type:

```
id: str                    # unique state instance id
state_type: str            # "session-zero" | "active" | "combat" | ...
phase: str                # current step within sequence
sequence: list[str]       # all steps in order
infinite: bool             # True = loop until exit; False = run once
round: int                 # current round number (0 before first round)
turn: int                  # current turn number within round (0-indexed)
active_participant: str    # character_id of who is currently acting
broadcast_scope: str       # "ALL" | "DM" | "ACTIVE" | "SUBSET"
allowed_actions: list[str] # computed from state + participant class
exit_condition: str        # what triggers state transition
parent_state: str | None   # state we came from (for returns)
created_at: str
```

---

## SHARED PROPERTIES (multiple states, not all)

### Initiative group (COMBAT, CHASE, MASS-COMBAT):
```
initiative_order: list[str]       # sorted participant IDs
initiative_roll: dict[str, int]    # participant → roll
surprise: None | "party" | "npc"   # who got surprised
surprise_resolved: bool
```

### Turn group (COMBAT, CHASE, MASS-COMBAT):
```
current_actor: str                 # character_id
turn_timeout: int | None           # seconds, for async/real-time
actions_taken: set[str]            # what's been used this turn
bonus_action_used: bool
reaction_available: bool
movement_used: int                 # feet moved this turn
```

### Exploration group (EXPLORATION, DUNGEON, TRAVEL):
```
terrain_type: str
travel_speed: int
navigation_dc: int
random_encounter_chance: float
forage_dc: int
time_elapsed: int                  # in-game minutes/hours
```

### Social group (SOCIAL, MASS-COMBAT morale):
```
influence_track: int             # "social HP" equivalent
npc_disposition: str             # friendly/neutral/hostile
checks_accumulated: int          # number of checks made this encounter
success_threshold: int           # checks needed to succeed
```

---

## PROPOSED CONSOLIDATED STATE LIST (8 states)

After merges, target list:

1. **SESSION-ZERO** — pre-campaign setup
2. **ACTIVE** — free-form play hub + cutscene flag
3. **COMBAT** — individual initiative-based fighting
4. **CHASE** — contested speed/movement
5. **SOCIAL** — dialog/persuasion/influence encounters
6. **EXPLORATION** — overland/dungeon/travel (with mode flag)
7. **DOWNTIME** — between-session activities (rest as activity type)
8. **MASS-COMBAT** — army vs army, morale-based

---

## STATE TRANSITION MAP

```
SESSION-ZERO
  └── activate → ACTIVE

ACTIVE
  ├── hostile encountered → COMBAT
  ├── social encounter → SOCIAL
  ├── travel begins → EXPLORATION (mode: travel)
  ├── enter dungeon → EXPLORATION (mode: dungeon)
  ├── session ends → DOWNTIME
  └── DM narration → ACTIVE (cutscene: True)

EXPLORATION (mode: travel | dungeon | overland)
  ├── combat encounter → COMBAT
  ├── destination reached → ACTIVE
  ├── time expires → DOWNTIME
  └── hostile chase starts → CHASE

CHASE
  ├── catch target → COMBAT
  ├── escape → (DM chooses next state)
  └── target lost → ACTIVE

COMBAT
  ├── all hostiles dead → ACTIVE
  ├── DM calls retreat → CHASE or ACTIVE
  └── enemy escapes → ACTIVE or CHASE

SOCIAL
  ├── persuasion success → ACTIVE
  ├── deception exposed → COMBAT or ACTIVE
  ├── intimidation fails → COMBAT
  └── time/maneuvers exhausted → DM chooses

DOWNTIME
  ├── rest days consumed → ACTIVE
  └── adventure calls → ACTIVE

MASS-COMBAT
  ├── army morale breaks → victory/defeat → ACTIVE
  └── DM ends → ACTIVE
```

---

## GUI LAYOUT BY STATE (draft)

Each state defines a default tab layout:

| State | Default Tab | Other Available Tabs |
|-------|------------|----------------------|
| SESSION-ZERO | Character List | DM Notes |
| ACTIVE | Map / Scene | Character Sheet, Inventory, Journal |
| COMBAT | Initiative Tracker | Character Sheet, Map, Action Buttons |
| CHASE | Distance Tracker | Map, Character Sheet |
| SOCIAL | Dialog / NPC Portrait | Skills, Character Sheet |
| EXPLORATION | Map / Hex Grid | Travel Log, Random Encounter Table |
| DUNGEON | Room Map | Exploration Notes, Time Tracker |
| TRAVEL | Overland Map | Marching Order, Camp Activities |
| DOWNTIME | Activity Menu | Shop, Training, Crafting |
| MASS-COMBAT | Army View | Terrain, Tactical Map |
| CUTSCENE | Narrative Display | (no other tabs) |

**Custom tab:** Always available — DM can place any widget, button, dropdown, image, text box, map pin, shortcut. This is the catch-all for things not anticipated by default layouts.

---

## NEXT STEPS

1. **Validate state list** — are there states missing? (Heist, Siege, Underwater?)
2. **Define transition conditions precisely** — what exactly triggers each exit?
3. **Flesh out COMBAT round_sequence** — this is the most mechanically complex
4. **Flesh out EXPLORATION mode handling** — how does mode flag affect behavior?
5. **Decide REST handling** — separate state or activity in DOWNTIME?
6. **GUI tab system design** — how does the frontend consume state to render tabs?

---

## OPEN QUESTIONS

1. **Can any state be entered from multiple parent states?** Yes — COMBAT can come from ACTIVE, EXPLORATION, CHASE. Need `parent_state` tracking.
2. **Can a state be re-entered without full reset?** E.g., COMBAT ends, then later resumes — does initiative reset? Surprise reset? Round counter?
3. **Do player-held resources (spell slots, HD, etc.) persist across state transitions?** Yes, but state transitions may trigger short/long rest checks.
4. **How does initiative interact with surprise in CHASE vs COMBAT?** Both resolve before loop starts.
5. **What happens to `active_participant` during cutscene?** Set to `None`, no actions allowed.
