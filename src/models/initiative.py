"""Initiative tracker for COMBAT and CHASE states.

Encapsulates all per-encounter initiative state:
  - Ordered participant list (sorted by roll, ties broken by dex)
  - Active participant pointer
  - Per-participant: health, conditions, dex modifier, active status

Used by Campaign when entering COMBAT or CHASE state.
GameLoop.initiative_order / active_participant are the *display* slice;
Initiative is the full model with health tracking, conditions, etc.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional


# Module-level counter for auto-generating participant IDs
_participant_counter = 0


def _next_id() -> str:
    global _participant_counter
    _participant_counter += 1
    return f"p{_participant_counter}"


@dataclass
class InitiativeParticipant:
    """One participant in the initiative order."""

    id: str
    name: str           # display name (character name or NPC label)
    card_id: str        # e.g. character_token or "npc_goblin_1"
    dex_mod: int = 0   # dex modifier for tiebreaker
    init_value: int = 0  # total initiative value (roll + dex + mods)

    # Health and combat status
    health: Optional[int] = None
    max_health: Optional[int] = None
    is_player_character: bool = False

    # D&D 5e conditions: Prone, Stunned, Grappled, etc.
    active_conditions: list[str] = field(default_factory=list)
    death_saving_throws: dict[str, int] = field(default_factory=dict)  # successes/failures

    # ── Computed ────────────────────────────────────────────────────────────

    def is_unconscious(self) -> bool:
        if self.health is None:
            return False
        return self.health <= 0

    def is_dead(self) -> bool:
        """Dead if health drops below negative max_health (-10 for a max_hp of 10)."""
        if self.health is None or self.max_health is None:
            return False
        return self.health <= -self.max_health

    def is_stable(self) -> bool:
        """Alive but unconscious with 0 HP and no negative HP."""
        if self.health is None:
            return False
        return 0 > self.health > -self.max_health if self.max_health else False

    @property
    def is_alive(self) -> bool:
        if self.health is None:
            return True
        return self.health > 0

    # ── Mutations ───────────────────────────────────────────────────────────

    def damage(self, amount: int) -> None:
        if self.health is None:
            return
        self.health = max(-999, self.health - amount)

    def heal(self, amount: int) -> None:
        if self.health is None:
            return
        self.health = min(self.max_health or 999, self.health + amount)

    def add_condition(self, condition: str) -> None:
        if condition not in self.active_conditions:
            self.active_conditions.append(condition)

    def remove_condition(self, condition: str) -> None:
        if condition in self.active_conditions:
            self.active_conditions.remove(condition)

    def die(self) -> None:
        self.health = -999

    def stabilize(self) -> None:
        if self.health is not None and self.health <= 0:
            self.health = 1

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "name":                self.name,
            "card_id":             self.card_id,
            "dex_mod":             self.dex_mod,
            "init_value":          self.init_value,
            "health":              self.health,
            "max_health":          self.max_health,
            "is_player_character": self.is_player_character,
            "active_conditions":   list(self.active_conditions),
            "death_saving_throws":  dict(self.death_saving_throws),
        }

    @classmethod
    def from_dict(cls, data: dict) -> InitiativeParticipant:
        return cls(**data)


@dataclass
class Initiative:
    """Full initiative tracker for a combat or chase encounter."""

    id: str = ""
    encounter_type: str = "combat"   # "combat" | "chase"
    participants: list[InitiativeParticipant] = field(default_factory=list)
    active_participant_idx: int = 0
    current_round: int = 1
    encounter_active: bool = False

    @property
    def active_participant(self) -> Optional[InitiativeParticipant]:
        if 0 <= self.active_participant_idx < len(self.participants):
            return self.participants[self.active_participant_idx]
        return None

    @property
    def count(self) -> int:
        return len(self.participants)

    def roll_for(self, name: str, card_id: str, dex_mod: int = 0) -> InitiativeParticipant:
        """Generate an initiative roll and add a participant. Returns the new participant."""
        roll = random.randint(1, 20)
        init_value = roll + dex_mod
        tiebreaker = dex_mod

        global _participant_counter
        _participant_counter += 1
        pid = f"p{_participant_counter}"

        p = InitiativeParticipant(
            id=pid,
            name=name,
            card_id=card_id,
            dex_mod=dex_mod,
            init_value=init_value,
        )

        # Insert in initiative order (highest first; ties broken by dex_mod)
        for i, existing in enumerate(self.participants):
            if init_value > existing.init_value:
                self.participants.insert(i, p)
                break
            elif init_value == existing.init_value and dex_mod > existing.dex_mod:
                self.participants.insert(i, p)
                break
        else:
            self.participants.append(p)

        return p

    def next_turn(self) -> Optional[InitiativeParticipant]:
        """Advance to the next participant. Wraps and increments round if needed."""
        if not self.participants:
            return None
        self.active_participant_idx = (self.active_participant_idx + 1) % len(self.participants)
        if self.active_participant_idx == 0:
            self.current_round += 1
        return self.active_participant

    def set_participant_dead(self, participant_id: str) -> None:
        for p in self.participants:
            if p.id == participant_id:
                p.die()
                break

    def set_participant_unconscious(self, participant_id: str) -> None:
        for p in self.participants:
            if p.id == participant_id:
                p.health = 0
                break

    def apply_condition(self, participant_id: str, condition: str) -> None:
        for p in self.participants:
            if p.id == participant_id:
                p.add_condition(condition)
                break

    def remove_condition(self, participant_id: str, condition: str) -> None:
        for p in self.participants:
            if p.id == participant_id:
                p.remove_condition(condition)
                break

    def to_dict(self) -> dict:
        return {
            "id":                   self.id,
            "encounter_type":       self.encounter_type,
            "participants":         [p.to_dict() for p in self.participants],
            "active_participant_idx": self.active_participant_idx,
            "current_round":        self.current_round,
            "encounter_active":     self.encounter_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Initiative:
        participants = [
            InitiativeParticipant.from_dict(p) for p in data.get("participants", [])
        ]
        return cls(
            id=data.get("id", ""),
            encounter_type=data.get("encounter_type", "combat"),
            participants=participants,
            active_participant_idx=data.get("active_participant_idx", 0),
            current_round=data.get("current_round", 1),
            encounter_active=data.get("encounter_active", False),
        )
