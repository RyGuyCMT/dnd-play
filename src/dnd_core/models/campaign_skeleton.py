"""
Campaign skeleton — DM's pre-created world scaffolding (optional).
Plot hooks, NPCs, factions, locations, maps — all planned before play starts.
This is the PLAN. Breadcrumbs track what actually happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlotPoint:
    """A plot hook or story beat the DM has planned."""
    id: str
    title: str
    description: str
    arc_tag: str = ""                       # "The Dragon Arc", etc.
    is_major: bool = True
    is_secret: bool = False                 # hidden from players
    dm_notes: str = ""
    # What must be true for this to trigger (conditions, NPC death, etc.)
    trigger_conditions: list[str] = field(default_factory=list)


@dataclass
class CampaignSkeleton:
    """
    Optional world scaffolding created by DM before Session Zero.
    All of this is PLANNED — it becomes breadcrumbs only when the party
    actually experiences it.
    """
    # Narrative scaffolding
    plot_hooks: list[PlotPoint] = field(default_factory=list)
    major_plot_points: list[PlotPoint] = field(default_factory=list)
    minor_plot_points: list[PlotPoint] = field(default_factory=list)

    # Pre-defined world elements (DM can populate these before launch)
    pre_defined_npc_ids: list[str] = field(default_factory=list)   # NPC IDs created separately
    pre_defined_location_ids: list[str] = field(default_factory=list)
    pre_defined_faction_ids: list[str] = field(default_factory=list)
    pre_defined_map_refs: list[str] = field(default_factory=list)   # e.g. URLs or file paths

    # Campaign premise (shown during Session Zero)
    premise: str = ""
    suggested_opening_hook: str = ""

    # DM's private notes on overall plan
    dm_master_plan: str = ""