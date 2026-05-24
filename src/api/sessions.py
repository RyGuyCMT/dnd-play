"""Session routes — start/end session, character connect/disconnect."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from config import settings

from api.deps import AuthContext, require_auth, require_dm
from models.message import Message, RecipientScope
from models.session import GameSession
from persistence.base import Repository, LocalStorageAdapter


router = APIRouter(prefix="/campaigns/{campaign_id}/sessions", tags=["sessions"])

_repo = None


def get_repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = Repository(LocalStorageAdapter(settings.data_path))
    return _repo


def set_repo(repo: Repository) -> None:
    global _repo
    _repo = repo


@router.post("/start")
def start_session(campaign_id: str, ctx: AuthContext = Depends(require_auth)):
    """Start a new session. Auto-increments session number. DM only."""
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.current_session is not None:
        raise HTTPException(status_code=409, detail="A session is already active")

    next_number = max([s.number for s in campaign.sessions.values()], default=0) + 1
    session = GameSession.start(campaign_id=campaign_id, number=next_number)
    campaign.current_session = session
    campaign.sessions[next_number] = session

    get_repo().save_campaign(campaign)

    msg = Message.send(
        campaign_id=campaign_id,
        sender_name="DM",
        recipient_names=[],
        content=f"Session {next_number} has begun.",
        scope=RecipientScope.BROADCAST,
        session_number=next_number,
        is_system=True,
    )
    get_repo().save_message(msg)

    return {"session_number": next_number, "started_at": session.started_at}


@router.post("/end")
def end_session(campaign_id: str, ctx: AuthContext = Depends(require_auth)):
    """End the current session. DM only."""
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.current_session is None:
        raise HTTPException(status_code=409, detail="No active session")

    session = campaign.current_session
    session.end()
    campaign.current_session = None

    get_repo().save_campaign(campaign)

    msg = Message.send(
        campaign_id=campaign_id,
        sender_name="DM",
        recipient_names=[],
        content=f"Session {session.number} has ended.",
        scope=RecipientScope.BROADCAST,
        session_number=session.number,
        is_system=True,
    )
    get_repo().save_message(msg)

    return {"session_number": session.number, "ended_at": session.ended_at}


@router.post("/characters/{character_name}/connect")
def connect_character(campaign_id: str, character_name: str,
                      ctx: AuthContext = Depends(require_auth)):
    """Mark a character as connected to the current session."""
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.current_session is None:
        raise HTTPException(status_code=409, detail="No active session")

    if character_name not in campaign.characters:
        raise HTTPException(status_code=404, detail="Character not registered")

    campaign.current_session.connect(character_name)
    get_repo().save_campaign(campaign)

    return {"character_name": character_name, "connected": True}


@router.post("/characters/{character_name}/disconnect")
def disconnect_character(campaign_id: str, character_name: str,
                        ctx: AuthContext = Depends(require_auth)):
    """Mark a character as disconnected from the current session. DM only."""
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.current_session is None:
        raise HTTPException(status_code=409, detail="No active session")

    campaign.current_session.disconnect(character_name)
    get_repo().save_campaign(campaign)

    return {"character_name": character_name, "connected": False}


@router.get("")
def get_session(campaign_id: str):
    """Get current session details."""
    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.current_session is None:
        return {"active": False}

    session = campaign.current_session
    return {
        "active": True,
        "number": session.number,
        "started_at": session.started_at,
        "connected_characters": list(session.connected_character_names),
    }