"""
Campaign setup — the pre-campaign container.
Created by DM before Session Zero. Becomes a Campaign after Session Zero completes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from dnd_core.models.campaign_constraints import CampaignConstraints
from dnd_core.models.campaign_skeleton import CampaignSkeleton


class CampaignTone(Enum):
    HEROIC    = auto()
    GRIMDARK  = auto()   # Think Witcher, Dark Souls
    SILVER_GRAY = auto()  # Morally complex, not grim, not heroically naive
    COMEDY    = auto()
    HORROR    = auto()
    SWORD_AND_SORCERY = auto()  # Conan, barbarians, pulp fantasy
    HIGH_FANTASY = auto()
    LOW_FANTASY = auto()
    CYBERPUNK_FANTASY = auto()  # Magitech, urban grit


class CampaignPacing(Enum):
    EPIC       = auto()   # Years-long campaign, world-changing events
    BALANCED   = auto()   # Standard adventure pacing
    SNAPPY     = auto()   # Tight, module-style, every session matters
    MINECRAFT  = auto()   # Sandbox, player-driven, no railroading


class SetupStatus(Enum):
    DRAFT      = auto()   # Still being edited
    ACTIVE     = auto()   # Session Zero in progress
    COMPLETED  = auto()   # Session Zero done, ready to play
    ABANDONED  = auto()


@dataclass
class CampaignSetup:
    """
    The pre-campaign container — created by the DM before Session Zero.
    After Session Zero completes, a Campaign is instantiated from this.
    """
    id: str
    dm_id: str

    # Identity
    title: str
    elevator_pitch: str = ""      # 1-2 sentence pitch

    # Tone & pacing
    tone: CampaignTone = CampaignTone.HIGH_FANTASY
    pacing: CampaignPacing = CampaignPacing.BALANCED

    # Constraints on what players can use
    constraints: CampaignConstraints = field(default_factory=CampaignConstraints)

    # World scaffolding (optional)
    skeleton: Optional[CampaignSkeleton] = None

    # Collaborative content built during Session Zero
    world_mood: str = ""
    group_covenants: list[str] = field(default_factory=list)    # "no PvP", "safety tools", etc.
    shared_history: str = ""      # Group backstory blurb agreed upon
    confirmed_player_ids: list[str] = field(default_factory=list)

    # Session Zero metadata
    session_zero_started_at: Optional[str] = None
    session_zero_completed_at: Optional[str] = None

    # Status
    status: SetupStatus = SetupStatus.DRAFT

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    def is_playable(self) -> bool:
        """True when Session Zero is done and campaign is ready to launch."""
        return self.status == SetupStatus.COMPLETED and bool(self.confirmed_player_ids)