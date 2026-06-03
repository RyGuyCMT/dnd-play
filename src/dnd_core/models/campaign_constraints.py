"""
Campaign constraints — what rules/materials are allowed in this campaign.
Screens character creation, spell selection, feat choices, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Sourcebook(Enum):
    PHB  = "Player's Handbook"
    XGtE = "Xanathar's Guide to Everything"
    TCoE = "Tasha's Cauldron of Everything"
    VGM  = "Volo's Guide to Monsters"
    MM   = "Monster Manual"
    DMG  = "Dungeon Master's Guide"
    AI   = "Acquisitions Incorporated"
    ERftLW = "Eberron: Races of Eberron"
    WGtE = "Wayfinder's Guide to Eberron"
    MTOF = "Mordenkainen's Tome of Foes"
    EGtW = "Explorer's Guide to Wildemount"
    SCC  = "Spelljammer: Cosmic Adventures"
    # Add others as needed
    HOMEBREW = "homebrew"


class VariantRule(Enum):
    FEATS                    = auto()
    MULTICLASSING            = auto()
    XGtE_VARIANT_CLASS_FEATS = auto()
    TCoE_CLASS_VARIANTS      = auto()
    CUSTOM_BG                = auto()
    FLOATING_ASIs            = auto()


@dataclass
class CampaignConstraints:
    """
    What content is allowed in this campaign.
    Empty lists = all are allowed.
    """
    allowed_races: list[str] = field(default_factory=list)
    allowed_classes: list[str] = field(default_factory=list)
    allowed_sourcebooks: list[Sourcebook] = field(default_factory=list)
    allowed_spells: list[str] = field(default_factory=list)  # empty = all
    allowed_feats: list[str] = field(default_factory=list)   # empty = all
    allowed_subsclasses: list[str] = field(default_factory=list)  # empty = all
    max_level: int = 20
    variant_rules: list[VariantRule] = field(default_factory=list)

    def race_allowed(self, race: str) -> bool:
        return not self.allowed_races or race in self.allowed_races

    def class_allowed(self, class_name: str) -> bool:
        return not self.allowed_classes or class_name in self.allowed_classes

    def spell_allowed(self, spell_name: str) -> bool:
        return not self.allowed_spells or spell_name in self.allowed_spells

    def feat_allowed(self, feat: str) -> bool:
        return not self.allowed_feats or feat in self.allowed_feats

    def subclass_allowed(self, subclass: str) -> bool:
        return not self.allowed_subsclasses or subclass in self.allowed_subsclasses