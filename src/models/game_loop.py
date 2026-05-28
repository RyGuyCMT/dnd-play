"""GameLoop — the core game state machine.

Models all D&D play states: SESSION-ZERO, EXPLORATION, COMBAT, CHASE, DOWNTIME.
Every in-game interaction flows through an active GameLoop instance.

Design principles:
- Changing state_type cascades ALL derived properties to state's defaults
- Individual properties can be OVERRIDDEN — overrides survive state changes
  (e.g., manually setting round=3 in COMBAT persists if you briefly go to DOWNTIME and back)
- Computed properties return override if set, else the state default
- Sub-modes (mode:) further specialize behavior within a state_type
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

# ─── Request body for game-loop transition ─────────────────────────────────────

@dataclass
class TransitionGameLoop:
    """Body model for POST /campaigns/{id}/sessions/{n}/game-loop."""

    state_type: Optional[str] = None
    mode: str = ""
    initiative_order: Optional[list[str]] = None
    surprise: Optional[str] = None


# ─── Top-level state types ──────────────────────────────────────────────────────

class GameStateType(Enum):
    SESSION_ZERO = auto()
    EXPLORATION  = auto()
    COMBAT       = auto()
    CHASE        = auto()
    DOWNTIME     = auto()


class ExplorationMode(Enum):
    OVERLAND = auto()
    DUNGEON  = auto()
    SOCIAL   = auto()


class CombatMode(Enum):
    INDIVIDUAL = auto()
    MASS       = auto()


class DowntimeMode(Enum):
    REST        = auto()
    ADVANCEMENT = auto()
    ADMIN       = auto()


# ─── Per-state default configurations ───────────────────────────────────────────

_STATE_DEFAULTS: dict[GameStateType, dict] = {
    GameStateType.SESSION_ZERO: {
        "sequence":       ["SETUP", "REVIEW", "ACTIVE"],
        "infinite":       False,
        "initiative":     None,
        "surprise":       None,
        "broadcast_scope":"DM",
    },
    GameStateType.EXPLORATION: {
        "sequence":       ["TRAVEL", "EVENT_CHECK", "DISCOVERY"],
        "infinite":       True,
        "initiative":     None,
        "surprise":       None,
        "broadcast_scope":"ALL",
    },
    GameStateType.COMBAT: {
        "sequence":       ["ROLL_INITIATIVE", "SURPRISE_CHECK", "ROUND"],
        "infinite":       True,
        "initiative":     True,
        "surprise":       None,        # None | "party" | "npc" — set at combat start
        "broadcast_scope":"ACTIVE",
    },
    GameStateType.CHASE: {
        "sequence":       ["ROLL_INITIATIVE", "CHASE_ROUND"],
        "infinite":       True,
        "initiative":     True,
        "surprise":       None,
        "broadcast_scope":"ACTIVE",
    },
    GameStateType.DOWNTIME: {
        "sequence":       ["SELECT_ACTIVITY", "RESOLVE", "ADVANCE_TIME"],
        "infinite":       False,
        "initiative":     None,
        "surprise":       None,
        "broadcast_scope":"DM",
    },
}


# ─── Shared action-tag definitions ──────────────────────────────────────────────

# Action tags used in COMBAT round_options UI.
# A character's available actions are filtered by these tags based on their
# class features, spells, and equipped items. Tags are additive — a spell
# might carry tags: ["spell", "standard_action", "attack_action", "saving_throw"].
ACTION_TAGS = {
    "move_action",
    "standard_action",
    "bonus_action",
    "reaction",
    "free_action",
    "object_interaction",
    "defensive_action",
    "full_round_action",
    "readied_action",
}

COMBAT_ACTION_TAGS = ACTION_TAGS  # alias for clarity


# ─── Main model ────────────────────────────────────────────────────────────────

@dataclass
class GameLoop:
    """
    Core game state machine. Single instance per active campaign.

    Changing state_type cascades all derived properties to the new state's
    defaults. Individual properties can be overridden — overrides survive
    state transitions (restored when returning to the same state).

    Orthogonal state (not stored here — held on WorldState or session):
      - location_type  (e.g. "thistledown-keep", "cavern-level-3", "neverwinter")
      - mood           (e.g. "tense", "euphoric", "foreboding")
      - weather        (e.g. "heavy-rain", "fog", "clear")
      - city / region  (for world-crawl tracking)

    These are orthogonal selectors filled in from the map/locale context,
    not game-loop drivers.
    """

    # ── Identity ────────────────────────────────────────────────────────────────
    id: str = ""

    # ── Core state ─────────────────────────────────────────────────────────────
    state_type: GameStateType = GameStateType.SESSION_ZERO

    # Sub-mode within state_type. Empty string means no sub-mode.
    # exploration_mode  — ExplorationMode value or ""
    # combat_mode      — CombatMode value or ""
    # downtime_mode    — DowntimeMode value or ""
    mode: str = ""

    # ── Turn/round tracking (all states) ───────────────────────────────────────
    _round: int = 0                    # stored via property for override support
    turn: int = 0                      # index within current round's sequence
    active_participant: str = ""     # character_id of who is currently acting

    # ── Initiative (shared by COMBAT + CHASE) ───────────────────────────────────
    initiative_order: list[str] = field(default_factory=list)   # sorted participant IDs
    initiative_rolls: dict[str, int] = field(default_factory=dict)  # id → roll

    # ── Surprise (shared by COMBAT + CHASE + EXPLORATION ambush) ───────────────
    # None = no surprise, "party" = party surprises NPCs, "npc" = NPCs surprise party
    surprise: Optional[str] = None
    surprise_resolved: bool = False

    # ── Action tracking (COMBAT + CHASE) ───────────────────────────────────────
    actions_taken: set[str] = field(default_factory=set)
    bonus_action_used: bool = False
    reaction_available: bool = True
    movement_used: int = 0           # feet moved this turn

    # ── Chase-specific ──────────────────────────────────────────────────────────
    distance_feet: int = 0          # distance between chaser and fleeing party
    exhaustion_count: dict[str, int] = field(default_factory=dict)  # participant → DC

    # ── Parent state (for return-after-transition) ─────────────────────────────
    parent_state_type: Optional[GameStateType] = None
    parent_mode: str = ""

    # ── Override registry ──────────────────────────────────────────────────────
    # Any computed property can be manually overridden.
    # _overrides keys match the property names below.
    _overrides: dict[str, object] = field(default_factory=dict)

    # ── Computed properties ─────────────────────────────────────────────────────

    @property
    def round(self) -> int:
        """Current round number. Override survives state transitions."""
        if "round" in self._overrides:
            return self._overrides["round"]
        return self._round

    @round.setter
    def round(self, value: int) -> None:
        """Setting round stores an override (survives state transitions)."""
        self._overrides["round"] = value

    @property
    def sequence(self) -> list[str]:
        if "sequence" in self._overrides:
            return self._overrides["sequence"]
        if self.state_type == GameStateType.COMBAT and self.combat_mode == "mass":
            return ["ROLL_INITIATIVE", "MORALE_CHECK", "ARMY_ROUND"]
        if self.state_type == GameStateType.EXPLORATION and self.mode == "dungeon":
            return ["EXPLORE_ROOM", "TRAP_CHECK", "ENCOUNTER_CHECK", "RESOURCE_CHECK"]
        return _STATE_DEFAULTS[self.state_type]["sequence"]

    @property
    def infinite(self) -> bool:
        if "infinite" in self._overrides:
            return self._overrides["infinite"]
        return _STATE_DEFAULTS[self.state_type]["infinite"]

    @property
    def initiative_required(self) -> Optional[bool]:
        if "initiative_required" in self._overrides:
            return self._overrides["initiative_required"]
        return _STATE_DEFAULTS[self.state_type]["initiative"]

    @property
    def broadcast_scope(self) -> str:
        if "broadcast_scope" in self._overrides:
            return self._overrides["broadcast_scope"]
        return _STATE_DEFAULTS[self.state_type]["broadcast_scope"]

    @property
    def allowed_actions(self) -> list[str]:
        """Actions available to the active participant this turn."""
        if self.state_type not in {GameStateType.COMBAT, GameStateType.CHASE}:
            return []
        # COMBAT individual: full action economy
        if self.state_type == GameStateType.COMBAT and self.combat_mode != "mass":
            return list(ACTION_TAGS)
        # COMBAT mass: simplified army actions
        if self.state_type == GameStateType.COMBAT:
            return ["advance", "hold", "retreat", "rally", "ranged", "melee", "special"]
        # CHASE: movement-focused
        if self.state_type == GameStateType.CHASE:
            return ["dash", "attack", "disengage", "improvise", "search"]
        return []

    # ── Sub-mode helpers ────────────────────────────────────────────────────────

    @property
    def exploration_mode(self) -> str:
        return self.mode if self.state_type == GameStateType.EXPLORATION else ""

    @property
    def combat_mode(self) -> str:
        return self.mode if self.state_type == GameStateType.COMBAT else ""

    @property
    def downtime_mode(self) -> str:
        return self.mode if self.state_type == GameStateType.DOWNTIME else ""

    # ── State transitions ──────────────────────────────────────────────────────

    def enter(self, new_state: GameStateType, mode: str = "") -> None:
        """
        Transition into a new state. Saves current state as parent for return.
        Cascades all derived properties to new state's defaults UNLESS they
        have been manually overridden (in which case they retain their override).
        """
        # Save parent so we can return
        self.parent_state_type = self.state_type
        self.parent_mode = self.mode

        # Apply new state
        self.state_type = new_state
        self.mode = mode

        # Reset turn/round for most states (combat/chase keep their round counter
        # unless transitioning from/to the same state)
        if new_state not in {GameStateType.COMBAT, GameStateType.CHASE}:
            # Only reset _round if user hasn't manually overridden it
            if "round" not in self._overrides:
                self._round = 0
            self.turn = 0

        # Reset per-turn tracking on entering a new round
        self._reset_turn_tracking()

    def return_to_parent(self) -> None:
        """Pop back to the previously saved parent state."""
        if self.parent_state_type is None:
            return
        self.state_type = self.parent_state_type
        self.mode = self.parent_mode
        self.parent_state_type = None
        self.parent_mode = ""
        self._reset_turn_tracking()

    def set_override(self, property_name: str, value: object) -> None:
        """
        Lock a computed property to a specific value.
        Override survives state transitions until cleared with clear_override().
        """
        self._overrides[property_name] = value

    def clear_override(self, property_name: str) -> None:
        """Remove a previously set override. Property reverts to state default."""
        self._overrides.pop(property_name, None)

    def clear_all_overrides(self) -> None:
        """Remove all overrides. All computed properties revert to state defaults."""
        self._overrides.clear()

    # ── Round/turn advancement ──────────────────────────────────────────────────

    def advance_turn(self) -> None:
        """Move to the next participant in initiative order."""
        if self.state_type in {GameStateType.COMBAT, GameStateType.CHASE}:
            if self.initiative_order:
                current_idx = 0
                if self.active_participant:
                    current_idx = self.initiative_order.index(self.active_participant)
                    current_idx = (current_idx + 1) % len(self.initiative_order)
                self.active_participant = self.initiative_order[current_idx]
        self.turn += 1
        self._reset_turn_tracking()

    def advance_round(self) -> None:
        """Increment round counter and reset turn tracking."""
        self._round += 1
        self.turn = 0
        self._reset_turn_tracking()

    def _reset_turn_tracking(self) -> None:
        """Reset per-turn action tracking. Called on enter and turn advance."""
        self.actions_taken = set()
        self.bonus_action_used = False
        self.reaction_available = True
        self.movement_used = 0

    # ── Serialisation helpers ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Minimal dict for persistence (overrides are NOT stored)."""
        return {
            "id":                  self.id,
            "state_type":          self.state_type.name,
            "mode":                self.mode,
            "round":               self._round,
            "turn":                self.turn,
            "active_participant":  self.active_participant,
            "initiative_order":    self.initiative_order,
            "initiative_rolls":    self.initiative_rolls,
            "surprise":            self.surprise,
            "surprise_resolved":   self.surprise_resolved,
            "distance_feet":       self.distance_feet,
            "parent_state_type":   self.parent_state_type.name if self.parent_state_type else None,
            "parent_mode":         self.parent_mode,
            "actions_taken":       list(self.actions_taken),  # set → list for JSON
        }

    @classmethod
    def from_dict(cls, data: dict) -> GameLoop:
        """Reconstruct from dict. Sets no overrides (fresh from storage)."""
        gl = cls()
        gl.id = data.get("id", "")
        gl.state_type = GameStateType[data.get("state_type", "SESSION_ZERO")]
        gl.mode = data.get("mode", "")
        gl._round = data.get("round", 0)
        gl.turn = data.get("turn", 0)
        gl.active_participant = data.get("active_participant", "")
        gl.initiative_order = data.get("initiative_order", [])
        gl.initiative_rolls = data.get("initiative_rolls", {})
        gl.surprise = data.get("surprise")
        gl.surprise_resolved = data.get("surprise_resolved", False)
        gl.distance_feet = data.get("distance_feet", 0)
        parent_st = data.get("parent_state_type")
        gl.parent_state_type = GameStateType[parent_st] if parent_st else None
        gl.parent_mode = data.get("parent_mode", "")
        gl.actions_taken = set(data.get("actions_taken", []))
        return gl
