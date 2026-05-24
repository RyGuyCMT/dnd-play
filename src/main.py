"""Uvicorn entry point — wires everything together."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from persistence.base import LocalStorageAdapter, Repository
from api import (campaigns_router, sessions_router,
                          characters_router, messages_router)
from api import websocket_ws
from websocket import ws_manager


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init repository
    adapter = LocalStorageAdapter(data_path=settings.data_path)
    repo = Repository(adapter)

    # Inject repo into all route modules
    from api import campaigns, sessions, characters, messages
    campaigns.set_repo(repo)
    sessions.set_repo(repo)
    characters.set_repo(repo)
    messages.set_repo(repo)

    logger.info(f"D&D Play server started — data at {settings.data_path}")
    yield
    # Shutdown
    logger.info("D&D Play server shutting down")


app = FastAPI(
    title="D&D Play",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(campaigns_router)
app.include_router(sessions_router)
app.include_router(characters_router)
app.include_router(messages_router)

# WebSocket
app.include_router(websocket_ws.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "dnd_play.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )