"""Registry routes — browse and load campaigns via Session Zero registry."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from persistence.base import RegistryService


router = APIRouter(prefix="/registries", tags=["registries"])

_registry_service: RegistryService | None = None


def set_registry_service(svc: RegistryService) -> None:
    global _registry_service
    _registry_service = svc


def _get_registry_service() -> RegistryService:
    global _registry_service
    if _registry_service is None:
        from config import settings
        from persistence.base import LocalStorageAdapter
        adapter = LocalStorageAdapter(data_path=settings.data_path)
        _registry_service = RegistryService(adapter)
    return _registry_service


@router.get("")
def list_registries():
    """List all finalized campaigns (those with a registry).

    Returns minimal metadata — sufficient for a DM to pick which to load.
    Full campaign data is not loaded until explicitly selected.
    """
    svc = _get_registry_service()
    return svc.list_registries()


@router.get("/{campaign_id}")
def get_registry(campaign_id: str):
    """Get registry for a specific campaign."""
    svc = _get_registry_service()
    reg = svc.load_registry(campaign_id)
    if reg is None:
        raise HTTPException(status_code=404, detail="Registry not found")
    return {
        "campaign_id": reg.campaign_id,
        "campaign_path": reg.campaign_path,
        "world_state_path": reg.world_state_path,
        "characters": [{"name": cp.name, "path": cp.path} for cp in reg.characters],
        "created_at": reg.created_at,
        "session_zero_finalized_at": reg.session_zero_finalized_at,
    }


@router.post("/{campaign_id}/save")
def save_to_registry(campaign_id: str):
    """Finalize a campaign into the registry (called after Session Zero is done).

    Loads the campaign from its storage path, writes a registry entry so it
    can be discovered and loaded later, and returns the registry metadata.
    """
    svc = _get_registry_service()

    # Load raw campaign dict from wherever campaigns API stored it
    from config import settings
    from persistence.base import LocalStorageAdapter
    adapter = LocalStorageAdapter(data_path=settings.data_path)
    campaign_data = adapter.load_campaign(campaign_id)
    if campaign_data is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Build character pointers from campaign.characters dict
    from models.registry import CampaignRegistry, CharacterPointer
    characters = [
        CharacterPointer(
            name=name,
            path=f"campaigns/{campaign_id}/characters/{name.lower()}.json",
        )
        for name in campaign_data.get('characters', {})
    ]

    registry = CampaignRegistry.new(
        campaign_id=campaign_id,
        campaign_path=f"campaigns/{campaign_id}.json",  # flat storage (matches campaigns API)
        world_state_path=f"campaigns/{campaign_id}/world_state.json",
        characters=characters,
    )
    svc.save_registry(registry)

    return {"campaign_id": campaign_id, "registry_saved": True}


@router.get("/{campaign_id}/load")
def load_from_registry(campaign_id: str):
    """Load full campaign state from registry paths, store in WS manager.

    This is the explicit "select campaign" action — all state is loaded
    into memory from the paths recorded in the registry, then pushed into
    the WebSocket manager so connected clients can access it.

    DM must call this before connecting via WebSocket.
    """
    svc = _get_registry_service()
    result = svc.load_from_registry(campaign_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Registry not found or campaign path unreadable")
    campaign, world_state, character_sheets = result

    # Store in WS manager for WebSocket auth + in-memory state
    from websocket import ws_manager
    ws_manager.preload_campaign(campaign_id, campaign)

    return {
        "campaign": {
            "id": campaign.id,
            "title": campaign.title,
            "status": campaign.status.value if hasattr(campaign.status, 'value') else campaign.status,
            "current_session": campaign.current_session.number if campaign.current_session else None,
            "character_names": list(campaign.characters.keys()),
            "dm_token": campaign.dm_token,  # DM needs this to connect via WS
        },
        "world_state": world_state,
        "character_sheets": character_sheets,
    }
