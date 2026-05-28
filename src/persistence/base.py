"""Persistence — JSON file storage adapter with a repository interface.

Storage layout:
  <data_path>/
    campaigns/
      <campaign_id>.json
    messages/
      <campaign_id>/
        <message_id>.json
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


# ─── JSON Helpers ──────────────────────────────────────────────────────────────

class PydanticEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        from pydantic import BaseModel
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, set):
            return sorted(list(obj), key=str)
        if isinstance(obj, Enum):
            # Store enum name (SETUP, DRAFT) not value (setup, draft)
            return obj.name
        return super().default(obj)


def to_json(obj: Any, pretty: bool = False) -> str:
    kwargs = {"indent": 2, "cls": PydanticEncoder} if pretty else {}
    return json.dumps(obj, **kwargs)


def from_json(data: str, model_type: type[T]) -> T:
    parsed = json.loads(data)
    if isinstance(model_type, type) and hasattr(model_type, "model_validate"):
        return model_type.model_validate(parsed)
    instance = model_type(**parsed)
    # Fix known enum fields post-load
    if model_type == Campaign:
        if isinstance(instance.status, str):
            from models.campaign import CampaignStatus
            instance.status = CampaignStatus[instance.status]
    return instance


def dataclass_to_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Cannot convert {type(obj)} to dict")


# ─── Storage Adapter ───────────────────────────────────────────────────────────

class StorageAdapter(ABC):
    @abstractmethod
    def save_campaign(self, campaign: dict) -> None: ...
    @abstractmethod
    def load_campaign(self, campaign_id: str) -> dict | None: ...
    @abstractmethod
    def list_campaigns(self) -> list[dict]: ...
    @abstractmethod
    def save_message(self, campaign_id: str, message: dict) -> None: ...
    @abstractmethod
    def load_messages(self, campaign_id: str) -> list[dict]: ...
    @abstractmethod
    def save_snapshot(self, key: str, data: dict) -> None: ...
    @abstractmethod
    def load_snapshot(self, key: str) -> dict | None: ...

    @abstractmethod
    def campaign_exists(self, campaign_id: str) -> bool: ...

    # ── Registry ────────────────────────────────────────────────────────────────

    @abstractmethod
    def save_registry(self, registry: dict) -> None: ...
    @abstractmethod
    def load_registry(self, campaign_id: str) -> dict | None: ...
    @abstractmethod
    def list_registries(self) -> list[dict]: ...


# ─── Local JSON Storage ────────────────────────────────────────────────────────

class LocalStorageAdapter(StorageAdapter):
    def __init__(self, data_path: str | None = None) -> None:
        self._root = Path(data_path or "/data")
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "campaigns").mkdir(exist_ok=True)
        (self._root / "messages").mkdir(exist_ok=True)

    def _campaign_path(self, campaign_id: str) -> Path:
        return self._root / "campaigns" / f"{campaign_id}.json"

    def _message_dir(self, campaign_id: str) -> Path:
        d = self._root / "messages" / campaign_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── Campaigns ────────────────────────────────────────────────────────────────

    def save_campaign(self, campaign: dict) -> None:
        path = self._campaign_path(campaign["id"])
        path.write_text(to_json(campaign, pretty=True))

    def load_campaign(self, campaign_id: str) -> dict | None:
        path = self._campaign_path(campaign_id)
        if not path.exists():
            return None
        return from_json(path.read_text(), dict)

    def campaign_exists(self, campaign_id: str) -> bool:
        return self._campaign_path(campaign_id).exists()

    def list_campaigns(self) -> list[dict]:
        out = []
        for p in (self._root / "campaigns").glob("*.json"):
            try:
                c = from_json(p.read_text(), dict)
                out.append({
                    "id": c.get("id"),
                    "title": c.get("title", "Unnamed"),
                    "status": c.get("status", ""),
                    "updated_at": c.get("updated_at", ""),
                })
            except Exception:
                pass
        return out

    # ── Messages ───────────────────────────────────────────────────────────────

    def save_message(self, campaign_id: str, message: dict) -> None:
        msg_id = message["id"]
        path = self._message_dir(campaign_id) / f"{msg_id}.json"
        path.write_text(to_json(message, pretty=True))

    def load_messages(self, campaign_id: str) -> list[dict]:
        dir_path = self._message_dir(campaign_id)
        messages = []
        for p in dir_path.glob("*.json"):
            try:
                messages.append(from_json(p.read_text(), dict))
            except Exception:
                pass
        messages.sort(key=lambda m: m.get("sent_at", ""))
        return messages

    # ── Snapshots ───────────────────────────────────────────────────────────────

    def save_snapshot(self, key: str, data: dict) -> None:
        snap_dir = self._root / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        # Keys may be bare names ("my_snap") or relative paths
        # ("campaigns/c1/world_state"). Normalise so we never double-suffix.
        safe_key = key.removesuffix(".json")
        path = snap_dir / f"{safe_key}.json"
        path.write_text(to_json(data, pretty=True))

    def load_snapshot(self, key: str) -> dict | None:
        path = self._root / "snapshots" / f"{key.removesuffix('.json')}.json"
        if not path.exists():
            return None
        return from_json(path.read_text(), dict)

    # ── Registry ────────────────────────────────────────────────────────────────

    def _registry_path(self, campaign_id: str) -> Path:
        return self._root / "registries" / f"{campaign_id}.json"

    def _registry_root(self) -> Path:
        r = self._root / "registries"
        r.mkdir(parents=True, exist_ok=True)
        return r

    def save_registry(self, registry: dict) -> None:
        path = self._registry_path(registry["campaign_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(to_json(registry, pretty=True))

    def load_registry(self, campaign_id: str) -> dict | None:
        path = self._registry_path(campaign_id)
        if not path.exists():
            return None
        return from_json(path.read_text(), dict)

    def list_registries(self) -> list[dict]:
        out = []
        for p in self._registry_root().glob("*.json"):
            try:
                r = from_json(p.read_text(), dict)
                out.append({
                    "campaign_id": r.get("campaign_id"),
                    "campaign_path": r.get("campaign_path"),
                    "world_state_path": r.get("world_state_path"),
                    "character_count": len(r.get("characters", [])),
                    "session_zero_finalized_at": r.get("session_zero_finalized_at", ""),
                })
            except Exception:
                pass
        return out

    # ── Load arbitrary path (for registry-driven loading) ───────────────────────

    def load_file(self, path: str) -> dict | None:
        """Load a JSON file given a relative path from _root or an absolute path."""
        p = Path(path)
        if not p.is_absolute():
            p = self._root / p
        if not p.exists():
            return None
        return from_json(p.read_text(), dict)


# ─── Repository ────────────────────────────────────────────────────────────────

from models.campaign import Campaign
from models.message import Message
from models.session import GameSession
from models.registry import CampaignRegistry, CharacterPointer


class RegistryService:
    """High-level registry operations — save, load, resolve full campaign state."""

    def __init__(self, adapter: StorageAdapter) -> None:
        self._adapter = adapter

    def save_registry(self, registry: CampaignRegistry) -> None:
        self._adapter.save_registry(dataclass_to_dict(registry))

    def load_registry(self, campaign_id: str) -> CampaignRegistry | None:
        data = self._adapter.load_registry(campaign_id)
        if data is None:
            return None
        return from_json(to_json(data), CampaignRegistry)

    def list_registries(self) -> list[dict]:
        return self._adapter.list_registries()

    def load_from_registry(self, campaign_id: str) -> tuple[Campaign, dict, list[dict]] | None:
        """Resolve all paths from the registry and load the full campaign state.

        Returns (campaign, world_state, character_sheets) or None if registry missing.
        Paths are resolved relative to _root, or as absolute URLs.

        Character sheets that can't be loaded (missing files) are skipped silently —
        the DM can add them later from the character creation flow.
        """
        registry = self.load_registry(campaign_id)
        if registry is None:
            return None

        campaign_data = self._adapter.load_file(registry.campaign_path)
        if campaign_data is None:
            return None

        world_data = self._adapter.load_file(registry.world_state_path)
        character_sheets = [
            cs for cs in (self._adapter.load_file(cp.path) for cp in registry.characters)
            if cs is not None
        ]

        campaign = from_json(to_json(campaign_data), Campaign)
        return campaign, world_data or {}, character_sheets


class Repository:
    def __init__(self, adapter: StorageAdapter) -> None:
        self._adapter = adapter

    # ── Campaign ────────────────────────────────────────────────────────────────

    def save_campaign(self, campaign: Campaign) -> None:
        self._adapter.save_campaign(dataclass_to_dict(campaign))

    def load_campaign(self, campaign_id: str) -> Campaign | None:
        data = self._adapter.load_campaign(campaign_id)
        if data is None:
            return None
        return from_json(to_json(data), Campaign)

    def campaign_exists(self, campaign_id: str) -> bool:
        return self._adapter.campaign_exists(campaign_id)

    def list_campaigns(self) -> list[dict]:
        return self._adapter.list_campaigns()

    # ── Messages ───────────────────────────────────────────────────────────────

    def save_message(self, message: Message) -> None:
        self._adapter.save_message(message.campaign_id, dataclass_to_dict(message))

    def load_messages(self, campaign_id: str) -> list[Message]:
        data = self._adapter.load_messages(campaign_id)
        return [from_json(to_json(m), Message) for m in data]

    def messages_for(self, campaign_id: str, character_name: str) -> list[Message]:
        """Return messages where character_name is a sender or recipient."""
        all_msgs = self.load_messages(campaign_id)
        return [
            m for m in all_msgs
            if m.sender_name == character_name or character_name in m.recipient_names
        ]

    def messages_from(self, campaign_id: str, sender_name: str) -> list[Message]:
        return [
            m for m in self.load_messages(campaign_id)
            if m.sender_name == sender_name
        ]

    # ── Snapshots ───────────────────────────────────────────────────────────────

    def save_snapshot(self, key: str, data: dict) -> None:
        self._adapter.save_snapshot(key, data)

    def load_snapshot(self, key: str) -> dict | None:
        return self._adapter.load_snapshot(key)