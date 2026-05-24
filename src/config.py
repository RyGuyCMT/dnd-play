"""Configuration — environment variables → settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    # Storage
    storage_mode: str = "local"          # "local" | "postgres"
    data_path: str = "/data"
    postgres_url: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = None       # defaults allow all

    # Auth
    secret_key: str = "dev-secret-change-in-production"

    def __post_init__(self) -> None:
        if self.cors_origins is None:
            self.cors_origins = ["*"]


def load_settings() -> Settings:
    return Settings(
        storage_mode=os.getenv("STORAGE_MODE", "local"),
        data_path=os.getenv("DATA_PATH", "/data"),
        postgres_url=os.getenv("POSTGRES_URL", ""),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        secret_key=os.getenv("SECRET_KEY", "dev-secret-change-in-production"),
    )


# Global singleton
settings = load_settings()