"""Message — in-game text messages between characters / DM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional
import uuid


class RecipientScope(Enum):
    SINGLE    = auto()   # 1 recipient
    PARTY     = auto()   # 2+ recipients (secret council, select players)
    BROADCAST = auto()   # all connected players in session


@dataclass
class Message:
    id: str
    campaign_id: str

    # Who sent it
    sender_name: str          # "DM" or a character name
    is_system: bool = False   # True for server-generated messages (session start, etc.)

    # Recipients
    recipient_names: list[str] = field(default_factory=list)
    scope: RecipientScope = RecipientScope.SINGLE

    content: str = ""
    sent_at: str = ""

    # Optional: which session number this was sent in
    session_number: Optional[int] = None

    @classmethod
    def send(cls, campaign_id: str, sender_name: str,
            recipient_names: list[str], content: str,
            scope: RecipientScope = RecipientScope.SINGLE,
            session_number: Optional[int] = None,
            is_system: bool = False) -> "Message":
        return cls(
            id=uuid.uuid4().hex[:12],
            campaign_id=campaign_id,
            sender_name=sender_name,
            is_system=is_system,
            recipient_names=recipient_names,
            scope=scope,
            content=content,
            sent_at=datetime.utcnow().isoformat(),
            session_number=session_number,
        )

    def __post_init__(self) -> None:
        # Handle enum loaded from JSON as string
        if isinstance(self.scope, str):
            self.scope = RecipientScope[self.scope]