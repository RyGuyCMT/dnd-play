"""Campaign routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from config import settings

from api.deps import AuthContext, require_auth, require_dm
from auth import generate_dm_token
from models.campaign import Campaign, CampaignStatus
from persistence.base import Repository, LocalStorageAdapter


router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_repo = None


def get_repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = Repository(LocalStorageAdapter(settings.data_path))
    return _repo


def set_repo(repo: Repository) -> None:
    global _repo
    _repo = repo


@router.post("", response_model=dict)
def create_campaign(request: Request):
    """Create a new campaign. Returns campaign + dm_token."""
    body = request.query_params
    title = body.get("title", "Unnamed Campaign")

    dm_token_plain, dm_token_hash = generate_dm_token(campaign_id="")

    campaign = Campaign.new(title=title, dm_token=dm_token_hash)

    import hashlib, hmac
    key = f"{settings.secret_key}:{campaign.id}:dm"
    campaign.dm_token = hmac.new(key.encode(), dm_token_plain.encode(), hashlib.sha256).hexdigest()[:64]

    get_repo().save_campaign(campaign)

    return {
        "id": campaign.id,
        "title": campaign.title,
        "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
        "dm_token": dm_token_plain,
    }


@router.get("")
def list_campaigns():
    """List all campaigns."""
    return get_repo().list_campaigns()


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str):
    """Get campaign details."""
    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {
        "id": campaign.id,
        "title": campaign.title,
        "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
        "current_session": campaign.current_session.number if campaign.current_session else None,
        "character_names": list(campaign.characters.keys()),
    }


@router.patch("/{campaign_id}")
def update_campaign(campaign_id: str, request: Request,
                    ctx: AuthContext = Depends(require_auth)):
    """Update campaign title/status. DM only."""
    require_dm(ctx)
    if ctx.campaign_id != campaign_id:
        raise HTTPException(status_code=403, detail="Not your campaign")

    campaign = get_repo().load_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    body = request.query_params
    if "title" in body:
        campaign.title = body["title"]
    if "status" in body:
        campaign.status = CampaignStatus[body["status"].upper()]

    get_repo().save_campaign(campaign)
    return {"ok": True}