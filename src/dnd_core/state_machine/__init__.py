"""
dnd_core.state_machine — game state management.

game.py   — top-level session state machine (all modes, all entities)
combat.py — combat sub-state machine (initiative, turns, rounds)
events.py — shared CombatEvent dataclass
"""

from dnd_core.state_machine.events import CombatEvent
from dnd_core.state_machine.game import GameMode, GameStateMachine, SessionState, TurnContext
from dnd_core.state_machine.combat import CombatStateMachine, CombatPhase

__all__ = [
    "CombatEvent",
    "CombatPhase",
    "CombatStateMachine",
    "GameMode",
    "GameStateMachine",
    "SessionState",
    "TurnContext",
]


# ─── Dice ──────────────────────────────────────────────────────────────────────

@dataclass
class RollResult:
    """Immutable result of a dice roll. All damage/effects derived from this."""
    expression: str          # e.g. "2d6+3"
    rolls: list[int]         # individual die results
    total: int
    raw_die: int             # just the d20 roll (for advantage/disadvantage)
    modifier: int = 0       # flat modifier added to total

    def to_dict(self) -> dict:
        return {
            "expression": self.expression,
            "rolls":       self.rolls,
            "total":       self.total,
            "modifier":    self.modifier,
        }


@dataclass
class AttackResult:
    """Result of an attack roll vs AC."""
    roll: RollResult
    hit: bool
    crit: bool
    miss: bool
    damage: Optional[RollResult] = None
    narrative: str = ""      # "hits for 14 slashing damage"

    def to_dict(self) -> dict:
        return {
            "hit":    self.hit,
            "crit":   self.crit,
            "miss":   self.miss,
            "roll":   self.roll.to_dict(),
            "damage": self.damage.to_dict() if self.damage else None,
            "narrative": self.narrative,
        }


@dataclass
class SavingThrowResult:
    """Result of a saving throw."""
    roll: RollResult
    dc: int
    success: bool
    failure: bool
    effects_applied: str = ""

    def to_dict(self) -> dict:
        return {
            "dc":     self.dc,
            "success": self.success,
            "failure": self.failure,
            "roll":   self.roll.to_dict(),
        }


# ─── Engine ────────────────────────────────────────────────────────────────────

class GameEngine:
    """
    Deterministic game engine. All mechanical operations go through here.
    Provides structured results suitable for:
      1. Direct state application
      2. LLM prompt construction (doesn't hand raw dice to LLM)
    """

    def __init__(self, combat_sm: Optional[CombatStateMachine] = None) -> None:
        self.combat_sm = combat_sm or CombatStateMachine()

    # ── Dice rolling ───────────────────────────────────────────────────────────

    def roll(self, expression: str) -> RollResult:
        """
        Parse and execute a dice expression.
        Supported: NdX, NdX+M, NdX-M, N (flat).
        e.g. "2d6+3", "1d20+5", "8d6", "1"
        """
        import re
        modifier = 0
        expr = expression.strip()

        m = re.match(r'^(\d+)d(\d+)([+-]\d+)?$', expr)
        if m:
            count = int(m.group(1))
            sides = int(m.group(2))
            modifier = int(m.group(3)) if m.group(3) else 0
            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls) + modifier
        else:
            # Flat roll
            try:
                total = int(expr)
                rolls = [total]
            except ValueError:
                raise ValueError(f"Unknown dice expression: {expression}")

        raw_die = rolls[0] if len(rolls) == 1 else 0  # ambiguous for multi-dice
        return RollResult(
            expression=expr,
            rolls=rolls,
            total=total,
            raw_die=raw_die,
            modifier=modifier,
        )

    def roll_d20(
        self,
        advantage: bool = False,
        disadvantage: bool = False,
        roll_modifier: int = 0,
    ) -> RollResult:
        """
        Roll a d20 with advantage/disadvantage rules.
        Neither applies on a natural 1 or 20 (handled by caller).
        """
        r1 = random.randint(1, 20)
        r2 = random.randint(1, 20)

        if advantage and not disadvantage:
            raw_die = max(r1, r2)
        elif disadvantage and not advantage:
            raw_die = min(r1, r2)
        else:
            raw_die = r1

        total = raw_die + roll_modifier
        rolls = [r1] if raw_die == r1 else [r1, r2]
        return RollResult(
            expression=f"d20{' (adv)' if advantage else ' (dis)' if disadvantage else ''}+{roll_modifier}",
            rolls=rolls,
            total=total,
            raw_die=raw_die,
            modifier=roll_modifier,
        )

    # ── Attack rolls ────────────────────────────────────────────────────────────

    def attack_roll(
        self,
        attacker: Entity,
        target: Entity,
        ability: Ability = Ability.STR,
        attack_modifier: int = 0,
        advantage: bool = False,
        disadvantage: bool = False,
        cover_bonus: int = 0,
    ) -> AttackResult:
        """
        Roll an attack: d20 + attack bonus vs target AC.
        Returns Hit/Miss/Crit info and damage roll if applicable.
        """
        roll = self.roll_d20(
            advantage=advantage,
            disadvantage=disadvantage,
            roll_modifier=attacker.modifier(ability) + attack_modifier,
        )

        natural = roll.raw_die
        crit = natural == 20
        fumble = natural == 1

        # Cover bonus to AC
        target_ac = target.ac + cover_bonus

        if crit:
            hit = True
            miss = False
        elif fumble:
            hit = False
            miss = True
        else:
            hit = roll.total >= target_ac
            miss = roll.total < target_ac

        return AttackResult(
            roll=roll,
            hit=hit,
            crit=crit,
            miss=miss,
            narrative=(
                f"→ {roll.total} vs AC {target_ac}: "
                f"{'CRIT!' if crit else 'HIT' if hit else 'MISS'}"
            ),
        )

    # ── Damage ────────────────────────────────────────────────────────────────

    def apply_damage(
        self,
        target: Entity,
        damage_roll: RollResult,
        damage_type: str,
        source: str,
        crit: bool = False,
    ) -> list[CombatEvent]:
        """
        Apply damage to a target entity.
        If crit=True, double the die rolls before applying.
        Returns events for LLM narration.
        """
        events = []

        actual_rolls = damage_roll.rolls[:]
        if crit and len(actual_rolls) >= 1:
            # Double each die
            actual_rolls = damage_roll.rolls * 2
        total_damage = sum(actual_rolls) + damage_roll.modifier

        target.apply_damage(total_damage)

        events.append(CombatEvent(
            "damage_dealt",
            f"{target.name} takes {total_damage} {damage_type} damage.",
            [target.name],
            data={
                "damage": total_damage,
                "type": damage_type,
                "source": source,
                "crit": crit,
                "target_hp": target.hp,
                "target_hp_max": target.hp_max,
            },
        ))

        if target.hp <= 0 and not target.death_saves.stable:
            events += self._trigger_death_saves(target)

        return events

    def _trigger_death_saves(self, target: Entity) -> list[CombatEvent]:
        events = [CombatEvent(
            "death_save_triggered",
            f"{target.name} falls unconscious! Start death saves.",
            [target.name],
        )]
        target.apply_condition(Condition.UNCONSCIOUS)
        return events

    # ── Saving throws ─────────────────────────────────────────────────────────

    def saving_throw(
        self,
        target: Entity,
        dc: int,
        ability: Ability,
        effect_on_fail: str = "",
        effect_on_success: str = "",
        half_effect_on_success: bool = False,
    ) -> SavingThrowResult:
        """
        Roll a saving throw: d20 + ability modifier vs DC.
        Effects are named strings (e.g. "fire_damage", "prone") —
        actual application is handled by the effects registry.
        """
        roll = self.roll_d20(roll_modifier=target.modifier(ability))
        success = roll.total >= dc
        failure = not success

        result = SavingThrowResult(
            roll=roll,
            dc=dc,
            success=success,
            failure=failure,
            effects_applied=effect_on_success if success else effect_on_fail,
        )

        # Note: caller applies the actual effect after this returns
        return result

    def roll_death_save(self, target: Entity) -> SavingThrowResult:
        """
        Roll a death saving throw (d20, no modifier).
        """
        roll = self.roll_d20()
        result = SavingThrowResult(
            roll=roll,
            dc=10,
            success=roll.total >= 10,
            failure=roll.total < 10,
        )
        target.death_saves.roll_save(roll.raw_die)

        if target.death_saves.stable:
            result.effects_applied = "stabilized"
        if target.death_saves.failures >= 3:
            result.effects_applied = "dead"

        return result

    # ── Ability checks ─────────────────────────────────────────────────────────

    def ability_check(
        self,
        entity: Entity,
        ability: Ability,
        difficulty: int = 10,      # DC
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> RollResult:
        """Roll an ability check (d20 + ability mod)."""
        return self.roll_d20(
            advantage=advantage,
            disadvantage=disadvantage,
            roll_modifier=entity.modifier(ability),
        )

    # ── Exhaustion ───────────────────────────────────────────────────────────

    def apply_exhaustion(self, target: Entity, levels: int = 1) -> list[str]:
        """
        Apply exhaustion levels. Returns list of effect descriptions
        that the LLM can use to narrate each threshold crossed.
        """
        effects = []
        old_level = target.exhaustion
        target.exhaustion = min(target.exhaustion + levels, 6)

        thresholds = {
            1: "You feel a little more fatigued.",
            2: "Your movements feel heavier. Speed halved.",
            3: "Everything is harder. Disadvantage on attacks and saves.",
            4: "Your body is failing. Max HP halved.",
            5: "You can barely move. Speed becomes 0.",
            6: "You collapse.",
        }

        for lvl in range(old_level + 1, target.exhaustion + 1):
            effects.append(thresholds[lvl])

        return effects

    def remove_exhaustion(self, target: Entity, levels: int = 1) -> list[str]:
        """Remove exhaustion levels (e.g. after long rest)."""
        effects = []
        target.exhaustion = max(target.exhaustion - levels, 0)
        if levels > 0:
            effects.append("You feel somewhat refreshed.")
        return effects

    # ── Resting ───────────────────────────────────────────────────────────────

    def short_rest(self, entity: Entity, hit_dice: Optional[list[int]] = None) -> dict:
        """
        Short rest: spend hit dice to recover HP.
        hit_dice: list of die sizes to roll, e.g. [8, 8] for two d8s.
        """
        # Caller provides the hit dice list based on character class
        recovered = 0
        if hit_dice:
            for d in hit_dice:
                recovered += self.roll(f"{d}").total + entity.modifier(Ability.CON)
            entity.heal(recovered)
        return {"hp_recovered": recovered}

    def long_rest(self, entity: Entity) -> dict:
        """
        Long rest: recover HP to max, remove exhaustion level 1,
        recover half of max HP worth of HP, and all spell slots.
        """
        entity.heal(entity.hp_max)
        if entity.exhaustion > 0:
            self.remove_exhaustion(entity, 1)
        return {"hp_at_max": True}

    # ── Spell casting helpers ──────────────────────────────────────────────────

    def use_spell_slot(self, entity: Entity, level: int) -> bool:
        """Attempt to consume a spell slot. Returns True if available."""
        return entity.spell_slots.use(level)

    def has_spell_slot(self, entity: Entity, level: int) -> bool:
        return entity.spell_slots.available(level) > 0

    # ── Concentration ─────────────────────────────────────────────────────────

    def start_concentration(self, entity: Entity, spell_name: str) -> None:
        entity.concentration = spell_name

    def check_concentration(
        self,
        entity: Entity,
        damage: int,
        dc: int = 10,
    ) -> bool:
        """
        Check concentration save when interrupted.
        DC = 10 OR half damage, whichever is higher.
        """
        actual_dc = max(dc, damage // 2)
        result = self.roll_d20(roll_modifier=entity.modifier(Ability.CON))
        success = result.total >= actual_dc
        if not success:
            entity.concentration = None
        return success

    # ── Status / condition helpers ─────────────────────────────────────────────

    def is_incapacitated(self, entity: Entity) -> bool:
        return entity.has_condition(Condition.INCAPACITATED)

    def is_paralyzed(self, entity: Entity) -> bool:
        return entity.has_condition(Condition.PARALYZED)

    def is_stunned(self, entity: Entity) -> bool:
        return entity.has_condition(Condition.STUNNED)

    def can_take_actions(self, entity: Entity) -> bool:
        return (
            entity.is_alive()
            and not self.is_incapacitated(entity)
            and not self.is_paralyzed(entity)
            and not self.is_stunned(entity)
        )