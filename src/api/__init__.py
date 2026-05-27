"""API package."""

from api.campaigns import router as campaigns_router
from api.sessions import router as sessions_router
from api.characters import router as characters_router
from api.messages import router as messages_router
from api.registries import router as registries_router

__all__ = [
    "campaigns_router",
    "sessions_router",
    "characters_router",
    "messages_router",
    "registries_router",
]
