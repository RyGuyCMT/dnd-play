"""Auth dependencies for FastAPI routes."""

from __future__ import annotations

from dataclasses import dataclass
from fastapi import HTTPException, Request
from config import settings
from auth import verify_token
from persistence.base import LocalStorageAdapter, Repository


@dataclass
class AuthContext:
    campaign_id: str
    character_name: str | None   # None = DM
    is_dm: bool


def require_auth(request: Request) -> AuthContext:
    """Extract and validate auth from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]   # strip "Bearer "

    # campaign_id from path params (FastAPI auto-injects these)
    campaign_id = request.path_params.get("campaign_id", "") or request.query_params.get("campaign_id", "")
    if not campaign_id:
        raise HTTPException(status_code=401, detail="Missing campaign_id")

    # Load campaign to get stored token hash
    repo = Repository(LocalStorageAdapter(settings.data_path))
    campaign = repo.load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Determine role from query params — character_name=None means DM
    role = request.query_params.get("role", "")
    is_dm = (role == "dm")

    if is_dm:
        if not verify_token(token, campaign_id, dm_token_hash=campaign.dm_token):
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        character_name = request.query_params.get("character_name")
        if character_name:
            char = campaign.characters.get(character_name)
            if char is None:
                raise HTTPException(status_code=404, detail="Character not found")
            if not verify_token(token, campaign_id, character_name=character_name,
                               character_token_hash=char.character_token):
                raise HTTPException(status_code=401, detail="Invalid token")
        else:
            # No role or character specified — treat as unauthenticated
            raise HTTPException(status_code=401, detail="Missing role (role=dm or character_name=...)")

    return AuthContext(
        campaign_id=campaign_id,
        character_name=request.query_params.get("character_name"),
        is_dm=is_dm,
    )


def require_dm(ctx: AuthContext) -> None:
    if not ctx.is_dm:
        raise HTTPException(status_code=403, detail="DM privileges required")