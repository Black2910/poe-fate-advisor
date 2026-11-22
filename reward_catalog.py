"""PoE 3.30.0c Covens of Umbra: loot reward TYPES, not Fate-name assignments.

Source: https://poedb.tw/us/Fates (Rewards section, checked 2026-11-22).
Patch: https://www.pathofexile.com/forum/view-thread/ (3.30.0c)

Loot is rolled per individual Fate card, NOT determined by Fate name.
A tiny icon can only suggest a type; an in-game tooltip is the source of truth.
"""
from __future__ import annotations
import re

# Image identifiers from PoEDB's Augury reward icon catalog. Categories may
# represent multiple rewards/tiers; an icon alone NEVER proves an exact drop.
REWARD_ICONS = {
    "UniqueWeapon": "einzigartige Waffe",
    "UniqueArmour": "einzigartige Rüstung",
    "UniqueJewellery": "einzigartiger Schmuck",
    "UniqueJewel": "einzigartiges Juwel",
    "UniqueFlask": "einzigartige Flasche",
    "UniqueAuguryItem": "spezielles Coven-Unique",
    "Gems": "Gems (ggf. Qualität)",
    "ExceptionalGems": "außergewöhnliches Gem",
    "IncreasedRarityAffectedMonster": "erhöhte Gegenstands-Seltenheit des Bosses",
    "Currency": "zusätzliche Währungsgegenstände",
    "MirrorShard": "Spiegelscherbe",
    "FracturingOrb": "Fracturing Orb",
    "DivineOrb": "Divine Orb",
    "AnnulmentOrb": "Orb of Annulment",
    "ReflectiveMist": "Reflecting Mist",
    "HinekorasLock": "Hinekora's Lock",
    "SacredOrb": "Sacred Orb",
    "Viscera": "Viscera",
    "Threads": "Threads",
    "Divination": "Stacked Decks",
    "Gold": "Gold",
    "Maps": "Maps",
    "Boots": "seltene Stiefel",
    "Helmet": "seltener Helm",
    "BodyArmour": "seltene Körperrüstung",
    "Gloves": "seltene Handschuhe",
    "Shield": "RareShields – seltene Schilde",
    "Quiver": "seltener Köcher",
    "RareWeapon": "Nahkampfwaffen/allgemeine Waffen",
    "Ring": "seltene Ringe",
    "Amulet": "seltene Amulette",
    "Belt": "seltene Gürtel",
    "Axe": "seltene Äxte",
    "Bow": "seltene Bögen",
    "Claw": "seltene Klauen",
    "Dagger": "seltene Dolche",
    "FishingRod": "seltene Angelrute",
    "Mace": "seltene Streitkolben",
    "Sceptre": "seltene Zepter",
    "Staff": "seltene Stäbe/Kampfstabe",
    "Wand": "seltene Zauberstäbe",
    "Sword": "seltene Schwerter",
    "RareRanged": "Fernkampfwaffen oder Köcher",
    "RareArmour": "Rüstungsgegenstände (genauer Slot unbekannt)",
    "RareJewellery": "Schmuckgegenstände (genauer Slot unbekannt)",
}

# The visible gold pile icon in the user's screenshot = Currency.
# The blue/black armour silhouette = generic RareArmour, NOT a helmet.
# These are reference labels, never tie them to Fate names.
VISIBLE_ICON_EXAMPLES = {
    "goldene Münz-/Währungssymbole": "Currency",
    "blau-schwarze Rüstungssilhouette": "RareArmour",
    "drei bläuliche Pfeilspitzen": "RareRanged",
}

# Patterns are matched against the ENGLISH textual tooltip, which has priority.
# Most specific first; avoid matching 'empower' inside 'Empowered Monster'.
PATTERNS = [
    (r"\bmirror shard\b", "Spiegelscherbe"),
    (r"\bhinekora['’]s lock\b", "Hinekora's Lock"),
    (r"\bfracturing orb\b", "Fracturing Orb"),
    (r"\bdivine orbs?\b", "Divine Orb(s)"),
    (r"\borbs? of annulment\b", "Orb(s) of Annulment"),
    (r"\breflecting mist\b", "Reflecting Mist"),
    (r"\bsacred orb\b", "Sacred Orb"),
    (r"\bdreadmaidens['’] sacrament\b|\bhide of the vendigo\b|\bcorpse rose\b|\bordered fate\b|\bdoedre['’]s tongue\b", "spezifisches Coven-Unique"),
    (r"\bexceptional gems?\b", "außergewöhnliches Gem"),
    (r"\b(viscera)\b", "Viscera"),
    (r"\bstacked decks?\b", "Stacked Decks"),
    (r"\bthreads?\b", "Threads"),
    (r"\bcurrency items?\b|\bvaluable currency\b", "zusätzliche Währungsgegenstände"),
    (r"\b(?:item )?rarity\b", "erhöhte Gegenstands-Seltenheit"),
    (r"\bunique jewellery\b", "einzigartiger Schmuck"),
    (r"\bunique jewels?\b", "einzigartiges Juwel"),
    (r"\bunique flasks?\b", "einzigartige Flasche"),
    (r"\bunique armou?r\b", "einzigartige Rüstung"),
    (r"\bunique weapons?\b", "einzigartige Waffe"),
    (r"\b(?:gems? with (?:maximum )?quality|gems?, some of which|quality gems?)\b", "Gems mit Qualität"),
    (r"\bskill gems?\b|\bsupport gems?\b|\badditional gems?\b", "Gems"),
    (r"\branged weapons? or quivers?\b", "Fernkampfwaffen oder Köcher"),
    (r"\bmelee weapons?\b", "Nahkampfwaffen"),
    (r"\barmou?r items? with (?:strength|dexterity|intelligence) requirements?\b", "Rüstungsgegenstände (Attribut-Anforderung)"),
    (r"\bjewell?ery items?\b", "Schmuckgegenstände"),
    (r"\b(?:rare )?quivers?\b", "Köcher"),
    (r"\b(?:rare )?boots?\b", "Stiefel"),
    (r"\b(?:rare )?helmets?\b", "Helme"),
    (r"\b(?:rare )?body armou?rs?\b", "Körperrüstungen"),
    (r"\b(?:rare )?gloves?\b", "Handschuhe"),
    (r"\b(?:rare )?shields?\b", "Schilde"),
    (r"\b(?:rare )?rings?\b", "Ringe"),
    (r"\b(?:rare )?amulets?\b", "Amulette"),
    (r"\b(?:rare )?belts?\b", "Gürtel"),
    (r"\b(?:rare )?bows?\b", "Bögen"),
    (r"\b(?:rare )?axes?\b", "Äxte"),
    (r"\b(?:rare )?claws?\b", "Klauen"),
    (r"\b(?:rare )?(?:rune )?daggers?\b", "Dolche"),
    (r"\b(?:rare )?fishing rods?\b", "Angelruten"),
    (r"\b(?:rare )?maces?\b", "Streitkolben"),
    (r"\b(?:rare )?sceptres?\b", "Zepter"),
    (r"\b(?:rare )?(?:war)?staves\b", "Stäbe"),
    (r"\b(?:rare )?wands?\b", "Zauberstäbe"),
    (r"\b(?:rare )?swords?\b", "Schwerter"),
    (r"\b(?:rare )?weapons?\b", "Waffen"),
    (r"\b(?:rare )?maps?\b", "Maps"),
    (r"\bgold\b", "Gold"),
]

MODIFIERS = {
    "speed": "Tempo", "resistance": "Resistenzen", "life": "Leben",
    "defence": "Verteidigung", "physical": "physisch", "critical": "kritisch",
    "attack": "Angriff", "elemental": "elementar", "chaos": "Chaos",
    "mana": "Mana", "gem": "Gem", "damage": "Schaden",
    "attribute": "Attribute", "drop": "Drops", "angling": "Angeln",
}


def classify_tooltip(text: str) -> str | None:
    """Turn a VERIFIED, transcribed visible loot tooltip into a category/bonus.

    None means the text cannot be classified, never silently guess a Fate loot.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    src = " ".join(text.lower().split())
    match_label = next((label for pattern, label in PATTERNS if re.search(pattern, src, flags=re.I)), None)
    if not match_label:
        return None
    # Preserve impactful qualifiers instead of flattening different rewards.
    if "chance to drop" in src:
        prefix = "Chance auf "
    elif "will drop" in src or "drop an additional" in src:
        prefix = "Zusätzlich: " if not match_label.startswith("zusätzliche") else ""
    elif "item rarity" in src:
        prefix = "Boss-Bonus: "
    else:
        prefix = ""
    details = []
    if "valuable" in src:
        details.append("wertvoll")
    if "many additional" in src or "hoards of" in src:
        details.append("viele")
    if "no " in src and " modifiers" in src:
        for en, de in MODIFIERS.items():
            if f"no {en} modifiers" in src:
                details.append(f"ohne {de}-Mods")
                break
    else:
        for en, de in MODIFIERS.items():
            if re.search(rf"\b(?:a|an) {en} modifier\b", src):
                details.append(f"mit {de}-Mod")
                break
    suffix = f" ({', '.join(details)})" if details else ""
    return f"{prefix}{match_label}{suffix}"


def icon_label(icon_id: str) -> str | None:
    """Validate an exact PoEDB icon identifier (not a guessed natural-language name)."""
    if not isinstance(icon_id, str):
        return None
    icon_id = icon_id.replace("AuguryRewardIcon", "")
    return REWARD_ICONS.get(icon_id)


def icon_legend() -> str:
    return "; ".join(f"{key}={value}" for key, value in REWARD_ICONS.items())
