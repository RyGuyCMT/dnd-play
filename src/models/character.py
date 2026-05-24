"""Character — player character definition, registered in a campaign."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Character:
    name: str                       # unique within campaign (used as ID)
    player_id: str                   # player who owns this character
    character_class: str = ""
    race: str = ""
    backstory: str = ""
    notes: str = ""

    created_at: str = ""

    # Token hash for WebSocket/REST authentication
    character_token: str = ""

    @classmethod
    def create(cls, name: str, player_id: str,
               character_class: str = "", race: str = "",
               backstory: str = "",
               character_token: str = "") -> "Character":
        return cls(
            name=name,
            player_id=player_id,
            character_class=character_class,
            race=race,
            backstory=backstory,
            character_token=character_token,
            created_at=datetime.utcnow().isoformat(),
        )