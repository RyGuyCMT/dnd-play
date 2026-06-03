"""
Breadcrumb — a meaningful narrative beat in the campaign.
The Cliffs Notes of the story the group has written together.
NOT a raw event log — only what matters gets recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class BreadcrumbType(Enum):
    WORLD_EVENT       = auto()  # Major plot development
    QUEST_MILESTONE   = auto()  # Quest completed/failed
    LOCATION_REVEAL   = auto()  # Discovered a new area
    NPC_INTRO         = auto()  # Met a new significant NPC
    NPC_DEPARTURE     = auto()  # NPC left/died/disappeared
    COMBAT_MILESTONE  = auto()  # Major battle concluded
    DISCOVERY         = auto()  # Found something important
    DOWNTIME_SKIP     = auto()  # Travel montage, time skip
    SESSION_MARKER    = auto()  # Session boundary
    DM_NOTE           = auto()  # DM wants to remember something


class BreadcrumbSource(Enum):
    DM_MANUAL              = auto()  # DM typed it themselves
    LLM_AUTO               = auto()  # LLM generated, accepted silently
    LLM_SUGGESTED_ACCEPTED = auto() # LLM suggested, DM approved
    PLAYER_NARRATED        = auto()  # Player wrote it
    SYSTEM                 = auto()  # Automatic (combat ended, etc.)


class BreadcrumbSignificance(Enum):
    MAJOR  = auto()   # Campaign-altering, arc end, character death
    NOTABLE = auto()  # Significant moment, quest progress
    MINOR  = auto()   # Worth remembering but not critical


@dataclass
class Breadcrumb:
    """
    A single meaningful event in the campaign narrative.
    Created when the party EXPERIENCES something — not when the DM plans it.
    If a plot hook goes unexplored, it never becomes a breadcrumb.
    """
    id: str
    campaign_id: str

    breadcrumb_type: BreadcrumbType
    sequence: int                      # Global ordering within campaign

    # When / where it happened
    session_id: Optional[str] = None
    round_number: Optional[int] = None
    world_time: str = ""              # In-game date/time when known

    # What mechanically happened (always present, user-readable)
    trigger_summary: str = ""

    # The story version (what was actually written/approved)
    narrative: Optional[str] = None

    # Provenance
    source: BreadcrumbSource = BreadcrumbSource.SYSTEM
    authored_by: Optional[str] = None   # user_id who wrote narrative
    llm_prompt_used: Optional[str] = None

    # Arc / significance
    arc_tag: Optional[str] = None
    significance: BreadcrumbSignificance = BreadcrumbSignificance.NOTABLE

    # Visibility
    hide_from_players: bool = False    # True = DM-only breadcrumb

    # Timestamps
    created_at: str = ""

    # ─── Convenience ───────────────────────────────────────────────────────

    def set_narrative(self, narrative: str, source: BreadcrumbSource, author: str) -> None:
        """
        Write narrative to breadcrumb.
        Note: LLM_SUGGESTED_REJECTED is handled at the caller level —
        rejected suggestions should NEVER be stored.
        """
        self.narrative = narrative
        self.source = source
        self.authored_by = author

    def is_visible_to_players(self) -> bool:
        return not self.hide_from_players