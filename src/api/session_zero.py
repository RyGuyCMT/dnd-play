"""Session Zero routes — campaign setup, character review, campaign activation."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import settings
from auth import generate_token
from persistence.base import LocalStorageAdapter, Repository, dataclass_to_dict
from models.campaign import Campaign, CampaignStatus, CampaignPhase
from models.character import Character


# ─── Enums ─────────────────────────────────────────────────────────────────────
# NOTE: CampaignPhase is imported from models.campaign, NOT redefined here.
# session_zero.py used to re-define it, causing a duplicate enum that broke
# equality checks (models.CampaignPhase.SETUP != session_zero.CampaignPhase.SETUP).

class CharacterStatus:
    """Status values for characters in Session Zero review."""
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ─── Request models ─────────────────────────────────────────────────────────────

class JoinRequest(BaseModel):
    player_id: str
    name: str
    character_class: str = ""
    race: str = ""
    backstory: str = ""


# ─── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/campaigns/{campaign_id}/session-zero", tags=["session-zero"])

_repo = None


def get_repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = Repository(LocalStorageAdapter(settings.data_path))
    return _repo


def set_repo(repo: Repository) -> None:
    global _repo
    _repo = repo


def _hash_token(token: str, campaign_id: str, character_name: str) -> str:
    key = f"{settings.secret_key}:{campaign_id}:{character_name}"
    return hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()[:64]


# ─── Campaign config (DM sets up before opening to players) ───────────────────

@router.patch("/config")
def configure_campaign(
    campaign_id: str,
    request: Request,
    ctx = None,  # injected by dependancy or None for DM-only
):
    """
    DM updates campaign title/elevator_pitch/tone/pacing and transitions phase.
    Called by the DM as they configure the campaign.

    Query params (all optional):
      title, elevator_pitch, tone, pacing, phase
    Auth: dm_token required (via require_dm dependency, injected by wrapper)
    """
    # Lazy import to avoid circular
    from api.deps import require_auth, require_dm as _require_dm, AuthContext

    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header[7:]
    repo = get_repo()
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Verify DM token
    if not _verify_dm_token(token, campaign_id, campaign.dm_token):
        raise HTTPException(status_code=401, detail="Invalid DM token")

    # Parse query params
    params = dict(request.query_params)
    if "title" in params:
        campaign.title = params["title"]
    if "elevator_pitch" in params:
        campaign.elevator_pitch = params["elevator_pitch"]
    if "tone" in params:
        campaign.tone = params["tone"]
    if "pacing" in params:
        campaign.pacing = params["pacing"]

    # Phase transition
    if "phase" in params:
        new_phase = CampaignPhase(params["phase"].lower())
        _transition_phase(campaign, new_phase)

    repo.save_campaign(campaign)
    return _campaign_summary(campaign)


def _transition_phase(campaign: Campaign, new_phase: CampaignPhase) -> None:
    """Validate and apply phase transition rules."""
    # Import here to avoid circular at module level
    from models.campaign import Campaign

    current = getattr(campaign, 'phase', CampaignPhase.SETUP)
    if isinstance(current, str):
        current = CampaignPhase(current)

    rules = {
        CampaignPhase.SETUP: {CampaignPhase.REVIEW},
        CampaignPhase.REVIEW: {CampaignPhase.ACTIVE, CampaignPhase.SETUP},
        CampaignPhase.ACTIVE: set(),  # no transitions out of ACTIVE via Session Zero
    }

    if new_phase not in rules.get(current, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {current.value} to {new_phase.value}"
        )

    campaign.phase = new_phase


def _verify_dm_token(token: str, campaign_id: str, dm_token_hash: str) -> bool:
    import hmac as _hmac
    key = f"{settings.secret_key}:{campaign_id}:dm"
    expected = _hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()[:64]
    return _hmac.compare_digest(expected, dm_token_hash or "")


# ─── Player: submit character for review ───────────────────────────────────────

@router.post("/join")
def join_campaign(campaign_id: str, body: JoinRequest):
    """
    Player submits their character to the campaign.
    Works without auth — players join via invite link.

    Creates character in PENDING status. DM reviews and approves before
    the player can connect via WebSocket.

    Only valid in SETUP or REVIEW phase.
    """
    repo = get_repo()
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    current_phase = getattr(campaign, 'phase', CampaignPhase.SETUP)
    if isinstance(current_phase, str):
        current_phase = CampaignPhase(current_phase)

    if current_phase not in {CampaignPhase.SETUP, CampaignPhase.REVIEW}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot join: campaign is {current_phase.value}"
        )

    if not body.name or not body.player_id:
        raise HTTPException(status_code=400, detail="name and player_id required")

    # Conflict check
    if campaign.characters and body.name in campaign.characters:
        raise HTTPException(status_code=409, detail="Character name already taken")

    # Generate character token (stored as hash)
    token_plain = generate_token()
    token_hash = _hash_token(token_plain, campaign_id, body.name)

    character = Character.create(
        name=body.name,
        player_id=body.player_id,
        character_class=body.character_class,
        race=body.race,
        backstory=body.backstory,
        character_token=token_hash,
    )

    # Track status internally (not in Character model — extend via campaign metadata)
    # Store pending status in campaign.pending_characters dict
    pending = getattr(campaign, '_pending_characters', {})
    pending[body.name] = CharacterStatus.PENDING
    campaign.pending_characters = pending

    campaign.register_character(character)
    repo.save_campaign(campaign)

    return {
        "name": body.name,
        "player_id": body.player_id,
        "character_token": token_plain,   # shown once
"status": "pending",
        "message": "DM will review your character before you can connect."
    }


# ─── DM: review characters ─────────────────────────────────────────────────────

@router.get("/characters")
def list_session_zero_characters(campaign_id: str, dm_token: str = ""):
    """
    List all characters in the campaign with their review status.
    DM only. Shows PENDING/APPROVED/REJECTED.
    Query param: dm_token (required)
    """
    repo = get_repo()
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Verify DM
    if not _verify_dm_token(dm_token, campaign_id, campaign.dm_token):
        raise HTTPException(status_code=401, detail="Invalid DM token")

    pending = getattr(campaign, 'pending_characters', {})

    return [
        {
            "name": ch.name,
            "player_id": ch.player_id,
            "class": ch.character_class,
            "race": ch.race,
            "backstory": ch.backstory,
            "status": pending.get(ch.name, CharacterStatus.APPROVED),
        }
        for ch in campaign.characters.values()
    ]


@router.patch("/characters/{character_name}/status")
def update_character_status(
    campaign_id: str,
    character_name: str,
    status: str = "",   # approved / rejected  (query param)
    dm_token: str = "",
):
    """
    DM approves or rejects a character.
    Only valid in REVIEW phase.

    Query params: status (required: 'approved' or 'rejected'), dm_token (required)
    """
    if not status or status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'")

    repo = get_repo()
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not _verify_dm_token(dm_token, campaign_id, campaign.dm_token):
        raise HTTPException(status_code=401, detail="Invalid DM token")

    current_phase = getattr(campaign, 'phase', CampaignPhase.SETUP)
    if isinstance(current_phase, str):
        current_phase = CampaignPhase(current_phase)

    if current_phase != CampaignPhase.REVIEW:
        raise HTTPException(status_code=409, detail="Only valid in REVIEW phase")

    if character_name not in campaign.characters:
        raise HTTPException(status_code=404, detail="Character not found")

    pending = getattr(campaign, '_pending_characters', {})
    pending[character_name] = CharacterStatus.APPROVED if status == "approved" else CharacterStatus.REJECTED
    campaign.pending_characters = pending
    repo.save_campaign(campaign)

    return {
        "name": character_name,
        "status": pending[character_name],
    }


# ─── DM: transition phase ──────────────────────────────────────────────────────

@router.post("/phase")
def transition_phase(
    campaign_id: str,
    phase: str = "",   # query param: setup / review / active
    dm_token: str = "",
):
    """
    DM moves the campaign to the next phase.
    Called explicitly by DM (not auto-transitions).

    - SETUP → REVIEW: DM is done configuring, opening to players
    - REVIEW → ACTIVE: DM finalizes (also writes registry + sets CampaignStatus)

    Query params: phase (required), dm_token (required)
    """
    if not phase:
        raise HTTPException(status_code=400, detail="phase query param required")

    try:
        new_phase = CampaignPhase(phase.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid phase: {phase}")

    repo = get_repo()
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not _verify_dm_token(dm_token, campaign_id, campaign.dm_token):
        raise HTTPException(status_code=401, detail="Invalid DM token")

    current_phase = getattr(campaign, 'phase', CampaignPhase.SETUP)
    if isinstance(current_phase, str):
        current_phase = CampaignPhase(current_phase)

    if new_phase not in {CampaignPhase.REVIEW, CampaignPhase.ACTIVE}:
        raise HTTPException(status_code=400, detail="Can only transition to REVIEW or ACTIVE via this endpoint")

    # Validate transition
    rules = {
        CampaignPhase.SETUP: {CampaignPhase.REVIEW},
        CampaignPhase.REVIEW: {CampaignPhase.ACTIVE},
        CampaignPhase.ACTIVE: set(),
    }
    if new_phase not in rules.get(current_phase, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {current_phase.value} to {new_phase.value}"
        )

    campaign.phase = new_phase

    # ACTIVE: finalize = write registry + set CampaignStatus.ACTIVE
    if new_phase == CampaignPhase.ACTIVE:
        campaign.status = CampaignStatus.ACTIVE
        _write_registry(campaign)

    repo.save_campaign(campaign)
    return {
        "campaign_id": campaign_id,
        "phase": campaign.phase.value,
        "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
    }


def _write_registry(campaign: Campaign) -> None:
    """Write a finalized campaign to the registry."""
    from models.registry import CampaignRegistry, CharacterPointer
    characters = [
        CharacterPointer(
            name=name,
            path=f"campaigns/{campaign.id}/characters/{name.lower()}.json",
        )
        for name in campaign.characters
    ]
    registry = CampaignRegistry.new(
        campaign_id=campaign.id,
        campaign_path=f"campaigns/{campaign.id}.json",
        world_state_path=f"campaigns/{campaign.id}/world_state.json",
        characters=characters,
    )
    adapter = LocalStorageAdapter(settings.data_path)
    adapter.save_registry(dataclass_to_dict(registry))


# ─── Status query ─────────────────────────────────────────────────────────────

@router.get("")
def get_session_zero_status(campaign_id: str):
    """Get current phase and character review summary. No auth required."""
    repo = get_repo()
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    current_phase = getattr(campaign, 'phase', CampaignPhase.SETUP)
    if isinstance(current_phase, str):
        current_phase = CampaignPhase(current_phase)

    pending = getattr(campaign, '_pending_characters', {})
    characters = [
        {
            "name": ch.name,
            "player_id": ch.player_id,
            "class": ch.character_class,
            "race": ch.race,
            "status": pending.get(ch.name, CharacterStatus.APPROVED),
        }
        for ch in campaign.characters.values()
    ]

    return {
        "campaign_id": campaign_id,
        "title": campaign.title,
        "phase": current_phase.value,
        "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
        "elevator_pitch": campaign.elevator_pitch,
        "tone": campaign.tone,
        "pacing": campaign.pacing,
        "characters": characters,
        "dm_token_plain": None,  # never exposed after creation
    }


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _campaign_summary(campaign: Campaign) -> dict:
    current_phase = getattr(campaign, 'phase', CampaignPhase.SETUP)
    if isinstance(current_phase, str):
        current_phase = CampaignPhase(current_phase)
    return {
        "campaign_id": campaign.id,
        "title": campaign.title,
        "phase": current_phase.value,
        "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
        "elevator_pitch": campaign.elevator_pitch,
        "tone": campaign.tone,
        "pacing": campaign.pacing,
    }