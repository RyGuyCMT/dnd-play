"""Simple token-based auth.

Design:
  - Campaign creator (DM) gets a `dm_token` — full privileges
  - When a character registers, they get a `character_token` tied to campaign + character
  - All requests pass token via Authorization header: "Bearer <token>"
  - No user accounts, no passwords — tokens are shared secrets
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import Enum, auto

from config import settings


class Role(Enum):
    DM       = auto()   # full privileges within a campaign
    PLAYER   = auto()   # can only send/receive messages for their character
    SYSTEM   = auto()   # internal server messages


@dataclass
class TokenClaims:
    campaign_id: str
    character_name: str | None    # None for DM token
    role: Role


def generate_token() -> str:
    """Generate a random token suitable for use as a secret."""
    return secrets.token_urlsafe(32)


def generate_dm_token(campaign_id: str) -> tuple[str, str]:
    """Generate a DM token. Returns (token, token_hash) — store hash only."""
    token = generate_token()
    return token, _hash(token, campaign_id, "dm")


def generate_character_token(campaign_id: str, character_name: str) -> tuple[str, str]:
    """Generate a character token. Returns (token, token_hash)."""
    token = generate_token()
    return token, _hash(token, campaign_id, character_name)


def _hash(token: str, campaign_id: str, suffix: str) -> str:
    """Stable HMAC hash of a token for storage."""
    key = f"{settings.secret_key}:{campaign_id}:{suffix}"
    return hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest()[:64]


def verify_token(token: str, campaign_id: str, character_name: str | None = None,
                 dm_token_hash: str | None = None,
                 character_token_hash: str | None = None) -> bool:
    """Verify a token against stored hash(es)."""
    if character_name is None:
        # DM token check
        expected = _hash(token, campaign_id, "dm")
        return hmac.compare_digest(expected, dm_token_hash or "")
    else:
        expected = _hash(token, campaign_id, character_name)
        return hmac.compare_digest(expected, character_token_hash or "")