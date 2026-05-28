"""Session routes — start/end session, character connect/disconnect."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from config import settings

from api.deps import AuthContext, require_auth, require_dm
from models.message import Message, RecipientScope
from models.session import GameSession
from models.game_loop import GameStateType, TransitionGameLoop
from websocket import ws_manager
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


# ─── Game Loop ───────────────────────────────────────────────────────────────

def _load_session(campaign_id: str, session_number: int | str) -> tuple:
    """Load campaign and resolve the requested session. Raises HTTPException on failure."""
    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    # session_number may arrive as str from URL path — try both int and str keys
    sess_num = int(session_number)

    # Primary: look in sessions dict (key may be int or str after round-trip)
    session = campaign.sessions.get(sess_num) or campaign.sessions.get(str(sess_num))

    # Fallback: if current_session has the requested session number, use it.
    # This handles the case where sessions dict wasn't populated but current_session was.
    if session is None and campaign.current_session is not None:
        if campaign.current_session.number == sess_num:
            session = campaign.current_session

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Rehydrate stale game_loop dict (e.g. if sessions[n] was not updated after
    # current_session.game_loop was modified in a prior in-memory session)
    from models.game_loop import GameLoop
    if isinstance(session.game_loop, dict):
        session.game_loop = GameLoop.from_dict(session.game_loop)

    return campaign, session


@router.get("/{session_number}/game-loop")
def get_game_loop(
    campaign_id: str,
    session_number: int,
    ctx: AuthContext = Depends(require_auth),
):
    """Get the current GameLoop state for a session. DM or player."""
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign, session = _load_session(campaign_id, session_number)
    if session.game_loop is None:
        raise HTTPException(status_code=404, detail="No game loop in this session")

    gl = session.game_loop
    return {
        "state_type":        gl.state_type.name,
        "mode":              gl.mode,
        "round":             gl.round,
        "turn":              gl.turn,
        "active_participant": gl.active_participant,
        "sequence":          gl.sequence,
        "infinite":          gl.infinite,
        "initiative_required": gl.initiative_required,
        "surprise":          gl.surprise,
        "broadcast_scope":   gl.broadcast_scope,
        "allowed_actions":   gl.allowed_actions,
        "parent_state_type": gl.parent_state_type.name if gl.parent_state_type else None,
        "parent_mode":       gl.parent_mode,
    }


@router.post("/{session_number}/game-loop")
def transition_game_loop(
    campaign_id: str,
    session_number: int,
    body: TransitionGameLoop,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Transition the GameLoop to a new state (DM only).

    Send state_type alone to enter that state with optional mode.
    Send state_type=RETURN (or omit state_type) to return to parent state.
    Sending state_type=CLEAR returns to EXPLORATION with all defaults.
    """
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign, session = _load_session(campaign_id, session_number)
    if session.game_loop is None:
        raise HTTPException(status_code=404, detail="No game loop in this session")

    gl = session.game_loop
    state_type = body.state_type
    mode = body.mode or ""

    # Return to parent
    if state_type is None or state_type.upper() == "RETURN":
        gl.return_to_parent()

    # Clear and reset to EXPLORATION defaults
    elif state_type.upper() == "CLEAR":
        gl.clear_all_overrides()
        gl.enter(GameStateType.EXPLORATION)

    # Enter new state
    else:
        try:
            new_state = GameStateType[state_type.upper()]
        except KeyError:
            valid = [s.name for s in GameStateType]
            raise HTTPException(status_code=400, detail=f"Invalid state_type. Use: {valid}")

        gl.enter(new_state, mode)

        # Seed initiative if provided (via body)
        if body.initiative_order is not None:
            gl.initiative_order = body.initiative_order
            gl.active_participant = body.initiative_order[0] if body.initiative_order else ""

        # Set surprise flag if provided (via body)
        if body.surprise is not None:
            gl.surprise = body.surprise if body.surprise in ("party", "npc") else None

    get_repo().save_campaign(campaign)

    # ── Broadcast game-loop update via WebSocket (after response) ────────────
    _broadcast_game_loop(campaign_id, gl)

    return {
        "state_type":        gl.state_type.name,
        "mode":              gl.mode,
        "round":             gl.round,
        "turn":              gl.turn,
        "initiative_order":  gl.initiative_order,
        "surprise":          gl.surprise,
        "parent_state_type": gl.parent_state_type.name if gl.parent_state_type else None,
    }


def _broadcast_game_loop(campaign_id: str, gl: "GameLoop") -> None:
    """Fire-and-forget WS broadcast after the HTTP response is sent.

    Uses asyncio.run() in a background thread so there is no latency
    cost to the DM's request.  Each call gets its own event loop.
    """
    import asyncio
    from threading import Thread

    def _run():
        asyncio.run(_async_broadcast_game_loop(campaign_id, gl))

    t = Thread(target=_run, daemon=True)
    t.start()


async def _async_broadcast_game_loop(campaign_id: str, gl: "GameLoop") -> None:
    """Async inner — may be called after the loop is already past suspension."""
    try:
        await ws_manager.broadcast_game_loop_update(
            campaign_id=campaign_id,
            state_type=gl.state_type.name,
            mode=gl.mode,
            round_num=gl.round,
            turn=gl.turn,
            active_participant=gl.active_participant,
            initiative_order=gl.initiative_order,
            allowed_actions=gl.allowed_actions,
            broadcast_scope=gl.broadcast_scope,
        )
    except Exception:
        # Never let a broadcast failure affect the HTTP response
        pass


@router.post("/{session_number}/game-loop/advance-turn")
def advance_turn(
    campaign_id: str,
    session_number: int,
    ctx: AuthContext = Depends(require_auth),
):
    """Advance to the next participant in initiative order. DM only."""
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign, session = _load_session(campaign_id, session_number)
    if session.game_loop is None:
        raise HTTPException(status_code=404, detail="No game loop in this session")

    gl = session.game_loop
    gl.advance_turn()
    get_repo().save_campaign(campaign)
    _broadcast_game_loop(campaign_id, gl)

    return {
        "active_participant": gl.active_participant,
        "turn":               gl.turn,
        "round":              gl.round,
    }


@router.post("/{session_number}/game-loop/advance-round")
def advance_round(
    campaign_id: str,
    session_number: int,
    ctx: AuthContext = Depends(require_auth),
):
    """Advance to the next round. DM only."""
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign, session = _load_session(campaign_id, session_number)
    if session.game_loop is None:
        raise HTTPException(status_code=404, detail="No game loop in this session")

    gl = session.game_loop
    gl.advance_round()
    get_repo().save_campaign(campaign)
    _broadcast_game_loop(campaign_id, gl)

    return {
        "round":         gl.round,
        "turn":          gl.turn,
        "actions_taken": list(gl.actions_taken),
    }


@router.post("/{session_number}/game-loop/combat/start")
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