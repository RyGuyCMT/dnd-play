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
      - DM receives everything (except its own messages)
      - Players receive messages where their name is sender OR recipient

    Also holds in-memory state for loaded campaigns (loaded via registry).
    """

    def __init__(self) -> None:
        # campaign_id → list[Client]  (rooms)
        self._rooms: dict[str, list[Client]] = {}
        # campaign_id → Campaign  (in-memory state after registry load)
        self._campaigns: dict[str, object] = {}

    # ── Campaign state (loaded from registry) ──────────────────────────────────

    def preload_campaign(self, campaign_id: str, state: object) -> None:
        """Store loaded campaign state. Called by REST /registries/{id}/load."""
        self._campaigns[campaign_id] = state

    def get_campaign(self, campaign_id: str) -> object | None:
        """Return loaded in-memory campaign state, or None."""
        return self._campaigns.get(campaign_id)

    def unload_campaign(self, campaign_id: str) -> None:
        """Remove in-memory state. Use when DM ends a campaign."""
        self._campaigns.pop(campaign_id, None)

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

    # ── Broadcast ───────────────────────────────────────────────────────────

    async def broadcast_message(
        self,
        campaign_id: str,
        message: Message,
        *,
        sender: Client | None = None,
    ) -> None:
        """Push a message to all relevant connected clients.

        The sender is excluded from recipients so they don't receive their own messages.
        DMs always receive all non-sender messages.
        Players receive if they are the sender or a named recipient.
        """
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
            # Sender never receives their own message
            if client is sender:
                continue
            # DM always receives (non-sender) messages
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

    async def broadcast_game_loop_update(
        self,
        campaign_id: str,
        state_type: str,
        mode: str,
        round_num: int,
        turn: int,
        active_participant: str,
        initiative_order: list[str],
        allowed_actions: list[str],
        broadcast_scope: str,
    ) -> None:
        """Push a game-loop state update to all connected clients in a campaign."""
        room = self._rooms.get(campaign_id, [])

        # Filter recipients based on broadcast_scope:
        #   ACTIVE  → only the active participant
        #   ALL    → everyone
        #   DM     → only the DM
        #   NONE   → no broadcast (state machine using this for side-effects only)
        targets: list[Client] = []
        for client in room:
            if broadcast_scope == "ALL":
                targets.append(client)
            elif broadcast_scope == "DM" and client.is_dm:
                targets.append(client)
            elif broadcast_scope == "ACTIVE" and client.character_name == active_participant:
                targets.append(client)
            elif broadcast_scope == "ACTIVE" and client.is_dm:
                # DM always sees active-participant broadcasts
                targets.append(client)

        if not targets:
            return

        payload = json.dumps({
            "type": "game_loop_update",
            "payload": {
                "state_type":      state_type,
                "mode":            mode,
                "round":           round_num,
                "turn":            turn,
                "active_participant": active_participant,
                "initiative_order": initiative_order,
                "allowed_actions": allowed_actions,
                "broadcast_scope": broadcast_scope,
            }
        })
        tasks = [client.websocket.send_text(payload) for client in targets]
        await asyncio.gather(*tasks, return_exceptions=True)

    # ── Query ─────────────────────────────────────────────────────────────────

    def connected_count(self, campaign_id: str) -> int:
        return len(self._rooms.get(campaign_id, []))


# Global singleton
ws_manager = WSManager()