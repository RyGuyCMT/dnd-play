"""
Persistence layer — JSON serializer + storage adapters.

Design goals:
  1. All domain models serialize to JSON (portable, versioned, human-readable)
  2. Single source of truth: pydantic for validation on read/write
  3. Storage adapters: LocalFiles (JSON), Postgres (JSONB), SQLServer (TEXT)
  4. The engine never talks to storage directly — only through repositories

Storage shapes:
  - Local:  one campaign = one JSON file  (~/.hermes/dnd-sessions/)
  - Postgres: campaigns table (id, name, data JSONB) + sessions table (id, campaign_id, data JSONB)
  - SQLServer: same but data = TEXT column
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

import pydantic

T = TypeVar("T")


# ─── JSON Helpers ──────────────────────────────────────────────────────────────

class PydanticEncoder(json.JSONEncoder):
    """Encode pydantic models and dataclasses to JSON."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, pydantic.BaseModel):
            return obj.model_dump(mode="json")
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, set):
            return sorted(list(obj), key=str)
        return super().default(obj)


def to_json(obj: Any, pretty: bool = False) -> str:
    kwargs = {"indent": 2, "cls": PydanticEncoder} if pretty else {}
    return json.dumps(obj, **kwargs)


def from_json(data: str, model_type: type[T]) -> T:
    """Parse JSON into a pydantic model or dataclass."""
    parsed = json.loads(data)
    if isinstance(model_type, type) and issubclass(model_type, pydantic.BaseModel):
        return model_type.model_validate(parsed)
    # dataclass
    return model_type(**parsed)


# ─── Storage Adapter Interface ─────────────────────────────────────────────────

class StorageAdapter(ABC):
    """Abstract storage backend. Implement for Postgres, SQLServer, Local, etc."""

    @abstractmethod
    def save_campaign(self, campaign: dict) -> None:
        """Upsert a campaign. Raises on failure."""
        ...

    @abstractmethod
    def load_campaign(self, campaign_id: str) -> dict | None:
        """Load a campaign by ID. Returns None if not found."""
        ...

    @abstractmethod
    def list_campaigns(self) -> list[dict]:
        """List all campaigns (id + name + updated_at only)."""
        ...

    @abstractmethod
    def save_session(self, session: dict) -> None:
        ...

    @abstractmethod
    def load_session(self, session_id: str) -> dict | None:
        ...

    @abstractmethod
    def save_world(self, world_id: str, world: dict) -> None:
        ...

    @abstractmethod
    def load_world(self, world_id: str) -> dict | None:
        ...

    # ── Generic key-value (for arbitrary serializable state) ─────────────────

    @abstractmethod
    def save_snapshot(self, key: str, data: dict) -> None:
        ...

    @abstractmethod
    def load_snapshot(self, key: str) -> dict | None:
        ...


# ─── Local File Storage ─────────────────────────────────────────────────────────

@dataclass
class LocalStorageConfig:
    base_path: Path = Path.home() / ".hermes" / "dnd-sessions"


class LocalStorageAdapter(StorageAdapter):
    """
    Stores everything as JSON files on disk.
    Layout:
      ~/.hermes/dnd-sessions/
        campaigns/
          <campaign_id>.json
        worlds/
          <world_id>.json
        sessions/
          <session_id>.json
        snapshots/
          <key>.json
    """

    def __init__(self, config: LocalStorageConfig | None = None) -> None:
        self.cfg = config or LocalStorageConfig()
        self._root = self.cfg.base_path
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "campaigns").mkdir(exist_ok=True)
        (self._root / "worlds").mkdir(exist_ok=True)
        (self._root / "sessions").mkdir(exist_ok=True)
        (self._root / "snapshots").mkdir(exist_ok=True)

    def _campaign_path(self, campaign_id: str) -> Path:
        return self._root / "campaigns" / f"{campaign_id}.json"

    def _session_path(self, session_id: str) -> Path:
        return self._root / "sessions" / f"{session_id}.json"

    def _world_path(self, world_id: str) -> Path:
        return self._root / "worlds" / f"{world_id}.json"

    def _snapshot_path(self, key: str) -> Path:
        return self._root / "snapshots" / f"{key}.json"

    # ── Campaign ────────────────────────────────────────────────────────────────

    def save_campaign(self, campaign: dict) -> None:
        path = self._campaign_path(campaign["id"])
        path.write_text(to_json(campaign, pretty=True))

    def load_campaign(self, campaign_id: str) -> dict | None:
        path = self._campaign_path(campaign_id)
        if not path.exists():
            return None
        return from_json(path.read_text(), dict)

    def list_campaigns(self) -> list[dict]:
        out = []
        for p in (self._root / "campaigns").glob("*.json"):
            c = from_json(p.read_text(), dict)
            out.append({
                "id": c.get("id"),
                "name": c.get("name", "Unnamed"),
                "updated_at": c.get("updated_at", ""),
            })
        return out

    # ── Session ────────────────────────────────────────────────────────────────

    def save_session(self, session: dict) -> None:
        path = self._session_path(session["id"])
        path.write_text(to_json(session, pretty=True))

    def load_session(self, session_id: str) -> dict | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        return from_json(path.read_text(), dict)

    # ── World ──────────────────────────────────────────────────────────────────

    def save_world(self, world_id: str, world: dict) -> None:
        path = self._world_path(world_id)
        path.write_text(to_json(world, pretty=True))

    def load_world(self, world_id: str) -> dict | None:
        path = self._world_path(world_id)
        if not path.exists():
            return None
        return from_json(path.read_text(), dict)

    # ── Snapshots ──────────────────────────────────────────────────────────────

    def save_snapshot(self, key: str, data: dict) -> None:
        path = self._snapshot_path(key)
        path.write_text(to_json(data, pretty=True))

    def load_snapshot(self, key: str) -> dict | None:
        path = self._snapshot_path(key)
        if not path.exists():
            return None
        return from_json(path.read_text(), dict)


# ─── Repository ─────────────────────────────────────────────────────────────────

@dataclass
class Repository:
    """
    High-level persistence interface used by the rest of the app.
    Wraps a StorageAdapter and handles domain model serialization.

    Usage:
      repo = Repository(LocalStorageAdapter())
      campaign = Campaign(id="...", name="...")
      repo.save(campaign)
      loaded = repo.load(Campaign, "...")
    """
    _adapter: StorageAdapter

    def save(self, model: Any) -> None:
        """Save any domain model (Campaign, GameSession, WorldState, etc.)."""
        if isinstance(model, Campaign):
            self._adapter.save_campaign(model.model_dump(mode="json"))
        elif isinstance(model, GameSession):
            self._adapter.save_session(model.model_dump(mode="json"))
        elif isinstance(model, WorldState):
            self._adapter.save_world(model.world_id, model.model_dump(mode="json"))
        else:
            # Generic snapshot
            key = getattr(model, "id", str(type(model).__name__))
            self._adapter.save_snapshot(key, model if isinstance(model, dict) else model.model_dump(mode="json"))

    def load(self, model_type: type[T], id_: str) -> T | None:
        """Load a model by ID. Returns None if not found."""
        if model_type == Campaign:
            data = self._adapter.load_campaign(id_)
        elif model_type == GameSession:
            data = self._adapter.load_session(id_)
        elif model_type == WorldState:
            data = self._adapter.load_world(id_)
        else:
            data = self._adapter.load_snapshot(id_)
        if data is None:
            return None
        return from_json(to_json(data), model_type)

    def list_campaigns(self) -> list[dict]:
        return self._adapter.list_campaigns()

    def save_snapshot(self, key: str, data: dict) -> None:
        self._adapter.save_snapshot(key, data)

    def load_snapshot(self, key: str) -> dict | None:
        return self._adapter.load_snapshot(key)


# ─── Import domain models for repository ──────────────────────────────────────
from dnd_core.models import Campaign, GameSession, WorldState