"""
Game session — a single play session within a campaign.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dnd_core.models.world import WorldState


@dataclass
class GameSession:
    id: str
    campaign_id: str
    session_number: int

    title: str = ""
    date: str = ""              # in-world date
    real_date: str = ""         # real-world date

    # DM notes (LLM can read but only updates via structured calls)
    dm_agenda: str = ""         # what the DM wants to accomplish
    dm_notes: str = ""          # session notes
    key_decisions: list[str] = field(default_factory=list)  # player choices that matter

    # Session state
    current_location_id: Optional[str] = None
    active_encounter_id: Optional[str] = None

    # World snapshot references
    world_snapshot: Optional[WorldState] = None  # world state at session start

    # Session status
    status: str = "active"      # "active", "paused", "completed"

    def add_decision(self, decision: str) -> None:
        self.key_decisions.append(decision)