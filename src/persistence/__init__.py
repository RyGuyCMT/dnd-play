"""Persistence package."""

from .base import (
    LocalStorageAdapter,
    Repository,
    StorageAdapter,
    dataclass_to_dict,
    from_json,
    to_json,
)

__all__ = [
    "LocalStorageAdapter",
    "Repository",
    "StorageAdapter",
    "dataclass_to_dict",
    "from_json",
    "to_json",
]
