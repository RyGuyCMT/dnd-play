"""WebSocket manager — real-time push to connected clients."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional

from models.message import Message


logger = logging.getLogger(__name__)


@dataclass
class Client:
    websocket: WebSocket
    campaign_id: str
    character_name: str | None    # None = DM
    is_dm: bool


class WSManager:
    """
    Manages WebSocket connections per campaign.

    On new message: broadcast to relevant clients
      - DM receives everything
      - Players receive messages where their name is sender OR recipient
    """

    def __init__(self) -> None:
        # campaign_id → list[Client]
        self._rooms: dict[str, list[Client]] = {}

    # ── Connection ─────────────────────────────────────────────────────────────

    async def connect(self, client: Client) -> None:
        await client.websocket.accept()
        room = self._rooms.setdefault(client.campaign_id, [])
        room.append(client)
        logger.info(f"WS connected: {client.character_name or 'DM'} @ {client.campaign_id}")

    def disconnect(self, client: Client) -> None:
        room = self._rooms.get(client.campaign_id, [])
        room[:] = [c for c in room if c.websocket != client.websocket]
        if not room:
            del self._rooms[client.campaign_id]
        logger.info(f"WS disconnected: {client.character_name or 'DM'} @ {client.campaign_id}")

    # ── Broadcast ────────────────────────────────────────────────────────────

    async def broadcast_message(self, campaign_id: str, message: Message) -> None:
        """Push a message to all relevant connected clients."""
        room = self._rooms.get(campaign_id, [])
        payload = json.dumps({
            "type": "message",
            "payload": {
                "id": message.id,
                "sender": message.sender_name,
                "recipients": message.recipient_names,
                "scope": message.scope.name,
                "content": message.content,
                "sent_at": message.sent_at,
                "session_number": message.session_number,
                "is_system": message.is_system,
            }
        })

        tasks = []
        for client in room:
            # DM always receives
            if client.is_dm:
                tasks.append(client.websocket.send_text(payload))
                continue

            # Players receive if they are sender or recipient
            if message.sender_name == client.character_name:
                tasks.append(client.websocket.send_text(payload))
                continue
            if client.character_name and client.character_name in message.recipient_names:
                tasks.append(client.websocket.send_text(payload))
                continue

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_session_event(self, campaign_id: str,
                                       event: str, session_number: int) -> None:
        """Notify all clients in a campaign of a session event (start/end/connect/disconnect)."""
        room = self._rooms.get(campaign_id, [])
        payload = json.dumps({
            "type": "session_event",
            "payload": {"event": event, "session_number": session_number}
        })
        tasks = [client.websocket.send_text(payload) for client in room]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ── Query ─────────────────────────────────────────────────────────────────

    def connected_count(self, campaign_id: str) -> int:
        return len(self._rooms.get(campaign_id, []))


# Global singleton
ws_manager = WSManager()