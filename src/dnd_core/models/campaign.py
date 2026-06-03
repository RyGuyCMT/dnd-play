"""
Campaign — the live playable container.
One per active campaign. Owned by the DM. Players get a filtered view.

Instantiated from CampaignSetup + SessionZero output when the campaign launches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from dnd_core.models.breadcrumb import Breadcrumb
from dnd_core.models.campaign_setup import CampaignSetup
from dnd_core.models.content_settings import ContentSettings
from dnd_core.models.game_session import GameSession
from dnd_core.models.world import WorldState
from dnd_core.models.content_settings import ContentSettings


class CampaignStatus(Enum):
    DRAFT     = auto()   # Created but not yet playing
    ACTIVE    = auto()   # In progress
    HIATUS    = auto()   # Paused
    COMPLETED = auto()   # Reached natural conclusion
    ABANDONED = auto()   # Dropped


@dataclass
class Campaign:
    """
    The live playable campaign container.
    Created from CampaignSetup when Session Zero is complete.
    """
    id: str
    setup_id: str                    # Link back to source CampaignSetup
    dm_id: str

    # Identity (copied from CampaignSetup, canonical for this campaign)
    title: str
    elevator_pitch: str = ""
    tone: str = ""
    pacing: str = ""

    # Character registry — uuid → CharacterSheet
    # Populated as players join and their sheets are approved in SessionZero
    characters: dict[str, object] = field(default_factory=dict)

    # World
    world: WorldState = field(default_factory=WorldState)

    # NPCs active in this campaign
    npcs: dict[str, object] = field(default_factory=dict)

    # Game sessions
    current_session_id: Optional[str] = None
    sessions: dict[str, GameSession] = field(default_factory=dict)

    # The breadcrumb trail — Cliffs Notes of the story
    breadcrumb_trail: list[Breadcrumb] = field(default_factory=list)

    # Content generation settings
    content_settings: ContentSettings = field(default_factory=ContentSettings)

    # Status
    status: CampaignStatus = CampaignStatus.DRAFT

    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    last_played_at: Optional[str] = None

    # ─── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def from_setup(cls, setup: CampaignSetup, dm_id: str) -> "Campaign":
        """Instantiate a Campaign from a completed CampaignSetup."""
        now = datetime.utcnow().isoformat()
        return cls(
            id=setup.id,
            setup_id=setup.id,
            dm_id=dm_id,
            title=setup.title,
            elevator_pitch=setup.elevator_pitch,
            tone=setup.tone.name if hasattr(setup.tone, 'name') else str(setup.tone),
            pacing=setup.pacing.name if hasattr(setup.pacing, 'name') else str(setup.pacing),
            characters={},
            world=WorldState(world_id=setup.id, name=setup.title),
            npcs={},
            current_session_id=None,
            sessions={},
            breadcrumb_trail=[],
            content_settings=ContentSettings.default(),
            status=CampaignStatus.DRAFT,
            created_at=now,
            updated_at=now,
            last_played_at=None,
        )

    # ─── Breadcrumb helpers ────────────────────────────────────────────────

    def add_breadcrumb(self, breadcrumb: Breadcrumb) -> None:
        breadcrumb.sequence = len(self.breadcrumb_trail)
        breadcrumb.campaign_id = self.id
        self.breadcrumb_trail.append(breadcrumb)

    def get_visible_breadcrumbs(self, include_dm_notes: bool = False) -> list[Breadcrumb]:
        """Return breadcrumbs visible to a given perspective."""
        results = []
        for bc in self.breadcrumb_trail:
            if bc.hide_from_players and not include_dm_notes:
                continue
            results.append(bc)
        return results

    # ─── Session helpers ───────────────────────────────────────────────────

    def start_session(self, session: GameSession) -> None:
        self.sessions[session.id] = session
        self.current_session_id = session.id
        self.last_played_at = datetime.utcnow().isoformat()

    def end_current_session(self) -> None:
        self.current_session_id = None