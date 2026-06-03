"""
CharacterSheet — player-facing character data.
Extends the core Entity model with D&D 5e class/race/background/skill data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from dnd_core.models.character import (
    Ability,
    AbilityScores,
    ActionEconomy,
    ActiveCondition,
    Condition,
    DeathSaves,
    Entity,
    SpellSlots,
)


@dataclass
class Proficiencies:
    """Armor, weapon, and tool proficiencies."""
    armor: list[str] = field(default_factory=list)   # "light", "medium", "heavy", "shields"
    weapons: list[str] = field(default_factory=list) # "simple", "martial", specific names
    tools: list[str] = field(default_factory=list)    # "thieves' tools", "herbalism kit", etc.
    languages: list[str] = field(default_factory=list)


@dataclass
class SkillProficiency:
    """A skill with its associated ability and proficiency level."""
    name: str            # "perception", "stealth", etc.
    ability: Ability
    proficient: bool = False
    expertise: bool = False    # doubled bonus (Rogue, Bard)
    half_proficient: bool = False  # Jack of All Trades: +half PB


# ─── Spellcasting ─────────────────────────────────────────────────────────────

@dataclass
class KnownSpells:
    """Spells the character knows/has prepared."""
    prepared: list[str] = field(default_factory=list)   # spell names prepared today
    known: list[str] = field(default_factory=list)       # spells in repertoire (full list)
    cantrips: list[str] = field(default_factory=list)    # always available


@dataclass
class PactMagic:
    """Pact Magic feature (Warlock)."""
    slots: int = 0     # number of pact slots
    level: int = 1     # level of pact slots
    recovered_short_rest: bool = False


# ─── Character Sheet ────────────────────────────────────────────────────────────

@dataclass
class CharacterSheet(Entity):
    """
    Full player character sheet.
    Extends Entity (HP, AC, conditions, abilities) with D&D-specific fields.
    """
    # D&D identity
    class_name: str = "Fighter"
    subclass: str = ""
    race: str = "Human"
    background: str = "Soldier"
    alignment: str = "Neutral"

    # Level & XP
    level: int = 1
    xp: int = 0
    xp_to_next_level: int = 300

    # Proficiency bonus (derived: 2 at level 1, +1 every 4 levels)
    _proficiency_bonus: int = 2

    # Core stats
    proficiencies: Proficiencies = field(default_factory=Proficiencies)
    skill_proficiencies: list[SkillProficiency] = field(default_factory=list)

    # Spellcasting
    spellcasting_ability: Optional[Ability] = None   # INT/WIS/CHA
    spell_attack_bonus: int = 0
    spell_save_dc: int = 0
    known_spells: KnownSpells = field(default_factory=KnownSpells)
    pact_magic: Optional[PactMagic] = None

    # Resources that reset on short rest
    hit_dice_remaining: list[int] = field(default_factory=list)  # e.g. [10, 10] for two d10s
    channel_divinity: int = 0
    bardic_inspiration: int = 0
    rage_charges: int = 0
    lay_on_hands: int = 0

    # Resources that reset on long rest
    sorcery_points: int = 0
    inspiration: int = 0       # bardic inspiration die

    # Death saves
    death_saves: DeathSaves = field(default_factory=DeathSaves)

    # Equipment & inventory (names/ids only; details in world state)
    equipment: list[str] = field(default_factory=list)   # item IDs
    magic_items: list[str] = field(default_factory=list)
    gold: int = 0

    # Backstory
    backstory: str = ""
    personality_traits: list[str] = field(default_factory=list)
    ideals: list[str] = field(default_factory=list)
    bonds: list[str] = field(default_factory=list)
    flaws: list[str] = field(default_factory=list)

    # Features & traits (named blocks of text)
    features: list[str] = field(default_factory=list)   # feature names / IDs

    # ── Derived helpers ────────────────────────────────────────────────────

    def proficiency_bonus(self) -> int:
        return 2 + (self.level - 1) // 4

    def passive_perception(self) -> int:
        """10 + perception modifier (includes expertise)."""
        skill = next((s for s in self.skill_proficiencies if s.name == "perception"), None)
        bonus = self.modifier(Ability.WIS)
        if skill and skill.expertise:
            bonus += self.proficiency_bonus() * 2
        elif skill and (skill.proficient or skill.half_proficient):
            bonus += self.proficiency_bonus()
        return 10 + bonus

    def skill_modifier(self, skill_name: str) -> int:
        """Effective bonus for a skill check."""
        skill = next((s for s in self.skill_proficiencies if s.name == skill_name), None)
        if skill is None:
            return self.modifier(Ability.WIS)  # default to WIS for unknown skills
        base = self.modifier(skill.ability)
        if skill.expertise:
            return base + self.proficiency_bonus() * 2
        elif skill.proficient:
            return base + self.proficiency_bonus()
        elif skill.half_proficient:
            return base + self.proficiency_bonus() // 2
        return base

    def save_modifier(self, ability: Ability) -> int:
        """Saving throw modifier."""
        # Proficiency in saves is a separate flag
        proficient_saves = []  # TODO: add to CharacterSheet
        base = self.modifier(ability)
        if ability.value in [s.value for s in proficient_saves]:
            base += self.proficiency_bonus()
        return base

    def can_cast_spell(self, spell_name: str, level: int) -> bool:
        """Check if character has the spell prepared/known and has a slot."""
        if level > 0:
            if not self.spell_slots.available(level) > 0:
                return False
        return (
            spell_name in self.known_spells.prepared
            or spell_name in self.known_spells.cantrips
            or spell_name in self.known_spells.known
        )

    def level_up(self) -> dict:
        """Handle level up. Returns info about what changed."""
        self.level += 1
        self._proficiency_bonus = 2 + (self.level - 1) // 4
        # HP increase: roll or fixed (PHB suggests fixed for ease)
        hp_increase = 0  # TODO: class-specific hit die average or roll
        self.hp_max += hp_increase
        self.hp += hp_increase
        return {"level": self.level, "hp_gained": hp_increase}