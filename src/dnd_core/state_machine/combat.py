"""
D&D 5e Combat State Machine.

Owns the rigid mechanical loop:
  idle → combat_start → combat_active (round loop) → combat_end

Round loop:
  round_start → (per combatant, in initiative order) turn_start → turn_active → turn_end → round_end → (next round)

All state mutation goes through here. The LLM never touches this directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from dnd_core.models import Entity
from dnd_core.state_machine.events import CombatEvent


# ─── Phase enums ────────────────────────────────────────────────────────────────

class CombatPhase(Enum):
    IDLE          = auto()   # no combat running
    COMBAT_START  = auto()   # rolling initiative, building order
    ROUND_START   = auto()   # beginning of round (free actions, effects that trigger)
    TURN_START    = auto()   # a combatant's turn begins
    TURN_ACTIVE   = auto()   # they have actions available
    TURN_END      = auto()   # cleanup: remove expired conditions, check concentration
    ROUND_END     = auto()   # round-level effects tick
    COMBAT_END    = auto()   # encounter resolved, drop all combat state


# ─── Combat state snapshot ──────────────────────────────────────────────────────

@dataclass
class InitiativeEntry:
    """One entry in the initiative order list."""
    entity: Entity
    roll: int           # raw d20 + modifier
    order: int          # tie-break position after rolling


@dataclass
class CombatState:
    """
    The complete combat state. Serializable for save/restore mid-session.
    """
    phase:  CombatPhase = CombatPhase.IDLE

    # Initiative order
    order: list[InitiativeEntry] = field(default_factory=list)
    current_index: int = -1      # index into `order`
    round_number: int = 0

    # Turn-level state
    current_entity: Optional[Entity] = None

    # Events pending resolution
    pending_damage: list[PendingDamage] = field(default_factory=list)
    pending_save:   list[PendingSave]   = field(default_factory=list)

    # Combat metadata
    encounter_name: str = ""
    started_at: Optional[str] = None   # ISO timestamp


# ─── Pending action queue ──────────────────────────────────────────────────────

@dataclass
class PendingDamage:
    target: Entity
    amount: int
    damage_type: str          # "slashing", "fire", etc.
    source: str              # "Longsword +1", "Fireball (8d6)", etc.
    save_target: Optional[Entity] = None  # if requires a saving throw first
    save_dc: Optional[int] = None
    save_ability: Optional[str] = None


@dataclass
class PendingSave:
    target: Entity
    dc: int
    ability: str             # "dex", "con", etc.
    on_fail: str            # effect to apply on failure
    on_success: str         # effect to apply on success
    damage: Optional[int] = None


# ─── State Machine ─────────────────────────────────────────────────────────────

class CombatStateMachine:
    """
    Immutable-process combat state.

    Each transition: read current state, return new state + list of
    mechanical events that occurred (for audit trail + LLM prompt injection).

    Event callbacks can be registered to trigger side-effects (play sound,
    send webhook, etc.) at specific points.
    """

    def __init__(self) -> None:
        self._state = CombatState()
        self._listeners: dict[str, list[Callable]] = {
            "phase_change": [],
            "damage_dealt": [],
            "turn_start":   [],
            "turn_end":     [],
            "round_end":    [],
            "combat_end":   [],
        }

    # ── Public read API ────────────────────────────────────────────────────────

    @property
    def state(self) -> CombatState:
        return self._state

    def in_combat(self) -> bool:
        return self._state.phase not in (CombatPhase.IDLE, CombatPhase.COMBAT_END)

    def current_actor(self) -> Optional[Entity]:
        return self._state.current_entity

    def initiative_order(self) -> list[Entity]:
        return [e.entity for e in self._state.order]

    def is_actor_turn(self, entity: Entity) -> bool:
        return self._state.current_entity is entity

    # ── Listener API ───────────────────────────────────────────────────────────

    def on(self, event: str, cb: Callable) -> None:
        """Register a callback for a named event."""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(cb)

    def _emit(self, event: str, **kwargs) -> None:
        for cb in self._listeners.get(event, []):
            cb(**kwargs)

    # ── Phase transitions ─────────────────────────────────────────────────────

    def start_combat(
        self,
        combatants: list[Entity],
        encounter_name: str = "",
    ) -> list[CombatEvent]:
        """
        Begin combat: roll initiative for all combatants, sort order.
        Returns a list of CombatEvents for the LLM to narrate.
        """
        if self.in_combat():
            return [CombatEvent("combat_already_running", "", [])]

        events: list[CombatEvent] = []
        self._state.phase = CombatPhase.COMBAT_START
        self._state.encounter_name = encounter_name
        self._state.round_number = 0

        # Roll initiative for each combatant
        entries: list[InitiativeEntry] = []
        for entity in combatants:
            roll = self._roll_initiative(entity)
            entries.append(InitiativeEntry(entity=entity, roll=roll, order=0))

        # Sort: primary = roll desc, secondary = order of tie (already appended order)
        entries.sort(key=lambda e: (e.roll, 0), reverse=True)
        for i, e in enumerate(entries):
            e.order = i

        self._state.order = entries
        self._state.current_index = -1

        events.append(CombatEvent(
            "combat_started",
            f"Combat begins! {encounter_name}",
            [e.entity.name for e in entries],
        ))
        self._emit("phase_change", phase=CombatPhase.COMBAT_START)

        return events + self._advance_to_next_turn()

    def end_combat(self, reason: str = "") -> list[CombatEvent]:
        """End combat, reset all combat state."""
        events = [CombatEvent("combat_ended", reason, [])]
        self._state.phase = CombatPhase.COMBAT_END
        self._emit("phase_end", reason=reason)
        self._reset_combat_state()
        return events

    # ── Turn loop ────────────────────────────────────────────────────────────

    def begin_turn(self) -> list[CombatEvent]:
        """
        Called when a new combatant's turn starts.
        Resets action economy, processes round-start effects.
        """
        if not self.in_combat():
            return []

        entity = self._state.current_entity
        if entity is None:
            return []

        events = []
        self._state.phase = CombatPhase.TURN_START

        # Reset action economy
        entity.economy = ActionEconomy(
            action=True,
            bonus_action=True,
            movement=entity.current_speed(),
            reaction=True,
        )

        events.append(CombatEvent("turn_start", f"{entity.name}'s turn begins.", []))
        self._emit("turn_start", entity=entity)

        self._state.phase = CombatPhase.TURN_ACTIVE
        return events

    def end_turn(self) -> list[CombatEvent]:
        """
        Called at the end of a combatant's turn.
        Process turn-end effects, concentration checks.
        """
        if not self.in_combat():
            return []

        entity = self._state.current_entity
        events = []
        self._state.phase = CombatPhase.TURN_END

        # Turn-end: remove conditions that expire at end of turn
        # (tracked separately in effects registry)

        # Concentration check if applicable
        if entity.concentration:
            pass  # handled by effects module

        events.append(CombatEvent("turn_end", f"{entity.name}'s turn ends.", []))
        self._emit("turn_end", entity=entity)

        return events + self._advance_to_next_turn()

    def _advance_to_next_turn(self) -> list[CombatEvent]:
        """
        Internal: move to the next combatant in initiative order.
        If round is complete, trigger round-end and start new round.
        """
        if not self._state.order:
            return []

        next_idx = self._state.current_index + 1

        if next_idx >= len(self._state.order):
            # End of round
            events = self._end_round()
            events += self._start_new_round()
            return events

        self._state.current_index = next_idx
        self._state.current_entity = self._state.order[next_idx].entity
        return self.begin_turn()

    def _start_new_round(self) -> list[CombatEvent]:
        self._state.round_number += 1
        self._state.current_index = 0
        self._state.current_entity = self._state.order[0].entity
        return [CombatEvent(
            "round_start",
            f"Round {self._state.round_number} begins.",
            [],
        )]

    def _end_round(self) -> list[CombatEvent]:
        events = [CombatEvent("round_end", f"Round {self._state.round_number} ends.", [])]
        self._emit("round_end", round=self._state.round_number)
        return events

    def _reset_combat_state(self) -> None:
        """Reset to idle state (but preserve entity HP, conditions, etc.)."""
        self._state = CombatState()
        self._emit("phase_change", phase=CombatPhase.IDLE)

    # ── Mechanical actions (called by engine) ─────────────────────────────────

    def roll_initiative(self, entity: Entity) -> int:
        return self._roll_initiative(entity)

    def _roll_initiative(self, entity: Entity) -> int:
        import random
        roll = random.randint(1, 20)
        modifier = entity.modifier(entity.ability_scores.modifier)
        # Default to DEX for initiative, unless they have a feature override
        return roll + entity.modifier(entity.ability_scores.modifier)

    # ── Serialization ─────────────────────────────────────────────────────────

    def snapshot(self) -> CombatState:
        """Return a deep-copy snapshot for save/load."""
        import copy
        return copy.deepcopy(self._state)

    def restore(self, state: CombatState) -> None:
        self._state = state


