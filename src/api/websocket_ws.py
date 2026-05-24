"""WebSocket endpoint — real-time client connections."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from config import settings

from config import settings
from persistence.base import LocalStorageAdapter, Repository
from websocket import Client, ws_manager


logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


def _hash_token(token: str, campaign_id: str, suffix: str) -> str:
    key = f"{settings.secret_key}:{campaign_id}:{suffix}"
    return hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()[:64]


@router.websocket("/campaigns/{campaign_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    campaign_id: str,
    token: str,
    character_name: str | None = None,
    dm_token: str | None = None,
):
    """
    WebSocket endpoint for real-time messaging.

    Connect as DM:
      ws://host/campaigns/<id>/ws?token=<dm_token>&dm_token=<dm_token>

    Connect as player:
      ws://host/campaigns/<id>/ws?token=<character_token>&character_name=<name>
    """
    repo = Repository(LocalStorageAdapter(settings.data_path))
    campaign = repo.load_campaign(campaign_id)

    if campaign is None:
        await websocket.close(code=4004, reason="Campaign not found")
        return

    # Verify token
    if character_name is None:
        # DM connection
        expected = _hash_token(token, campaign_id, "dm")
        if not hmac.compare_digest(expected, campaign.dm_token):
            await websocket.close(code=4001, reason="Invalid DM token")
            return
        is_dm = True
        char_name: str | None = None
    else:
        # Player connection
        if character_name not in campaign.characters:
            await websocket.close(code=4004, reason="Character not registered")
            return
        char = campaign.characters[character_name]
        expected = _hash_token(token, campaign_id, character_name)
        if not hmac.compare_digest(expected, char.character_token):
            await websocket.close(code=4001, reason="Invalid character token")
            return
        is_dm = False
        char_name = character_name

    client = Client(
        websocket=websocket,
        campaign_id=campaign_id,
        character_name=char_name,
        is_dm=is_dm,
    )
    await ws_manager.connect(client)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg.get("type") == "message":
                await _handle_ws_message(char_name, is_dm, campaign_id, msg, repo)
    except WebSocketDisconnect:
        ws_manager.disconnect(client)


async def _handle_ws_message(
    character_name: str | None,
    is_dm: bool,
    campaign_id: str,
    msg: dict,
    repo: Repository,
):
    from models.message import RecipientScope
    from services.messages import send_message

    content = msg.get("content", "").strip()
    if not content:
        return

    scope_name = msg.get("scope", "SINGLE").upper()
    try:
        scope = RecipientScope[scope_name]
    except KeyError:
        return

    recipient_names = msg.get("recipient_names", [])

    if is_dm:
        sender_name = "DM"
    else:
        sender_name = character_name or "DM"

    message = send_message(
        repo=repo,
        campaign_id=campaign_id,
        sender_name=sender_name,
        scope=scope,
        recipient_names=recipient_names,
        content=content,
    )
    await ws_manager.broadcast_message(campaign_id, message)