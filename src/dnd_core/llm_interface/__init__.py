"""
llm_interface — LLM-facing gateway for DM and narration.

The LLM never directly reads or writes game state.
Instead, it receives structured prompts + events and returns structured responses
which the interface validates and routes to the engine.

Separation of concerns:
  - Engine  →  pure mechanics (damage, saves, initiative)
  - State   →  pure state (who has what HP, where are they)
  - LLM IF  →  narrative generation + "what do I describe?" decisions
"""

from dnd_core.llm_interface.interfaces import DMInterface, PlayerInterface, PlayerViewSession
from dnd_core.llm_interface.narrator import Narrator

__all__ = [
    "DMInterface",
    "Narrator",
    "PlayerInterface",
    "PlayerViewSession",
]