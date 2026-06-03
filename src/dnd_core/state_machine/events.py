"""
Shared event primitives. Avoids circular imports between state_machine and engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CombatEvent:
    """
    A single mechanical event that occurred.
    The LLM receives these as structured prompts for narration.
    """
    kind: str                 # "damage_dealt", "turn_start", "spell_cast", etc.
    narrative: str            # terse mechanical description for LLM to flesh out
    entities: list[str]       # entity names involved
    # Raw mechanical data for the LLM to use in description:
    data: dict = field(default_factory=dict)

    def to_llm_prompt(self) -> str:
        return (
            f"[EVENT: {self.kind}]\n"
            f"Narrative: {self.narrative}\n"
            f"Entities: {', '.join(self.entities)}\n"
        )