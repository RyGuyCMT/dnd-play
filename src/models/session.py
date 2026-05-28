"""GameSession — an instance of play within a campaign."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from models.game_loop import GameLoop, GameStateType


@dataclass
class GameSession:
    campaign_id: str
    number: int                      # auto-increment per campaign

    connected_character_names: set[str] = field(default_factory=set)

    started_at: str = ""
    ended_at: Optional[str] = None
    arc_notes: str = ""

    # Active game loop for this session. Created fresh on session start.
    game_loop: Optional[GameLoop] = None

    def __post_init__(self) -> None:
        # Handle list->set conversion for fields restored from JSON (asdict converts set→list)
        if isinstance(self.connected_character_names, (list, set)):
            self.connected_character_names = set(self.connected_character_names)

        # Rehydrate game_loop dict back to GameLoop object (asdict produces nested dicts)
        if isinstance(self.game_loop, dict):
            self.game_loop = GameLoop.from_dict(self.game_loop)
        elif self.game_loop is None:
            # Defensive: if game_loop is None on a loaded session, create a default
            self.game_loop = GameLoop(id=f"{self.campaign_id}:{self.number}")
            self.game_loop.enter(GameStateType.EXPLORATION)

    @classmethod
    def start(cls, campaign_id: str, number: int) -> "GameSession":
        """Start a new session with a fresh GameLoop in EXPLORATION state."""
        session = cls(
            campaign_id=campaign_id,
            number=number,
            connected_character_names=set(),
            started_at=datetime.utcnow().isoformat(),
        )
        session.game_loop = GameLoop(id=f"{campaign_id}:{number}")
        session.game_loop.enter(GameStateType.EXPLORATION)
        return session

    def connect(self, character_name: str) -> None:
        self.connected_character_names.add(character_name)

    def disconnect(self, character_name: str) -> None:
        self.connected_character_names.discard(character_name)

    def end(self) -> None:
        self.ended_at = datetime.utcnow().isoformat()