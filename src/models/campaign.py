"""Campaign — the long-lived container for a D&D campaign."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from .session import GameSession


class CampaignPhase(Enum):
    SETUP  = "setup"
    REVIEW = "review"
    ACTIVE = "active"


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

    # Session Zero state — character review status
    # Only used during SETUP/REVIEW phase; empty dict means all approved
    pending_characters: dict[str, str] = field(default_factory=dict)

    # Game sessions
    current_session: Optional[GameSession] = None
    sessions: dict[int, GameSession] = field(default_factory=dict)   # number → session

    # Status
    status: CampaignStatus = CampaignStatus.DRAFT

    # Session Zero phase
    phase: CampaignPhase = CampaignPhase.SETUP

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        # Rehydrate enums from string representations (stored as .name, loaded by name or value)
        from models.campaign import CampaignPhase, CampaignStatus

        if isinstance(self.status, str):
            self.status = CampaignStatus[self.status]

        # Rehydrate phase from string (PydanticEncoder stores .name, e.g. "SETUP")
        if isinstance(self.phase, str):
            try:
                self.phase = CampaignPhase[self.phase]  # lookup by name first
            except KeyError:
                self.phase = CampaignPhase(self.phase)  # fallback to value lookup
        elif not isinstance(self.phase, CampaignPhase):
            self.phase = CampaignPhase(self.phase.value if hasattr(self.phase, 'value') else str(self.phase))
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
            # game_loop inside each GameSession may still be a dict (asdict flattens it)
            # — rehydrate it after the GameSession itself is reconstructed.
            # Also handles the case where sessions dict was NOT rehydrated
            # (already GameSession objects) but have stale dict game_loop.
            from models.game_loop import GameLoop
            for session in self.sessions.values():
                if isinstance(session.game_loop, dict):
                    session.game_loop = GameLoop.from_dict(session.game_loop)
        # Rehydrate game_loop for current_session — either rehydrated above
        # or still a dict (e.g. if sessions dict was already objects and the
        # sessions rehydration block was skipped)
        if self.current_session is not None:
            from models.game_loop import GameLoop
            if isinstance(self.current_session, dict):
                from models.session import GameSession
                self.current_session = GameSession(**self.current_session)
            if isinstance(self.current_session.game_loop, dict):
                self.current_session.game_loop = GameLoop.from_dict(self.current_session.game_loop)
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
            phase=CampaignPhase.SETUP,
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