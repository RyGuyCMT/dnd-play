"""Message routes — send and retrieve messages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from config import settings

from api.deps import AuthContext, require_auth, require_dm
from models.message import Message, RecipientScope
from config import settings
from persistence.base import Repository, LocalStorageAdapter


router = APIRouter(prefix="/campaigns/{campaign_id}/messages", tags=["messages"])

_repo = None


def get_repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = Repository(LocalStorageAdapter(settings.data_path))
    return _repo


def set_repo(repo: Repository) -> None:
    global _repo
    _repo = repo


def _message_to_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "sender": m.sender_name,
        "recipients": m.recipient_names,
        "scope": m.scope.name,
        "content": m.content,
        "sent_at": m.sent_at,
        "session_number": m.session_number,
        "is_system": m.is_system,
    }


@router.post("")
def send_message(campaign_id: str, request: dict, ctx: AuthContext = Depends(require_auth)):
    """
    Send a message.

    Scope SINGLE:    specify recipient_names = ["Grog"]
    Scope PARTY:     specify recipient_names = ["Grog", "Velora", "Theron"]
    Scope BROADCAST: omit recipient_names (sends to all connected session characters)

    Sender is determined by auth context — ctx.character_name or "DM".
    """
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    content = request.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")

    scope_name = request.get("scope", "SINGLE").upper()
    try:
        scope = RecipientScope[scope_name]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid scope: {scope_name}")

    recipient_names = request.get("recipient_names", [])
    session_number = campaign.current_session.number if campaign.current_session else None

    # Resolve broadcast: send to all connected characters
    if scope == RecipientScope.BROADCAST:
        recipient_names = campaign.get_connected_character_names()
        if not recipient_names:
            raise HTTPException(status_code=409, detail="No connected characters in session")

    # Validate recipients exist
    if scope != RecipientScope.BROADCAST:
        for name in recipient_names:
            if name not in campaign.characters:
                raise HTTPException(status_code=404, detail=f"Character '{name}' not registered")

    # Determine sender
    if ctx.is_dm and ctx.character_name is None:
        sender_name = "DM"
    else:
        sender_name = ctx.character_name or "DM"

    msg = Message.send(
        campaign_id=campaign_id,
        sender_name=sender_name,
        recipient_names=recipient_names,
        content=content,
        scope=scope,
        session_number=session_number,
    )
    get_repo().save_message(msg)

    return _message_to_dict(msg)


@router.get("")
def get_messages(campaign_id: str, ctx: AuthContext = Depends(require_auth)):
    """
    Get messages for the authenticated character.
    DM sees all messages. Players see only their sent/received messages.
    """
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if ctx.is_dm and ctx.character_name is None:
        # DM — return all messages
        messages = get_repo().load_messages(campaign_id)
    elif ctx.character_name:
        messages = get_repo().messages_for(campaign_id, ctx.character_name)
    else:
        messages = []

    return [_message_to_dict(m) for m in messages]


@router.get("/history")
def get_message_history(campaign_id: str, ctx: AuthContext = Depends(require_auth),
                        limit: int = 50, before: str = ""):
    """
    Paginated message history. DM only.
    before: ISO timestamp — fetch messages sent before this time.
    """
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    messages = get_repo().load_messages(campaign_id)
    if before:
        messages = [m for m in messages if m.sent_at < before]
    messages = messages[-limit:]

    return [_message_to_dict(m) for m in messages]