"""
World state — locations, factions, lore, and visited history.
Serialized to JSON / Postgres.

The world is a graph of Locations. Connections between them form the map.
The LLM only reads/writes to this via structured calls — never raw.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional

class LocationType(Enum):
    VILLAGE    = auto()
    TOWN       = auto()
    CITY       = auto()
    DUNGEON    = auto()
    WILDERNESS = auto()
    BUILDING   = auto()
    REGION     = auto()
    PLANE      = auto()
    OTHER      = auto()


class VisitStatus(Enum):
    UNEXPLORED = auto()
    VISITED    = auto()
    EXPLORED   = auto()   # player spent significant time
    HOME_BASE  = auto()


@dataclass
class LocationConnection:
    """A connection between two locations (road, portal, etc.)."""
    from_location_id: str
    to_location_id: str
    travel_method: str = "foot"    # "foot", "horse", "ship", "portal", etc.
    travel_time: str = ""          # "2 hours", "3 days", etc.
    notes: str = ""


@dataclass
class Location:
    id: str
    name: str
    location_type: LocationType
    description: str = ""          # LLM-enhanced lore

    # DM world-building fields
    dm_notes: str = ""            # hidden DM notes (LLM doesn't see this)
    history: str = ""             # in-world history
    current_events: str = ""       # what's happening now

    # Meta
    visit_status: VisitStatus = VisitStatus.UNEXPLORED
    first_visited: Optional[str] = None  # ISO date
    last_visited: Optional[str] = None

    # Relationships
    connected_to: list[str] = field(default_factory=list)  # location IDs
    NPCs_here: list[str] = field(default_factory=list)    # NPC IDs
    encounters: list[str] = field(default_factory=list)   # encounter IDs


# ─── Factions ─────────────────────────────────────────────────────────────────

@dataclass
class Faction:
    id: str
    name: str
    description: str = ""
    alignment: str = ""      # e.g. "Lawful Neutral"
    headquarters: str = ""   # location ID
    leader: str = ""         # NPC ID
    member_npcs: list[str] = field(default_factory=list)   # NPC IDs
    relationships: dict[str, str] = field(default_factory=dict)  # faction_id → "allied", "hostile", etc.
    dm_notes: str = ""


# ─── World State ──────────────────────────────────────────────────────────────

@dataclass
class WorldState:
    """Top-level world container."""
    world_id: str
    name: str
    description: str = ""

    locations: dict[str, Location] = field(default_factory=dict)  # id → Location
    factions: dict[str, Faction] = field(default_factory=dict)    # id → Faction
    connections: list[LocationConnection] = field(default_factory=list)

    # Timeline of major events (DM-controlled history)
    timeline: list[WorldEvent] = field(default_factory=list)

    created_at: str = ""
    updated_at: str = ""

    def add_location(self, location: Location) -> None:
        self.locations[location.id] = location

    def visit_location(self, location_id: str) -> None:
        if location_id in self.locations:
            loc = self.locations[location_id]
            now = datetime.utcnow().isoformat()
            if loc.first_visited is None:
                loc.first_visited = now
            loc.last_visited = now
            if loc.visit_status == VisitStatus.UNEXPLORED:
                loc.visit_status = VisitStatus.VISITED


@dataclass
class WorldEvent:
    """A dated entry on the world timeline."""
    id: str
    date: str                    # in-world calendar date
    title: str
    description: str
    location_id: Optional[str] = None  # where it happened
    factions_involved: list[str] = field(default_factory=list)
    dm_notes: str = ""


# GameSession lives in its own file (imported by campaign.py)