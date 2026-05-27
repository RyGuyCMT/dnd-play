"""Campaign — the long-lived container for a D&D campaign."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from .session import GameSession


class CampaignStatus(Enum):
    DRAFT     = auto()
    ACTIVE    = auto()
    HIATUS    = auto()
    COMPLETED = auto()
    ABANDONED = auto()


@dataclass
class Campaign:
    id: str
    dm_token: str               # DM privileged token (generated on creation)
    title: str
    elevator_pitch: str = ""
    tone: str = ""
    pacing: str = ""

    # Character registry — name → Character
    # Characters are registered (invited) here; connected players live in session
    characters: dict[str, "Character"] = field(default_factory=dict)

    # Game sessions
    current_session: Optional[GameSession] = None
    sessions: dict[int, GameSession] = field(default_factory=dict)   # number → session

    # Status
    status: CampaignStatus = CampaignStatus.DRAFT

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        # Handle enum loaded from JSON as string
        if isinstance(self.status, str):
            from models.campaign import CampaignStatus
            self.status = CampaignStatus[self.status]
        # Rehydrate GameSession objects from plain dicts (asdict strips dataclass type)
        if isinstance(self.current_session, dict):
            from models.session import GameSession
            self.current_session = GameSession(**self.current_session)
        if self.sessions:
            from models.session import GameSession
            self.sessions = {
                num: (GameSession(**sess) if isinstance(sess, dict) else sess)
                for num, sess in self.sessions.items()
            }
        # Rehydrate Character objects from plain dicts (dataclass_to_dict flattens them)
        from models.character import Character
        for name, char_data in list(self.characters.items()):
            if isinstance(char_data, dict):
                self.characters[name] = Character(**char_data)

    def model_post_init(self, __context) -> None:
        # Called by Pydantic model_validate; delegate to __post_init__ logic
        self.__post_init__()

    @classmethod
    def new(cls, title: str, dm_token: str, elevator_pitch: str = "",
            tone: str = "", pacing: str = "") -> "Campaign":
        now = datetime.utcnow().isoformat()
        return cls(
            id=_generate_id(),
            dm_token=dm_token,
            title=title,
            elevator_pitch=elevator_pitch,
            tone=tone,
            pacing=pacing,
            characters={},
            current_session=None,
            sessions={},
            status=CampaignStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )

    def register_character(self, character: "Character") -> None:
        self.characters[character.name] = character
        self.updated_at = datetime.utcnow().isoformat()

    def get_connected_character_names(self) -> list[str]:
        """Names of characters currently connected to the live session."""
        if self.current_session is None:
            return []
        return list(self.current_session.connected_character_names)

    def connected_characters(self) -> dict[str, "Character"]:
        """Characters in the campaign who are connected to the live session."""
        names = self.get_connected_character_names()
        return {name: self.characters[name] for name in names if name in self.characters}


def _generate_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]