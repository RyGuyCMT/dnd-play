"""
NPCs, DM notes, and encounter templates.
All persistent game state outside of player character sheets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from dnd_core.models.character import AbilityScores


# ─── NPC / Monster ───────────────────────────────────────────────────────────────

class NPCRole(Enum):
    CIVILIAN   = auto()
    MERCHANT   = auto()
    GUARD      = auto()
    NOBLE      = auto()
    CLERGY     = auto()
    SAGE       = auto()
    CRIMINAL   = auto()
    ADVENTURER = auto()
    MONSTER    = auto()
    BOSS       = auto()


@dataclass
class NPC:
    """
    Any non-player character — shopkeeper, quest giver, enemy, etc.
    Shares the Entity base but adds DM-facing fields.
    """
    id: str
    name: str
    role: NPCRole = NPCRole.CIVILIAN

    # Public description (LLM can read and use)
    description: str = ""

    # DM-only (LLM hidden)
    dm_notes: str = ""
    secret_motivations: str = ""
    secrets: str = ""          # what the party hasn't discovered yet

    # Mechanical (for monster NPCs)
    hp_max: int = 0
    ac: int = 10

    # Disposition tracking
    disposition: str = "neutral"   # "friendly", "hostile", "neutral", etc.
    disposition_toward_party: str = "neutral"

    # Relationships
    location_id: Optional[str] = None
    faction_id: Optional[str] = None
    related_npc_ids: list[str] = field(default_factory=list)
    related_pc_ids: list[str] = field(default_factory=list)

    # Quest flags
    quest_id: Optional[str] = None
    has_met_party: bool = False

    # If it's a monster with a stat block
    stat_block: Optional[MonsterStatBlock] = None


@dataclass
class MonsterStatBlock:
    """Stat block for a monster NPC."""
    challenge_rating: str = "0"
    size: str = "Medium"
    type: str = "humanoid"
    alignment: str = "neutral"

    # Standard 5e stat block fields
    hp: int = 0
    ac: int = 10
    speed: str = "30 ft."

    # Ability scores (all monsters have them)
    strength:     int = 10
    dexterity:    int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom:       int = 10
    charisma:     int = 10

    # Combat stats
    hit_dice: str = ""    # e.g. "2d8"

    # Saves & skills
    saving_throws: str = ""
    skills: str = ""
    damage_resistances: str = ""
    damage_immunities: str = ""
    condition_immunities: str = ""
    senses: str = ""
    languages: str = ""

    # Abilities & actions (as raw text)
    abilities: str = ""   # Multiattack, Legendary Actions, etc.
    actions: str = ""
    legendary_actions: str = ""


# ─── DM Notes ──────────────────────────────────────────────────────────────────

@dataclass
class DMNotes:
    """
    The DM's private notes for the current session / campaign.
    The LLM can READ this but only modifies it via structured calls.
    """
    session_id: str

    # Agenda and plan
    tonight_plan: str = ""           # what you want to accomplish tonight
    improvisation_backup: str = ""   # "if things go sideways, do this"
    pacing_notes: str = ""          # "drag this out", "skip if rushed"

    # NPC state
    npc_current_moods: dict[str, str] = field(default_factory=dict)  # npc_id → mood

    # Table tracking
    player_attention: dict[str, str] = field(default_factory=dict)   # pc_id → "high", "low"
    table_vibe: str = "normal"       # "tense", "silly", "tired"

    # Secrets
    unused_secrets: list[str] = field(default_factory=list)
    foreshadowing: list[str] = field(default_factory=list)


# ─── Encounter Template ─────────────────────────────────────────────────────────

@dataclass
class EncounterTemplate:
    id: str
    name: str
    description: str = ""          # LLM reads this to set the scene

    # DM-only setup (LLM doesn't see until triggered)
    dm_setup: str = ""
    suggested_terrain: str = ""
    suggested_mood: str = ""

    # Mechanical
    enemies: list[dict] = field(default_factory=dict)  # [{name, count, cr}]

    # Post-encounter
    loot: list[str] = field(default_factory=list)
    consequences: list[str] = field(default_factory=list)


# ─── Quest ─────────────────────────────────────────────────────────────────────

class QuestStatus(Enum):
    AVAILABLE = auto()
    ACTIVE    = auto()
    COMPLETED = auto()
    FAILED    = auto()
    ABANDONED = auto()


@dataclass
class QuestObjective:
    id: str
    description: str
    completed: bool = False
    hidden: bool = False    # don't show player until revealed


@dataclass
class Quest:
    id: str
    name: str
    description: str = ""
    status: QuestStatus = QuestStatus.AVAILABLE

    giver_npc_id: Optional[str] = None
    location_id: Optional[str] = None

    objectives: list[QuestObjective] = field(default_factory=list)
    rewards: list[str] = field(default_factory=list)

    dm_notes: str = ""

    # Quest flags
    is_main_story: bool = False
    is_recurring: bool = False

    def mark_objective_done(self, objective_id: str) -> None:
        for obj in self.objectives:
            if obj.id == objective_id:
                obj.completed = True

    def is_complete(self) -> bool:
        return all(o.completed for o in self.objectives)