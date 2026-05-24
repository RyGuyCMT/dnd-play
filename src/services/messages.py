"""Message service — shared logic for REST and WebSocket handlers.

Both the REST /messages POST endpoint and the WebSocket handler call through
here so message saving + WebSocket broadcast happen in one place.
"""

from __future__ import annotations

from fastapi import HTTPException

from models.message import Message, RecipientScope
from persistence.base import Repository


def send_message(
    repo: Repository,
    campaign_id: str,
    sender_name: str,
    scope: RecipientScope,
    recipient_names: list[str],
    content: str,
) -> Message:
    """Save a message and return it. Callers handle WebSocket broadcast."""
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if scope == RecipientScope.BROADCAST:
        recipient_names = campaign.get_connected_character_names()
        if not recipient_names:
            raise HTTPException(status_code=409, detail="No connected characters in session")

    # Validate recipients exist
    if scope != RecipientScope.BROADCAST:
        for name in recipient_names:
            if name not in campaign.characters:
                raise HTTPException(status_code=404, detail=f"Character '{name}' not registered")

    session_number = campaign.current_session.number if campaign.current_session else None

    msg = Message.send(
        campaign_id=campaign_id,
        sender_name=sender_name,
        recipient_names=recipient_names,
        content=content,
        scope=scope,
        session_number=session_number,
    )
    repo.save_message(msg)
    return msg