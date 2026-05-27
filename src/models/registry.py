"""Campaign registry — pointer document produced by Session Zero.

Schema (paths are relative to the registry file location, or absolute):
{
  "campaign_id": "abc123",
  "campaign_path": "campaigns/abc123/campaign.json",
  "world_state_path": "campaigns/abc123/world_state.json",
  "characters": [
    { "name": "Grog", "path": "campaigns/abc123/characters/grog.json" }
  ],
  "created_at": "...",
  "session_zero_finalized_at": "..."
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CharacterPointer:
    """A single character — name + path to its saved state file."""
    name: str
    path: str


@dataclass
class CampaignRegistry:
    """Pointer document for a campaign whose Session Zero is complete."""
    campaign_id: str
    campaign_path: str          # relative or absolute path to campaign.json
    world_state_path: str       # relative or absolute path to world_state.json
    characters: list[CharacterPointer] = field(default_factory=list)

    created_at: str = ""
    session_zero_finalized_at: str = ""

    @classmethod
    def new(
        cls,
        campaign_id: str,
        campaign_path: str,
        world_state_path: str,
        characters: list[CharacterPointer] | None = None,
    ) -> "CampaignRegistry":
        now = datetime.utcnow().isoformat()
        return cls(
            campaign_id=campaign_id,
            campaign_path=campaign_path,
            world_state_path=world_state_path,
            characters=characters or [],
            created_at=now,
            session_zero_finalized_at=now,
        )

    def add_character(self, name: str, path: str) -> None:
        self.characters.append(CharacterPointer(name=name, path=path))

    def __post_init__(self) -> None:
        # Rehydrate CharacterPointer objects from plain dicts
        if self.characters:
            self.characters = [
                CharacterPointer(**cp) if isinstance(cp, dict) else cp
                for cp in self.characters
            ]