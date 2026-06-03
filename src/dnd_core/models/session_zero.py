"""
Session Zero — the collaborative onboarding workflow before campaign launch.
A series of phases where the group shapes the world together.

Design philosophy:
  - Lead with open-ended, referential questions ("Game of Thrones or The Office?")
  - Players contribute before the DM reveals their skeleton
  - Safety tools come early and use anonymous input where helpful
  - Mechanics/character creation come last
  - All output is editable — nothing is locked in
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class SessionZeroStatus(Enum):
    NOT_STARTED = auto()
    ACTIVE      = auto()
    PAUSED      = auto()
    COMPLETED   = auto()
    CANCELLED   = auto()


class PhaseStatus(Enum):
    PENDING     = auto()
    IN_PROGRESS = auto()
    COMPLETED   = auto()
    SKIPPED     = auto()


class PhaseType(Enum):
    # ── Phase 0: DM-only prep (not shown to players) ──────────────────────
    DM_PREP = auto()          # DM fills out skeleton before inviting players

    # ── Phase 1: World Mood ───────────────────────────────────────────────
    WORLD_MOOD = auto()      # "How do we want this to feel?"

    # ── Phase 2: Setting / World ──────────────────────────────────────────
    SETTING_OVERVIEW = auto()  # Collaborative world shape
    FLAG_PLANTING = auto()    # Optional: players plant backstory flags in world
    MICROSCOPE = auto()       # Optional: collaborative history timeline game

    # ── Phase 3: Group Dynamic ────────────────────────────────────────────
    GROUP_DYNAMIC = auto()    # "What binds this party together?"
    RELATIONSHIP_MAPPING = auto()  # "How does your PC know the others?"

    # ── Phase 4: Character Creation ───────────────────────────────────────
    CHARACTER_CREATION = auto()  # Build and approve sheets within constraints
    BACKSTORY_SHARING = auto()   # Share backstories, react

    # ── Phase 5: Safety & Agreements ─────────────────────────────────────
    COVENANTS = auto()        # Safety tools, table rules
    EXPECTATIONS = auto()     # Scheduling, attendance, communication

    # ── Phase 6: Confirmation ─────────────────────────────────────────────
    CONFIRMATION = auto()     # "Everyone good? Campaign starts."

    # ── Catch-all for DM-defined phases ───────────────────────────────────
    CUSTOM = auto()


# ─── Prompt Templates ──────────────────────────────────────────────────────────
# These are the open-ended / referential questions that drive each phase.
# The DM can accept defaults, edit, or replace entirely.
# Structured as (prompt_text, is_anonymous, note_to_dm) tuples.

PHASE_PROMPTS: dict[PhaseType, list[tuple[str, bool, str]]] = {
    PhaseType.WORLD_MOOD: [
        (
            "What movies, books, or TV shows give you the feeling you want from this campaign? "
            "Give me 2-3 examples — even if they're very different tonally.",
            False,
            "Reference media reveals tone better than abstract descriptors. "
            "Use these to set the visual/audio language for the campaign."
        ),
        (
            "If this campaign were a tone, would it be closer to...\n"
            "  A) Game of Thrones / Dark Souls — consequences are real, death is possible\n"
            "  B) Marvel movies — heroes win, but with real stakes and heart\n"
            "  C) Lord of the Rings — epic, heroic, but ultimately good triumphs\n"
            "  D) The Witcher — morally gray, gritty, but still heroic\n"
            "  E) Conan / pulp sword-and-sorcery — viscerally physical, sex and violence present\n"
            "  F) Something else — tell us what.",
            False,
            "ABCDE options are starting points. 'Something else' opens the best discussions."
        ),
        (
            "What gets you most excited about fantasy RPGs? Choose any that feel right:\n"
            "  🗡️ Combat and dungeon crawls\n"
            "  🌍 Exploring new places and uncovering secrets\n"
            "  🗣️ Deep NPC interactions and social intrigue\n"
            "  📖 Story-driven plots with clear arcs\n"
            "  🎭 Character drama, backstories, and relationships\n"
            "  🧩 Strategic problem-solving\n"
            "  💬 Laughing with friends at the table\n"
            "  🏆 Loot, progression, and character growth",
            False,
            "Shows what players value most. Good for adjusting pacing and spotlight allocation."
        ),
        (
            "What's a moment from a past game (D&D or otherwise) that you'll never forget? "
            "What made it great?",
            False,
            "This reveals what players find meaningful. Often surfaces unspoken expectations."
        ),
    ],

    PhaseType.SETTING_OVERVIEW: [
        (
            "What kind of world are you most excited to explore?\n"
            "  A) Classic high fantasy — elves, dwarves, dragons, familiar D&D tropes\n"
            "  B) Dark and gritty — the world doesn't care about you\n"
            "  C) Weird and alien — strange magic, unfamiliar cultures, things that don't follow normal rules\n"
            "  D) Historical-adjacent — medieval tech, but with real-world cultural richness\n"
            "  E) Urban and modern-adjacent — cities, politics, commerce\n"
            "  F) Something else — describe it",
            False,
            "Helps the DM frame their skeleton and decide how much to reveal in Session Zero."
        ),
        (
            "Any real-world history, mythology, or genre influences you want in this world? "
            "Ancient Rome? Viking sagas? Sengoku Japan? Egyptian mythology?",
            True,  # anonymous — less groupthink on niche interests
            "Write-in. Lets people mention things they'd be embarrassed to advocate for out loud."
        ),
        (
            "Do you want this to feel like a familiar, comfortable world — or a strange new one "
            "where even the rules work differently?",
            False,
            "Frames how alien or familiar the setting should be. Affects world-building scope."
        ),
    ],

    PhaseType.FLAG_PLANTING: [
        (
            "Plant a flag: declare one fact about the world that connects to your character's "
            "backstory. It becomes a real part of the world.\n\n"
            "Example: 'My character is from a port city that was destroyed by a tsunami.' "
            "→ Now that city exists, was destroyed, and your character has history there.",
            True,
            "Anonymous flag planting works best — reduces social pressure to 'compete' with other players."
        ),
    ],

    PhaseType.GROUP_DYNAMIC: [
        (
            "What kind of party dynamic do you want?\n"
            "  A) Tight-knit family — we'd die for each other, we have shared values\n"
            "  B) Reluctant allies — we're here for different reasons but respect each other\n"
            "  C) Professional mercenaries — we're getting paid, that's the only binding\n"
            "  D) Wild cards — we might not all agree, there's room for conflict\n"
            "  E) Something else",
            False,
            "Sets expectations for intra-party conflict. D is only for groups that actively want PvP potential."
        ),
        (
            "Do you want your characters to start with pre-existing connections — "
            "or discover who you are together as the story unfolds?",
            False,
            "Determines whether RELATIONSHIP_MAPPING is rich (pre-connections) or exploratory."
        ),
        (
            "What draws your character to adventure alongside others? "
            "Pick the primary motivation:\n"
            "  💰 Gold and glory\n"
            "  🔮 Purpose — a personal mission drives me\n"
            "  🤝 Loyalty — my friends are here, I'm here for them\n"
            "  ⚔️ Adventure itself — I love the thrill of danger\n"
            "  📜 Knowledge — I seek answers the world doesn't have",
            False,
            "Each player picks one. DM uses these to find group synergy and potential conflicts."
        ),
    ],

    PhaseType.RELATIONSHIP_MAPPING: [
        (
            "For each other PC, write one sentence: 'My character knows [Name] because...'\n"
            "If you don't know them yet, write 'My character is curious about [Name] because...'\n"
            "These are public record — everyone sees all of them.",
            False,
            "Relationship mapping. Creates party cohesion without forcing backstories to match."
        ),
    ],

    PhaseType.CHARACTER_CREATION: [
        (
            "What classes or class archetypes are you interested in? "
            "Don't worry about optimization — tell us what sounds fun and thematic.",
            False,
            "DM collates and checks against CampaignConstraints. Reveals interest clusters."
        ),
        (
            "Any races or species you're especially excited about? "
            "Any you want to see excluded from this campaign?",
            True,
            "Anonymous preference on race/exclusion reduces social pressure to conform."
        ),
        (
            "Do you want to use feats? Multiclassing? Any variant rules from Tasha's/XGtE?",
            False,
            "Mechanics question. DM decides based on group vote and campaign scope."
        ),
        (
            "What's your target level range for this campaign? "
            "(Starting at 1, ending at... 3, 5, 10, 15, 20?)",
            False,
            "Sets scope. Short campaigns (1-5) are very different from epic (15-20)."
        ),
    ],

    PhaseType.BACKSTORY_SHARING: [
        (
            "Share your backstory. Read it aloud or summarize — however you're comfortable. "
            "The rest of us will react: what we find interesting, what questions we have, "
            "and how your past might connect to ours.",
            False,
            "Backstories shared aloud. Players react in-turn. DM facilitates connections."
        ),
        (
            "Each PC has one secret only they know. Write it down privately — "
            "give it to the DM. It will come up in play.",
            True,
            "Private secrets. DM holds until relevant. Creates dramatic irony and future hooks."
        ),
    ],

    PhaseType.COVENANTS: [
        (
            "Before we discuss content, does anyone want to privately write down any topics "
            "they are not comfortable with? These will be read aloud by the DM and grouped "
            "into LINES (never appear) and VEILS (fade to black, off-screen only).\n\n"
            "Nobody needs to justify why. If you write it, it's a line.",
            True,  # anonymous — critical for safety
            "Anonymous input first. Then DM reads aloud and categorizes: Lines vs Veils. "
            "This is the most important phase for player comfort."
        ),
        (
            "When the table gets uncomfortable with a topic or moment in-session, "
            "how do you want to handle it?\n"
            "  A) X-Card — tap the card, we skip/rewind, no questions asked\n"
            "  B) Open Door — anyone can step out anytime, no explanation needed\n"
            "  C) Script Change — rate intensity 0-10, we adjust in the moment\n"
            "  D) Just say the word — casual check-in, 'hey can we skip that?'\n"
            "  E) All of the above",
            False,
            "Choose safety tools as a group. E is the recommended default for most groups."
        ),
        (
            "Any table rules we should establish?\n"
            "Examples: no PvP without consent, flanking rules, milestone vs XP leveling, "
            "no rolling stats — point buy or array, device policy, late policy...",
            False,
            "Open write-in. DM proposes their own house rules here too."
        ),
    ],

    PhaseType.EXPECTATIONS: [
        (
            "When and how often do we play? What day, what time, how long? "
            "What's our policy if someone can't make a session?",
            False,
            "Scheduling. Set explicit expectations. Include 'what if we lose a player mid-arc?'"
        ),
        (
            "How do we communicate between sessions? Group chat? Email? "
            "Any topics that shouldn't go in the group chat?",
            False,
            "Out-of-game communication norms. Also: who posts the recap?"
        ),
    ],

    PhaseType.CONFIRMATION: [
        (
            "Before we start — any last concerns, questions, or things you want to change? "
            "This is the last off-ramp before the campaign begins.",
            False,
            "Final check-in. Requires all participants to explicitly confirm. "
            "Anyone who doesn't confirm isn't ready — DM follows up privately."
        ),
        (
            "The campaign is called '[title]'. "
            "The DM's one-line pitch is '[elevator_pitch]'. "
            "We're playing in a [tone] world with [pacing] pacing. "
            "Player characters start at level [level]. "
            "Do I have that right?",
            False,
            "DM reads the summary aloud. Players confirm or correct. "
            "This is the contract moment."
        ),
    ],
}


# ─── Safety Tool Models ────────────────────────────────────────────────────────

@dataclass
class SafetyLine:
    """A hard topic boundary — this content never appears."""
    content: str           # e.g. "no harm to children"
    id: str = ""           # auto-generated
    source: str = ""       # participant_id who set it


@dataclass
class SafetyVeil:
    """A fade-to-black topic — it exists but is never described in detail."""
    content: str           # e.g. "torture happens off-screen"
    id: str = ""
    source: str = ""


@dataclass
class SafetySettings:
    """Safety configuration for the campaign."""
    lines: list[SafetyLine] = field(default_factory=list)
    veils: list[SafetyVeil] = field(default_factory=list)

    x_card_enabled: bool = True
    open_door_enabled: bool = True
    script_change_enabled: bool = False

    def add_line(self, content: str, source: str = "") -> SafetyLine:
        line = SafetyLine(content=content, source=source)
        self.lines.append(line)
        return line

    def add_veil(self, content: str, source: str = "") -> SafetyVeil:
        veil = SafetyVeil(content=content, source=source)
        self.veils.append(veil)
        return veil


# ─── Participant Response ─────────────────────────────────────────────────────

@dataclass
class ParticipantResponse:
    """One person's response to a phase prompt."""
    id: str
    participant_id: str
    role: str                    # "dm", "player"
    content: str                 # What was written/said
    prompt_index: int = 0         # Which prompt this responds to (index into PHASE_PROMPTS)
    upvotes: list[str] = field(default_factory=list)   # participant_ids who upvoted
    is_approved: bool = False   # DM marked as accepted into resolved_content
    timestamp: str = ""
    is_anonymous: bool = False


# ─── Session Zero Phase ────────────────────────────────────────────────────────

@dataclass
class SessionZeroPhase:
    """
    One discrete step in the Session Zero workflow.
    input_template: the prompt shown to participants
    prompt_topic: short label for display
    prompts: list of (question_text, is_anonymous, dm_note) tuples
    """
    phase_type: PhaseType
    sort_order: int

    status: PhaseStatus = PhaseStatus.PENDING
    moderator: str = "dm"        # "dm" or "group"

    # Display / labeling
    prompt_topic: str = ""       # Short: "World Tone", "Safety", etc.
    input_template: str = ""     # Legacy single prompt (used if no prompts defined)

    # Multi-prompt support
    prompts: list[tuple[str, bool, str]] = field(default_factory=list)
    current_prompt_index: int = 0

    # Responses collected for this phase
    responses: list[ParticipantResponse] = field(default_factory=list)

    # Final agreed version after discussion
    resolved_content: str = ""

    is_required: bool = True
    is_skippable: bool = False

    # Safety settings (Phase 5 only)
    safety: Optional[SafetySettings] = None

    # Optional arc tag hint for content from this phase
    arc_tag_hint: str = ""

    # ─── Prompt helpers ───────────────────────────────────────────────────

    def get_current_prompt(self) -> tuple[str, bool, str] | None:
        """Return (question_text, is_anonymous, dm_note) for current prompt."""
        if self.prompts and 0 <= self.current_prompt_index < len(self.prompts):
            return self.prompts[self.current_prompt_index]
        return None

    def advance_prompt(self) -> bool:
        """Move to next prompt in phase. Returns True if more remain."""
        if self.current_prompt_index < len(self.prompts) - 1:
            self.current_prompt_index += 1
            return True
        return False

    def load_default_prompts(self) -> None:
        """Load the standard prompts for this phase type from PHASE_PROMPTS."""
        if self.phase_type in PHASE_PROMPTS:
            self.prompts = list(PHASE_PROMPTS[self.phase_type])

    # ─── Response helpers ──────────────────────────────────────────────────

    def get_anonymous_responses(self) -> list[ParticipantResponse]:
        return [r for r in self.responses if r.is_anonymous]

    def get_named_responses(self) -> list[ParticipantResponse]:
        return [r for r in self.responses if not r.is_anonymous]

    def approve_response(self, response_id: str) -> None:
        for r in self.responses:
            if r.id == response_id:
                r.is_approved = True


# ─── Participant ───────────────────────────────────────────────────────────────

@dataclass
class Participant:
    """Someone invited to the Session Zero."""
    id: str
    user_id: str              # The actual user account
    role: str                 # "dm" or "player"
    name: str = ""            # Display name
    joined_at: str = ""
    is_ready: bool = False    # Confirmed they're done with their phase
    is_confirmed: bool = False  # Final confirmation at end


# ─── Session Zero ────────────────────────────────────────────────────────────────

@dataclass
class SessionZero:
    """
    The active Session Zero workflow instance.
    One per CampaignSetup. Dies when the campaign launches.
    """
    id: str
    campaign_setup_id: str
    dm_id: str

    phases: list[SessionZeroPhase] = field(default_factory=list)
    current_phase_index: int = 0
    participants: list[Participant] = field(default_factory=list)

    status: SessionZeroStatus = SessionZeroStatus.NOT_STARTED

    # Safety settings (shared across phases)
    safety: SafetySettings = field(default_factory=SafetySettings)

    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # ─── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def create_default(cls, campaign_setup_id: str, dm_id: str) -> "SessionZero":
        """
        Build a standard Session Zero with all phases and default prompts.
        DM can remove/skip/reorder phases before starting.
        """
        all_phase_types = [
            PhaseType.WORLD_MOOD,
            PhaseType.SETTING_OVERVIEW,
            PhaseType.FLAG_PLANTING,     # Optional
            PhaseType.GROUP_DYNAMIC,
            PhaseType.RELATIONSHIP_MAPPING,
            PhaseType.CHARACTER_CREATION,
            PhaseType.BACKSTORY_SHARING,
            PhaseType.COVENANTS,
            PhaseType.EXPECTATIONS,
            PhaseType.CONFIRMATION,
        ]

        phases = []
        for i, pt in enumerate(all_phase_types):
            phase = SessionZeroPhase(
                phase_type=pt,
                sort_order=i,
                prompt_topic=_phase_topic(pt),
            )
            phase.load_default_prompts()
            phases.append(phase)

        return cls(
            id=str(id),
            campaign_setup_id=campaign_setup_id,
            dm_id=dm_id,
            phases=phases,
            current_phase_index=0,
            participants=[],
            status=SessionZeroStatus.NOT_STARTED,
            safety=SafetySettings(),
            started_at=None,
            completed_at=None,
        )

    # ─── Phase navigation ─────────────────────────────────────────────────

    def current_phase(self) -> Optional[SessionZeroPhase]:
        if 0 <= self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index]
        return None

    def phase_by_type(self, phase_type: PhaseType) -> Optional[SessionZeroPhase]:
        for p in self.phases:
            if p.phase_type == phase_type:
                return p
        return None

    def advance_phase(self) -> None:
        """Move to next phase."""
        if self.current_phase_index < len(self.phases) - 1:
            self.current_phase_index += 1
        else:
            self.status = SessionZeroStatus.COMPLETED

    def is_complete(self) -> bool:
        return all(p.status == PhaseStatus.COMPLETED or p.is_skippable
                   for p in self.phases)


def _phase_topic(pt: PhaseType) -> str:
    return {
        PhaseType.WORLD_MOOD: "World Mood & Tone",
        PhaseType.SETTING_OVERVIEW: "Setting & World",
        PhaseType.FLAG_PLANTING: "World Flags",
        PhaseType.MICROSCOPE: "Microscope History Game",
        PhaseType.GROUP_DYNAMIC: "Party Dynamic",
        PhaseType.RELATIONSHIP_MAPPING: "Relationships",
        PhaseType.CHARACTER_CREATION: "Character Creation",
        PhaseType.BACKSTORY_SHARING: "Backstory Sharing",
        PhaseType.COVENANTS: "Safety & Table Rules",
        PhaseType.EXPECTATIONS: "Expectations & Scheduling",
        PhaseType.CONFIRMATION: "Final Confirmation",
        PhaseType.DM_PREP: "DM Prep",
        PhaseType.CUSTOM: "Custom",
    }.get(pt, str(pt.name))