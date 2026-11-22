"""Local/offline Fate hints for Path of Exile 1, Covens of Umbra (3.30).

Heuristic priorities only. In-game reward ICONS and set completion take precedence.
No access to the game process or game files.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re

# Subjective danger ratings for a moving bow/DoT Pathfinder. 1=easy, 5=hard.
DANGER = {
    "Crowkeeper": 3, "Sanguine": 4, "Incandescent": 3, "Rot": 3, "Rotted": 3,
    "Dryad": 2, "Deathbringer": 4, "Torchbearer": 3, "Bloodthirsty": 4,
    "Wildfire": 2, "Murderous": 3, "Gravewalker": 3, "Houndmaster": 5,
    "Black Frost": 4, "Conjurer": 4, "Golemancer": 3, "Doomsayer": 2,
    "Avalanche": 5, "Butcher": 3, "Alchemist": 4, "Stormcaller": 3,
    "Tempest": 3, "Blood Moon": 3, "Savage": 4, "Pestilent": 4,
    "Sadist": 4,
}
FATE_NAMES = sorted(DANGER)

# Keywords for *textual/manual* reward notes. Screenshots must be inspected by vision;
# plain Fate names alone cannot reveal the actual randomized rewards.
REWARD_KEYWORDS = [
    (("exceptional gem", "aussergewöhn", "außergewöhn", "empower support", "enlighten support", "enhance support"), 15, "Exceptional Gem"),
    (("mirror shard", "spiegelscherbe", "hinekora"), 18, "Seltene High-End-Currency"),
    (("divine orb", "göttliche kugel", "fracturing", "fracture orb"), 12, "Wertvolle Currency"),
    (("viscera", "eingeweide"), 11, "Viscera"),
    (("jewel", "juwel"), 6, "Jewel"),
    (("unique", "einzigartig"), 4, "Unique"),
    (("quality gem", "qualitätsgem", "qualität gem"), 5, "Gems mit Qualität"),
    (("rare bow", "seltener bogen", "bogen", "quiver", "köcher", "boots", "stiefel", "resist", "life"), 5, "Leveling-Gear"),
    (("rare armour", "rare armor", "seltene rüstung", "seltene ruestung", "rüstung", "ruestung"), 3, "Seltene Rüstung (Slot offen)"),
    (("rare helmet", "seltener helm", "rare helm", "helm"), 4, "Seltener Helm nur bei explizitem Beleg"),

    (("thread", "faden"), 4, "Threads"),
    (("stacked deck", "kartendeck", "set"), 5, "Set/Decks"),
    (("currency", "währung", "währungsgegenstände", "gold", "maps", "map", "karte"), 3, "Currency/Maps/Gold"),
]

@dataclass
class Fate:
    name: str
    rewards: str = ""

@dataclass
class RatedFate:
    name: str
    score: float
    danger: int
    summary: str
    rewards: str


def score_fate(fate: Fate, prior: list[Fate] | None = None, phase: str = "Kampagne",
               goal: str = "Ausgewogen") -> RatedFate:
    """Explainable estimate from manually typed rewards, build and prior selections."""
    prior = prior or []
    name = fate.name.strip()
    danger = DANGER.get(name, 3)
    score = 20.0 - danger * (6.0 if goal == "Sicher" else 3.5)
    why = [f"geschätztes Risiko {danger}/5"]
    words = fate.rewards.lower().strip()
    best_reward, label = 0, ""
    for keys, points, desc in REWARD_KEYWORDS:
        if any(re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", words) for k in keys) and points > best_reward:
            best_reward, label = points, desc
    if words:
        mult = 1.5 if goal == "Loot" else 1.1
        if phase == "Kampagne" and label in {"Leveling-Gear", "Seltener Helm nur bei explizitem Beleg", "Seltene Rüstung (Slot offen)"}:
            mult *= 2
        if phase == "Kampagne" and label in {"Exceptional Gem", "Viscera"}:
            mult *= 0.6
        score += best_reward * mult
        if label:
            why.append(f"Belohnung: {label}")
        else:
            why.append("Belohnung nicht zuverlässig bewertet")
        if any(k in words for k in ("rare wand", "seltener zauberstab", "rare axe", "seltene axt",
                                     "rare axes", "seltene äxte")) and not label:
            score -= 2
            why.append("Waffentyp für Toxic Rain kaum nützlich")
    else:
        why.append("keine Belohnung angegeben – nur Risikobewertung")
    matches = [p for p in prior if p.name.casefold() == name.casefold() and name]
    if matches:
        # As of 3.30.0b Hotfix 3 the first and third copies triple their own
        # rewards; copy 2's own rewards are ignored. We cannot value unknown icons.
        if len(matches) == 1:
            # Höherer Loot-Ertrag, aber auch stärkere Bossmechanik.
            # Ohne genaue Reward-Symbole darf die Kombination NICHT
            # automatisch mit 9/10 als sicher empfohlen werden.
            duplicate_bonus = 2 if goal == "Sicher" else 8 if goal == "Ausgewogen" else 12
            score += duplicate_bonus
            why.append("Duplikat: 3× Belohnung der ersten Karte (zweite entfällt), aber stärkerer Boss")
        elif len(matches) == 2:
            score += 4 if goal == "Sicher" else 8
            why.append("dritte Kopie: mögliche weitere 3× Belohnung; höheres Risiko")
    if goal == "Viscera" and name in {"Savage", "Pestilent", "Sadist"}:
        score += 7
        why.append("zusätzlicher Boss mit eigener Viscera-Chance")
    return RatedFate(name=name, score=round(score, 1), danger=danger,
                     summary=" · ".join(why), rewards=fate.rewards)


def rank_fates(fates: list[Fate], prior: list[Fate] | None = None,
               phase: str = "Kampagne", goal: str = "Ausgewogen") -> list[RatedFate]:
    return sorted((score_fate(f, prior, phase, goal) for f in fates if f.name.strip()),
                  key=lambda f: f.score, reverse=True)
