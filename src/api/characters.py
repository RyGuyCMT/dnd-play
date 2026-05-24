"""Character registration routes."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException
from config import settings

from api.deps import AuthContext, require_auth, require_dm
from auth import generate_token
from config import settings
from models.character import Character
from persistence.base import Repository, LocalStorageAdapter


router = APIRouter(prefix="/campaigns/{campaign_id}/characters", tags=["characters"])

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


@router.post("")
def register_character(campaign_id: str, request: dict, ctx: AuthContext = Depends(require_auth)):
    """
    Register (invite) a character to the campaign.
    DM or player (with their own player_id) can register.
    Returns character_name + character_token (shown once).
    """
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    name = request.get("name", "")
    player_id = request.get("player_id", "")
    character_class = request.get("class", "")
    race = request.get("race", "")
    backstory = request.get("backstory", "")

    if not name or not player_id:
        raise HTTPException(status_code=400, detail="name and player_id required")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if name in campaign.characters:
        raise HTTPException(status_code=409, detail="Character name already taken")

    # Generate token pair — plaintext returned once, hash stored
    token_plain = generate_token()
    token_hash = _hash_token(token_plain, campaign_id, name)

    character = Character.create(
        name=name,
        player_id=player_id,
        character_class=character_class,
        race=race,
        backstory=backstory,
        character_token=token_hash,
    )
    campaign.register_character(character)
    get_repo().save_campaign(campaign)

    return {
        "name": name,
        "player_id": player_id,
        "character_token": token_plain,   # shown once
    }


@router.get("")
def list_characters(campaign_id: str):
    """List all registered characters in the campaign."""
    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return [
        {
            "name": ch.name,
            "player_id": ch.player_id,
            "class": ch.character_class,
            "race": ch.race,
        }
        for ch in campaign.characters.values()
    ]


@router.get("/{character_name}")
def get_character(campaign_id: str, character_name: str):
    """Get character details."""
    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if character_name not in campaign.characters:
        raise HTTPException(status_code=404, detail="Character not found")

    ch = campaign.characters[character_name]
    return {
        "name": ch.name,
        "player_id": ch.player_id,
        "class": ch.character_class,
        "race": ch.race,
        "backstory": ch.backstory,
    }