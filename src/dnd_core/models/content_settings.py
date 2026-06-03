"""
Content generation settings — who generates narrative and when.
Two independent axes:
  1. What gets logged (campaign-global breadcrumb log level)
  2. Who writes the narrative (per-user contribution mode)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class GenerationMode(Enum):
    """
    Who provides the content for a given field.
    """
    MANUAL    = auto()  # User types it themselves
    LLM_AUTO  = auto()  # LLM generates silently, no prompt
    LLM_ASK   = auto()  # LLM suggests, user approves/rejects/edits
    USER_FILL = auto()  # Prompt user to fill, but don't block


class BreadcrumbLogLevel(Enum):
    """
    Campaign-global: what events create breadcrumbs.
    Like log levels — each tier includes the ones above it.
    """
    OFF       = auto()  # No automatic breadcrumbs at all
    MAJOR_ONLY = auto() # Only MAJOR significance (arc conclusions, deaths)
    NOTABLE   = auto()  # MAJOR + NOTABLE (good default)
    VERBOSE   = auto()  # MAJOR + NOTABLE + MINOR (everything)


@dataclass
class ContentSettings:
    """
    Global content generation settings for a campaign.
    These are defaults — individual users can override their own
    narrative contribution mode.
    """
    # Breadcrumb log level (campaign-wide)
    breadcrumb_log_level: BreadcrumbLogLevel = BreadcrumbLogLevel.NOTABLE

    # Default narrative contribution mode for DM
    dm_narrative_mode: GenerationMode = GenerationMode.MANUAL

    # Default narrative contribution mode for players
    player_narrative_mode: GenerationMode = GenerationMode.MANUAL

    # Image generation defaults
    dm_image_mode: GenerationMode = GenerationMode.MANUAL
    player_image_mode: GenerationMode = GenerationMode.MANUAL

    @classmethod
    def default(cls) -> "ContentSettings":
        return cls()