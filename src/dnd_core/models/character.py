"""
Core domain models for D&D 5e entities.
All mutable state is kept here — no logic in the models themselves.
Logic lives in the engine/rules modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ─── Ability Scores & Derived Stats ──────────────────────────────────────────

class Ability(Enum):
    STR = "strength"
    DEX = "dexterity"
    CON = "constitution"
    INT = "intelligence"
    WIS = "wisdom"
    CHA = "charisma"


@dataclass(frozen=True)
class AbilityScores:
    """Six ability scores. Use ability_modifier() to get the bonus."""
    strength:     int = 10
    dexterity:    int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom:       int = 10
    charisma:     int = 10

    def modifier(self, ability: Ability) -> int:
        return (getattr(self, ability.value) - 10) // 2


@dataclass
class SkillBonus:
    """Override for a specific skill (e.g., Expertise, Jack of All Trades)."""
    skill: str          # e.g. "perception", "stealth"
    bonus: int          # flat bonus to add on top of ability modifier


# ─── Conditions & Status ─────────────────────────────────────────────────────

class Condition(Enum):
    BLINDED      = auto()
    CHARMED      = auto()
    DEAFENED     = auto()
    EXHAUSTION   = auto()   # track level separately
    FRIGHTENED   = auto()
    GRAPPLED     = auto()
    INCAPACITATED = auto()
    INVISIBLE    = auto()
    PARALYZED    = auto()
    PETRIFIED    = auto()
    POISONED     = auto()
    PRONE        = auto()
    RESTRAINED   = auto()
    STUNNED      = auto()
    UNCONSCIOUS  = auto()


class ExhaustionLevel(Enum):
    NONE     = 0
    LEVEL_1  = 1   # disad. ability checks
    LEVEL_2  = 2   # speed halved
    LEVEL_3  = 3   # disad. attack rolls & saves
    LEVEL_4  = 4   # max HP halved
    LEVEL_5  = 5   # speed 0
    LEVEL_6  = 6   # death


@dataclass
class ActiveCondition:
    condition: Condition
    source: str = ""                    # who/what applied it
    notes: str = ""                     # flavour description


# ─── Hit Points & Death Saves ──────────────────────────────────────────────────

@dataclass
class DeathSaves:
    successes: int = 0   # 3 = stabilized
    failures:  int = 0   # 3 = dead
    stable:    bool = False

    def roll_save(self, roll: int) -> None:
        """Process a death saving throw. Caller provides the raw d20 result."""
        if self.stable:
            return
        if roll >= 10:
            self.successes += 1
            if self.successes >= 3:
                self.stable = True
        else:
            self.failures += 1
            # Roll of 1 counts as 2 failures
            if roll == 1:
                self.failures += 1
            # Roll of 20 brings you to 1 HP
            if roll == 20:
                self.failures = 0
                self.successes = 0
                self.stable = False
        if self.failures >= 3:
            self.failures = 3  # cap, character is dead


# ─── Spellcasting ──────────────────────────────────────────────────────────────

@dataclass
class SpellSlots:
    """Simple spell-slot tracking per level (1-9)."""
    level_1: int = 0
    level_2: int = 0
    level_3: int = 0
    level_4: int = 0
    level_5: int = 0
    level_6: int = 0
    level_7: int = 0
    level_8: int = 0
    level_9: int = 0

    def slot_max(self, level: int) -> int:
        """Max slots per level for a full caster (override for half-caster, etc.)."""
        return getattr(self, f"level_{level}", 0)

    def available(self, level: int) -> int:
        return self.slot_max(level)

    def use(self, level: int) -> bool:
        """Consume a slot. Returns True if successful."""
        if getattr(self, f"level_{level}", 0) > 0:
            setattr(self, f"level_{level}", getattr(self, f"level_{level}") - 1)
            return True
        return False


# ─── Action Economy ────────────────────────────────────────────────────────────

@dataclass
class ActionEconomy:
    action:     bool = True
    bonus_action: bool = True
    movement:   int = 30        # feet
    reaction:   bool = True
    # Used for e.g. Flurry of Blows, Action Surge
    extra_actions: int = 0
    # Used for e.g. Patient Repost
    extra_reactions: int = 0


# ─── Core Entity ───────────────────────────────────────────────────────────────

@dataclass
class Entity:
    """
    Abstract base for anything with HP: player characters, monsters, summons.
    """
    id: str
    name: str

    # Stats
    hp:            int = 0
    hp_max:        int = 0
    ac:            int = 10      # flat AC (no armor worn)
    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    speed:         int = 30      # feet per round

    # Conditions & status
    conditions:    list[ActiveCondition] = field(default_factory=list)
    exhaustion:    int = 0       # 0-6; 6 = dead

    # Combat tracking
    death_saves:   DeathSaves = field(default_factory=DeathSaves)
    initiative_roll: Optional[int] = None   # set during combat init
    is_prone:      bool = False
    concentration: Optional[str] = None    # name of active concentration spell

    # Spellcasting
    spell_slots:   SpellSlots = field(default_factory=SpellSlots)

    # Action economy for this turn
    economy:       ActionEconomy = field(default_factory=ActionEconomy)

    # Metadata
    source: str = "unknown"      # "player", "monster", "npc"

    # ─── Convenience helpers ──────────────────────────────────────────────────

    def apply_condition(self, condition: Condition, source: str = "", notes: str = "") -> None:
        if not self.has_condition(condition):
            self.conditions.append(ActiveCondition(condition, source, notes))

    def remove_condition(self, condition: Condition) -> None:
        self.conditions = [c for c in self.conditions if c.condition != condition]

    def has_condition(self, condition: Condition) -> bool:
        return any(c.condition == condition for c in self.conditions)

    def current_speed(self) -> int:
        """Speed after exhaustion penalties."""
        if self.exhaustion >= 4:
            return 0
        if self.exhaustion >= 2:
            return self.speed // 2
        return self.speed

    def is_unconscious(self) -> bool:
        return self.hp <= 0 or self.has_condition(Condition.UNCONSCIOUS)

    def is_alive(self) -> bool:
        return self.hp > 0 and not self.is_unconscious()

    def modifier(self, ability: Ability) -> int:
        return self.ability_scores.modifier(ability)

    def attack_bonus(self, ability: Ability = Ability.STR) -> int:
        return self.modifier(ability)

    def damage_bonus(self, ability: Ability = Ability.STR) -> int:
        return self.modifier(ability)

    # ─── HP mutation (only through engine, not direct) ───────────────────────

    def heal(self, amount: int) -> int:
        old = self.hp
        self.hp = min(self.hp + amount, self.hp_max)
        return self.hp - old

    def apply_damage(self, amount: int) -> int:
        """
        Apply raw damage to HP. Returns actual damage dealt.
        Death saves are triggered by the caller if hp reaches 0.
        """
        self.hp = max(self.hp - amount, -self.hp_max)  # can go to negative
        return amount