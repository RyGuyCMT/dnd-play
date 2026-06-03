"""
D&D 5e Game State Machine.

Covers the full session lifecycle, not just combat:

  idle → exploring → social → travel → dungeon_mode
                        ↓
                   [any can trigger combat_active]
                        ↓
                   combat_end → exploring / downtime

Downtime (between sessions) is a separate loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from dnd_core.models import Entity
from dnd_core.state_machine.events import CombatEvent


# ─── High-level game mode ───────────────────────────────────────────────────────

class GameMode(Enum):
    IDLE          = auto()   # between sessions, no active game
    EXPLORING     = auto()   # moving through world, descriptions, skill checks
    SOCIAL        = auto()   # NPC interaction, dialogue, persuasion
    TRAVEL        = auto()   # overland travel, random encounters, time passing
    DUNGEON       = auto()   # inside a dungeon / confined tactical space
    COMBAT        = auto()   # combat active (round loop running)
    DOWNTIME      = auto()   # between sessions, training/crafting/shopping
    LONG_REST     = auto()   # special rest sub-mode


# ─── Turn structure within non-combat modes ─────────────────────────────────────

class ExplorationPhase(Enum):
    # Exploring / Social / Travel
    DESCRIBE      = auto()   # LLM describes what the party sees
    AWAIT_INPUT   = auto()   # waiting for player action
    PROCESS_ACTION = auto() # engine resolves skill check, movement, etc.
    APPLY_RESULTS = auto()   # state changes, trigger events
    TICK_ENVIRONMENT = auto() # time passes, random events can trigger

    # Downtime
    DOWNTIME_START = auto()
    DOWNTIME_ACTIVITY = auto()
    DOWNTIME_END = auto()


@dataclass
class TurnContext:
    """
    What's currently happening in the session.
    Replaces the old CombatState.phase field when in non-combat modes.
    """
    mode: GameMode = GameMode.IDLE
    phase: ExplorationPhase = ExplorationPhase.DESCRIBE

    # Location / scene
    location_id: str = ""
    scene_description: str = ""   # LLM-enhanced description of current scene
    ambient_threats: list[str] = field(default_factory=list)  # "trap in room", "suspicious guard"

    # Time tracking
    exploration_time_minutes: int = 0
    travel_time_hours: int = 0
    short_rest_count: int = 0   # per long rest

    # Active quest (for LLM context)
    active_quest_id: str = ""

    # Social
    current_npc_id: str = ""
    conversation_topics: list[str] = field(default_factory=list)


# ─── Tickable effects ───────────────────────────────────────────────────────────

@dataclass
class TimedEffect:
    """
    An effect that ticks over real time or game time.
    E.g., "torch lit — burns out in 1 hour", "suspicious guard — gets reinforcements in 3 rounds"
    """
    id: str
    description: str           # for LLM narration
    ticks_on: str             # "time", "round", "entry", "exit"
    ticks_remaining: int = 1
    on_tick: str              # event to fire when it expires
    apply_immediately: bool = False


# ─── Session State ─────────────────────────────────────────────────────────────

@dataclass
class SessionState:
    """
    The full session state machine. Serializable for mid-session saves.
    """
    # Core
    campaign_id: str = ""
    session_id: str = ""

    # Mode & phase
    mode: GameMode = GameMode.IDLE
    turn_context: TurnContext = field(default_factory=TurnContext)

    # Initiative (only populated in COMBAT mode)
    initiative_order: list["InitiativeEntry"] = field(default_factory=list)
    current_actor_index: int = -1
    round_number: int = 0

    # Time
    game_date: str = ""         # in-world date
    real_start_time: str = ""   # ISO timestamp when session started

    # Tickable effects registry
    timed_effects: list[TimedEffect] = field(default_factory=list)

    # History (for LLM context — last N events)
    event_log: list["CombatEvent"] = field(default_factory=list)

    def current_actor(self) -> Optional[Entity]:
        if self.mode != GameMode.COMBAT:
            return None
        if 0 <= self.current_actor_index < len(self.initiative_order):
            return self.initiative_order[self.current_actor_index].entity
        return None


@dataclass
class InitiativeEntry:
    entity: Entity
    roll: int
    order: int = 0


# ─── State Machine ─────────────────────────────────────────────────────────────

class GameStateMachine:
    """
    Top-level game state. Handles transitions between exploration, social,
    travel, dungeon, combat, and downtime modes.

    All mechanical operations are delegated to the engine.
    All narrative generation is delegated to the LLM interface.
    This owns ONLY state transitions and event emission.
    """

    def __init__(self) -> None:
        self._state = SessionState()
        self._listeners: dict[str, list[Callable]] = {
            "mode_change": [],
            "phase_change": [],
            "turn_start": [],
            "turn_end": [],
            "round_end": [],
            "timed_effect_expired": [],
            "combat_end": [],
            "time_advanced": [],
        }

    # ── Read API ──────────────────────────────────────────────────────────────

    @property
    def state(self) -> SessionState:
        return self._state

    def mode(self) -> GameMode:
        return self._state.mode

    def is_combat(self) -> bool:
        return self._state.mode == GameMode.COMBAT

    def in_combat(self) -> bool:
        return self._state.mode == GameMode.COMBAT

    def current_actor(self) -> Optional[Entity]:
        return self._state.current_actor()

    def turn_context(self) -> TurnContext:
        return self._state.turn_context

    # ── Listener API ───────────────────────────────────────────────────────────

    def on(self, event: str, cb: Callable) -> None:
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(cb)

    def _emit(self, event: str, **kwargs) -> None:
        for cb in self._listeners.get(event, []):
            cb(**kwargs)

    # ── Mode transitions ───────────────────────────────────────────────────────

    def enter_mode(self, mode: GameMode, context: dict | None = None) -> list[CombatEvent]:
        """
        Transition into a new mode. Returns events for LLM narration.
        context: optional dict with mode-specific data (e.g., location_id for exploring)
        """
        old_mode = self._state.mode
        self._state.mode = mode

        events = []
        old_ctx = self._state.turn_context

        if mode == GameMode.EXPLORING:
            self._state.turn_context.mode = GameMode.EXPLORING
            self._state.turn_context.phase = ExplorationPhase.DESCRIBE
            if context:
                self._state.turn_context.location_id = context.get("location_id", "")

        elif mode == GameMode.COMBAT:
            # Combat is a sub-mode; phase managed separately
            self._state.turn_context.mode = GameMode.COMBAT
            self._state.turn_context.phase = ExplorationPhase.DESCRIBE
            events.append(CombatEvent(
                "mode_change",
                f"Entering {mode.name} mode",
                [],
                {"old_mode": old_mode.name, "new_mode": mode.name},
            ))

        elif mode == GameMode.DOWNTIME:
            self._state.turn_context.mode = GameMode.DOWNTIME
            self._state.turn_context.phase = ExplorationPhase.DOWNTIME_START

        events.append(CombatEvent(
            "mode_change",
            f"Mode changed from {old_mode.name} to {mode.name}",
            [],
            {"old_mode": old_mode.name, "new_mode": mode.name},
        ))

        self._emit("mode_change", old=old_mode, new=mode)
        return events

    # ── Exploration / Social / Dungeon ────────────────────────────────────────

    def describe_scene(self, description: str) -> None:
        """Store LLM-provided scene description in state."""
        self._state.turn_context.scene_description = description

    def set_location(self, location_id: str) -> None:
        self._state.turn_context.location_id = location_id

    def set_active_npc(self, npc_id: str) -> None:
        self._state.turn_context.current_npc_id = npc_id

    def tick_time(self, minutes: int) -> list[CombatEvent]:
        """Advance game time. Triggers timed effects."""
        events = []
        old_time = self._state.turn_context.exploration_time_minutes
        self._state.turn_context.exploration_time_minutes += minutes

        # Check timed effects
        self._state.turn_context.exploration_time_minutes += minutes
        self._check_timed_effects(events)
        self._emit("time_advanced", minutes=minutes, total=self._state.turn_context.exploration_time_minutes)
        return events

    def _check_timed_effects(self, events: list[CombatEvent]) -> None:
        expired = []
        for effect in self._state.timed_effects:
            if effect.ticks_on == "time":
                effect.ticks_remaining -= 1
                if effect.ticks_remaining <= 0:
                    expired.append(effect)

        for effect in expired:
            self._state.timed_effects.remove(effect)
            events.append(CombatEvent(
                "timed_effect_expired",
                effect.description,
                [],
                {"effect_id": effect.id, "on_tick": effect.on_tick},
            ))
            self._emit("timed_effect_expired", effect=effect)

    def add_timed_effect(self, effect: TimedEffect) -> None:
        self._state.timed_effects.append(effect)

    # ── Travel ────────────────────────────────────────────────────────────────

    def travel_to(self, destination_id: str, hours: int) -> list[CombatEvent]:
        """Advance time and transition to travel mode."""
        self._state.turn_context.travel_time_hours += hours
        self._state.turn_context.location_id = destination_id
        return self.enter_mode(GameMode.TRAVEL, {"destination_id": destination_id})

    # ── Combat (delegates to CombatStateMachine in practice) ─────────────────

    def start_combat(
        self,
        combatants: list[Entity],
        encounter_name: str = "",
    ) -> list[CombatEvent]:
        """Enter COMBAT mode with initiative order."""
        events = self.enter_mode(GameMode.COMBAT, {"encounter_name": encounter_name})

        # Roll initiative
        entries = []
        for entity in combatants:
            roll = self._roll_initiative(entity)
            entries.append(InitiativeEntry(entity=entity, roll=roll, order=0))

        entries.sort(key=lambda e: e.roll, reverse=True)
        for i, e in enumerate(entries):
            e.order = i

        self._state.initiative_order = entries
        self._state.current_actor_index = 0
        self._state.round_number = 0

        events.append(CombatEvent(
            "combat_started",
            f"Combat begins: {encounter_name}",
            [e.entity.name for e in entries],
        ))

        return events + self._start_combat_turn()

    def _roll_initiative(self, entity: Entity) -> int:
        import random
        return random.randint(1, 20) + entity.modifier(entity.ability_scores.modifier)

    def _start_combat_turn(self) -> list[CombatEvent]:
        if not self._state.initiative_order:
            return []
        self._state.current_actor_index = 0
        entity = self.initiative_order[0].entity
        entity.economy = ActionEconomy(
            action=True, bonus_action=True,
            movement=entity.current_speed(),
            reaction=True,
        )
        return [CombatEvent("turn_start", f"{entity.name}'s turn begins.", [entity.name])]

    def end_combat(self, reason: str = "") -> list[CombatEvent]:
        """Exit COMBAT mode, return to previous mode."""
        events = [CombatEvent("combat_end", reason or "Combat ended.", [])]
        self._emit("combat_end", reason=reason)

        # Reset combat state
        self._state.initiative_order = []
        self._state.current_actor_index = -1
        self._state.round_number = 0

        # Return to exploring mode
        return events + self.enter_mode(GameMode.EXPLORING)

    def next_turn(self) -> list[CombatEvent]:
        """Advance to the next combatant's turn."""
        if not self._state.initiative_order:
            return []

        next_idx = self._state.current_actor_index + 1

        if next_idx >= len(self._state.initiative_order):
            # Round complete
            events = [CombatEvent("round_end", f"Round {self._state.round_number} ends.", [])]
            self._state.round_number += 1
            next_idx = 0
            self._emit("round_end", round=self._state.round_number)
        else:
            events = []

        self._state.current_actor_index = next_idx
        entity = self._state.initiative_order[next_idx].entity
        entity.economy = ActionEconomy(
            action=True, bonus_action=True,
            movement=entity.current_speed(),
            reaction=True,
        )
        events.append(CombatEvent("turn_start", f"{entity.name}'s turn begins.", [entity.name]))
        self._emit("turn_start", entity=entity)
        return events

    # ── Downtime ───────────────────────────────────────────────────────────────

    def enter_downtime(self) -> list[CombatEvent]:
        """Between sessions: training, crafting, shopping."""
        return self.enter_mode(GameMode.DOWNTIME)

    def rest_short(self, party: list[Entity], hit_dice: list[int]) -> dict:
        """
        Short rest: party spends hit dice.
        Caller provides hit_dice per character.
        Returns summary dict for LLM narration.
        """
        self._state.turn_context.short_rest_count += 1
        return {"short_rests_today": self._state.turn_context.short_rest_count}

    def rest_long(self) -> list[CombatEvent]:
        """Long rest: full HP, half HP back on failed hit dice, exhaustion -1, spell slots."""
        self._state.turn_context.short_rest_count = 0
        self._state.turn_context.exploration_time_minutes = 0
        return self.enter_mode(GameMode.DOWNTIME)

    # ── Snapshots ─────────────────────────────────────────────────────────────

    def snapshot(self) -> SessionState:
        import copy
        return copy.deepcopy(self._state)

    def restore(self, state: SessionState) -> None:
        self._state = state


# Re-export for convenience
from dnd_core.models import ActionEconomy