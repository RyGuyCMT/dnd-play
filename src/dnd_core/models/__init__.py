"""
dnd_core.models — entity domain models.
"""

from dnd_core.models.character import (
    Ability,
    AbilityScores,
    ActionEconomy,
    ActiveCondition,
    Condition,
    DeathSaves,
    Entity,
    ExhaustionLevel,
    SpellSlots,
    SkillBonus,
)
from dnd_core.models.character_sheet import (
    CharacterSheet,
    KnownSpells,
    PactMagic,
    Proficiencies,
    SkillProficiency,
)
from dnd_core.models.world import (
    Faction,
    Location,
    LocationConnection,
    LocationType,
    VisitStatus,
    WorldEvent,
    WorldState,
)
from dnd_core.models.npc import (
    DMNotes,
    EncounterTemplate,
    MonsterStatBlock,
    NPC,
    NPCRole,
    Quest,
    QuestObjective,
    QuestStatus,
)
from dnd_core.models.game_session import GameSession
from dnd_core.models.campaign_constraints import (
    CampaignConstraints,
    Sourcebook,
    VariantRule,
)
from dnd_core.models.campaign_skeleton import (
    CampaignSkeleton,
    PlotPoint,
)
from dnd_core.models.campaign_setup import (
    CampaignSetup,
    CampaignPacing,
    CampaignTone,
    SetupStatus,
)
from dnd_core.models.session_zero import (
    Participant,
    ParticipantResponse,
    PhaseStatus,
    PhaseType,
    SessionZero,
    SessionZeroPhase,
    SessionZeroStatus,
)
from dnd_core.models.content_settings import (
    BreadcrumbLogLevel,
    ContentSettings,
    GenerationMode,
)
from dnd_core.models.user_llm_config import (
    LLMConfig,
    LLMProvider,
    UserLLMSettings,
)
from dnd_core.models.breadcrumb import (
    Breadcrumb,
    BreadcrumbSignificance,
    BreadcrumbSource,
    BreadcrumbType,
)
from dnd_core.models.campaign import (
    Campaign,
    CampaignStatus,
)

__all__ = [
    # character
    "Ability",
    "AbilityScores",
    "ActionEconomy",
    "ActiveCondition",
    "Condition",
    "DeathSaves",
    "Entity",
    "ExhaustionLevel",
    "SpellSlots",
    "SkillBonus",
    # character sheet
    "CharacterSheet",
    "KnownSpells",
    "PactMagic",
    "Proficiencies",
    "SkillProficiency",
    # world
    "Faction",
    "Location",
    "LocationConnection",
    "LocationType",
    "VisitStatus",
    "WorldEvent",
    "WorldState",
    # npc
    "DMNotes",
    "EncounterTemplate",
    "MonsterStatBlock",
    "NPC",
    "NPCRole",
    "Quest",
    "QuestObjective",
    "QuestStatus",
    # game session
    "GameSession",
    # campaign setup
    "CampaignConstraints",
    "CampaignPacing",
    "CampaignSetup",
    "CampaignSkeleton",
    "CampaignTone",
    "PlotPoint",
    "SetupStatus",
    # session zero
    "Participant",
    "ParticipantResponse",
    "PhaseStatus",
    "PhaseType",
    "SessionZero",
    "SessionZeroPhase",
    "SessionZeroStatus",
    # content / LLM
    "BreadcrumbLogLevel",
    "ContentSettings",
    "GenerationMode",
    "LLMConfig",
    "LLMProvider",
    "UserLLMSettings",
    # breadcrumb
    "Breadcrumb",
    "BreadcrumbSignificance",
    "BreadcrumbSource",
    "BreadcrumbType",
    # campaign
    "Campaign",
    "CampaignStatus",
]