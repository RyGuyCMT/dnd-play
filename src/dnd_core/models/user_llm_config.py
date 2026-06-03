"""
Per-user LLM configuration.
Each user owns their own LLM credentials and preferences.
The campaign never sees keys — only the generated output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from dnd_core.models.content_settings import GenerationMode


class LLMProvider(Enum):
    OPENAI         = auto()
    ANTHROPIC      = auto()
    OPENROUTER     = auto()
    OLLAMA         = auto()    # Local models
    GROQ           = auto()
    MISTRAL        = auto()
    CUSTOM         = auto()    # Custom endpoint


@dataclass
class LLMConfig:
    """
    A user's LLM configuration for a single provider.
    API keys are stored server-side encrypted; only used server-side.
    """
    id: str
    user_id: str

    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4o"                    # Default model for this provider
    api_key: str = ""                        # Encrypted; never exposed to campaign
    base_url: str = ""                       # For custom endpoints / proxies

    # Generation preferences
    temperature: float = 0.7
    max_tokens: int = 1024

    is_active: bool = True                   # True = use this config
    is_default: bool = True                 # Default provider for this user


@dataclass
class UserLLMSettings:
    """
    Per-user settings for content generation.
    Stored per-user, not per-campaign.
    """
    user_id: str

    # Active configs (user may have multiple providers set up)
    configs: list[LLMConfig] = field(default_factory=list)

    # Preferred generation mode for narrative content
    narrative_mode: GenerationMode = GenerationMode.MANUAL

    # Preferred generation mode for image prompts
    image_mode: GenerationMode = GenerationMode.MANUAL

    # Whether to show LLM suggestions to this user in the DM flow
    show_llm_suggestions: bool = True

    def get_active_config(self) -> Optional[LLMConfig]:
        for cfg in self.configs:
            if cfg.is_active:
                return cfg
        return None