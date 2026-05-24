"""GameSession — an instance of play within a campaign."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class GameSession:
    campaign_id: str
    number: int                      # auto-increment per campaign

    connected_character_names: set[str] = field(default_factory=set)

    started_at: str = ""
    ended_at: Optional[str] = None
    arc_notes: str = ""

    @classmethod
    def start(cls, campaign_id: str, number: int) -> "GameSession":
        return cls(
            campaign_id=campaign_id,
            number=number,
            connected_character_names=set(),
            started_at=datetime.utcnow().isoformat(),
        )

    def connect(self, character_name: str) -> None:
        self.connected_character_names.add(character_name)

    def disconnect(self, character_name: str) -> None:
        self.connected_character_names.discard(character_name)

    def end(self) -> None:
        self.ended_at = datetime.utcnow().isoformat()