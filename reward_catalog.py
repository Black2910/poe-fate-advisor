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


# ---- Reward variants (v1.3.3): bundled in legacy-approved module ----
from dataclasses import dataclass

ALIASES = {
    'RareShields': 'Shield', 'RareShield': 'Shield', 'RareArmourItems': 'RareArmour',
    'RareArmourStrength': 'RareArmour', 'RareArmourDexterity': 'RareArmour',
    'RareArmourIntelligence': 'RareArmour',
    'RareHelmets': 'Helmet', 'RareBodyArmours': 'BodyArmour',
    'RareGloves': 'Gloves', 'RareBoots': 'Boots',
    'RareWands': 'Wand', 'RareAxes': 'Axe', 'RareBows': 'Bow',
    'RareRings': 'Ring', 'RareAmulets': 'Amulet',
}


def normalise_icon_id(name: str) -> str:
    name = str(name or '').replace('AuguryRewardIcon', '').strip()
    return ALIASES.get(name, name)


@dataclass(frozen=True)
class RewardVariant:
    variant_id: str
    icon_id: str
    label_de: str
    tooltip_en: str


_VARIANTS: list[RewardVariant] = []


def add(icon: str, slug: str, german: str, tooltip: str) -> None:
    if icon not in REWARD_ICONS:
        raise ValueError(f'Unknown icon {icon}')
    _VARIANTS.append(RewardVariant(f'{icon}.{slug}', icon, german, tooltip))


# Shared iconic rewards: the variant usually changes loot amount/quality, not art.
for icon, lines in {
    'UniqueWeapon': [('Normal','einzigartige Waffe','an additional Unique Weapon'), ('Valuable','wertvolle einzigartige Waffe','an additional Valuable Unique Weapon')],
    'UniqueArmour': [('Normal','einzigartige Rüstung','an additional Unique Armour'), ('Valuable','wertvolle einzigartige Rüstung','an additional Valuable Unique Armour')],
    'UniqueJewellery': [('Normal','einzigartiger Schmuck','an additional Unique Jewellery Item'), ('Valuable','wertvoller einzigartiger Schmuck','an additional Valuable Unique Jewellery Item')],
    'UniqueJewel': [('Normal','einzigartiges Juwel','an additional Unique Jewel')],
    'UniqueFlask': [('Normal','einzigartige Flasche','an additional Unique Flask')],
    'ExceptionalGems': [('Normal','außergewöhnliches Gem','an additional Exceptional Gem')],
    'MirrorShard': [('Normal','Spiegelscherbe','an additional Mirror Shard')],
    'FracturingOrb': [('Normal','Fracturing Orb','an additional Fracturing Orb')],
    'DivineOrb': [('Single','ein Divine Orb','an additional Divine Orb'), ('Multiple','mehrere Divine Orbs','additional Divine Orbs')],
    'AnnulmentOrb': [('Single','ein Orb of Annulment','an additional Orb of Annulment'), ('Multiple','mehrere Orbs of Annulment','additional Orbs of Annulment')],
    'ReflectiveMist': [('Normal','Reflecting Mist','an additional Reflecting Mist')],
    'HinekorasLock': [('Normal',"Hinekora's Lock", "an additional Hinekora's Lock")],
    'SacredOrb': [('Normal','Sacred Orb','an additional Sacred Orb')],
    'Viscera': [('Normal','Viscera-Gegenstand','an additional Viscera Item')],
    'Threads': [('Normal','zusätzliche Threads','additional Threads'),('Many','viele zusätzliche Threads','many additional Threads')],
    'Divination': [('Normal','zusätzliche Stacked Decks','additional Stacked Decks'),('Many','viele zusätzliche Stacked Decks','many additional Stacked Decks')],
    'Gold': [('Normal','zusätzliches Gold','additional Gold'),('Hoards','große Goldmengen','hoards of Gold')],
    'Maps': [('Normal','zusätzliche seltene Map','an additional Rare Map'), ('Many','viele seltene Maps','many additional Rare Maps')],
    'Currency': [('Normal','zusätzliche Currency','additional Currency Items'), ('Valuable','wertvolle Currency','additional Valuable Currency Items')],
    'RareWeapon': [('Melee','Nahkampfwaffen','additional Melee Weapons'),('Physical','seltene Waffen mit physischem Modifikator','additional Rare Weapons; Weapons dropped by Empowered Monster will have a Physical modifier')],
    'RareRanged': [('Normal','Fernkampfwaffen oder Köcher','additional Ranged Weapons or Quivers')],
    'RareJewellery': [('Normal','Schmuckgegenstände','additional Jewellery items')],
}.items():
    for slug, german, fragment in lines:
        add(icon, slug, german, 'Empowered Monster will drop '+fragment)

for name in ('Dreadmaidens Sacrament','Hide of the Vendigo','Corpse Rose','Ordered Fate','Doedres Tongue'):
    label = {'Dreadmaidens Sacrament':"Dreadmaidens' Sacrament",'Doedres Tongue':"Doedre's Tongue"}.get(name, name)
    add('UniqueAuguryItem', re.sub(r'\W','',name), label, f'Empowered Monster will drop {label}')

for slug, label, tooltip in [
    ('Quality','Gems mit Qualität','additional Gems with Quality'),
    ('MixedMaximum','Gems, teils maximale Qualität','additional Gems, some of which will be maximum Quality'),
    ('Maximum','Gems mit maximaler Qualität','additional Gems with maximum Quality'),
    ('Skill','Skill Gem','an additional Skill Gem'),
    ('Support','Support Gem','an additional Support Gem'),
]:
    add('Gems',slug,label,'Empowered Monster will drop '+tooltip)

for slug, label, tooltip in [
    ('Greatly','erhöhte Gegenstands-Seltenheit','greatly increased Item Rarity'),
    ('Massively','massiv erhöhte Gegenstands-Seltenheit','massively increased Item Rarity'),
    ('Extremely','extrem erhöhte Gegenstands-Seltenheit','extremely increased Item Rarity')]:
    add('IncreasedRarityAffectedMonster',slug,label,'Empowered Monster has '+tooltip)

# Requirements are three different text outcomes represented by ONE RareArmour image.
for stat, german in [('Strength','Stärke'),('Dexterity','Geschicklichkeit'),('Intelligence','Intelligenz')]:
    add('RareArmour',stat,f'Seltene Rüstung mit {german}-Anforderung',
        f'Empowered Monster will drop additional Armour items with {stat} requirements')

# Fated gear (3.30.0c): an item's guaranteed/banned modifier may vary without a new icon.
# The second boolean distinguishes the guaranteed additional Rare item reward from the
# lower-tier chance-based reward with the same artwork.
GEAR_MODIFIERS = {
    'Boots': [('Resistance','Widerstands-Modifikator','a Resistance modifier'),('NoDefence','ohne Verteidigungs-Modifikatoren','no Defence modifiers'),('Speed','Geschwindigkeits-Modifikator','a Speed modifier')],
    'Helmet':[('Defence','Verteidigungs-Modifikator','a Defence modifier'),('Life','Lebens-Modifikator','a Life modifier'),('Drop','Drop-Modifikator','a Drop modifier')],
    'BodyArmour':[('Life','Lebens-Modifikator','a Life modifier'),('Defence','Verteidigungs-Modifikator','a Defence modifier'),('Chaos','Chaos-Modifikator','a Chaos modifier')],
    'Gloves':[('Defence','Verteidigungs-Modifikator','a Defence modifier'),('Life','Lebens-Modifikator','a Life modifier'),('Attack','Angriffs-Modifikator','an Attack modifier')],
    'Shield':[('Life','Lebens-Modifikator','a Life modifier'),('Defence','Verteidigungs-Modifikator','a Defence modifier'),('Resistance','Widerstands-Modifikator','a Resistance modifier')],
    'Quiver':[('Elemental','Elementar-Modifikator','an Elemental modifier'),('NoElemental','ohne Elementar-Modifikatoren','no Elemental modifiers')],
    'Ring':[('Mana','Mana-Modifikator','a Mana modifier'),('Speed','Geschwindigkeits-Modifikator','a Speed modifier')],
    'Amulet':[('Attribute','Attribut-Modifikator','an Attribute modifier'),('Damage','Schadens-Modifikator','a Damage modifier'),('Gem','Gem-Modifikator','a Gem modifier')],
    'Belt':[('Defence','Verteidigungs-Modifikator','a Defence modifier'),('Elemental','Elementar-Modifikator','an Elemental modifier')],
    'Axe':[('Speed','Geschwindigkeits-Modifikator','a Speed modifier'),('Physical','physischer Modifikator','a Physical modifier')],
    'Bow':[('Speed','Geschwindigkeits-Modifikator','a Speed modifier'),('Critical','kritischer Modifikator','a Critical modifier')],
    'Claw':[('Speed','Geschwindigkeits-Modifikator','a Speed modifier'),('Critical','kritischer Modifikator','a Critical modifier'),('NoPhysical','ohne physische Modifikatoren','no Physical modifiers')],
    'Dagger':[('Speed','Geschwindigkeits-Modifikator','a Speed modifier'),('Critical','kritischer Modifikator','a Critical modifier'),('NoAttack','Runendolch ohne Angriffs-Modifikatoren','no Attack modifiers')],
    'FishingRod':[('Angling','Angling-Modifikator','an Angling modifier')],
    'Mace':[('Speed','Geschwindigkeits-Modifikator','a Speed modifier'),('Physical','physischer Modifikator','a Physical modifier')],
    'Sceptre':[('Mana','Mana-Modifikator','a Mana modifier'),('Gem','Gem-Modifikator','a Gem modifier'),('NoPhysical','ohne physische Modifikatoren','no Physical modifiers')],
    'Staff':[('Mana','Mana-Modifikator','a Mana modifier'),('Gem','Gem-Modifikator','a Gem modifier'),('NoAttack','ohne Angriffs-Modifikatoren','no Attack modifiers'),('WarstaffSpeed','Kampfstab mit Geschwindigkeits-Modifikator','a Speed modifier'),('WarstaffCritical','Kampfstab mit kritischem Modifikator','a Critical modifier')],
    'Wand':[('Mana','Mana-Modifikator','a Mana modifier'),('Gem','Gem-Modifikator','a Gem modifier'),('NoAttack','ohne Angriffs-Modifikatoren','no Attack modifiers')],
    'Sword':[('Speed','Geschwindigkeits-Modifikator','a Speed modifier'),('Critical','kritischer Modifikator','a Critical modifier'),('NoPhysical','ohne physische Modifikatoren','no Physical modifiers')],
}

PLURALS = {
    'Boots':'Boots','Helmet':'Helmets','BodyArmour':'Body Armours','Gloves':'Gloves','Shield':'Shields',
    'Quiver':'Quivers','Ring':'Rings','Amulet':'Amulets','Belt':'Belts','Axe':'Axes',
    'Bow':'Bows','Claw':'Claws','Dagger':'Daggers','FishingRod':'Fishing Rods',
    'Mace':'Maces','Sceptre':'Sceptres','Staff':'Staves','Wand':'Wands','Sword':'Swords'
}

for category, mod_rows in GEAR_MODIFIERS.items():
    for slug, german, fragment in mod_rows:
        obj = 'Rune Daggers' if category=='Dagger' and slug=='NoAttack' else 'Warstaves' if slug.startswith('Warstaff') else PLURALS[category]
        mod_verb = 'will have ' if not fragment.startswith('no ') else 'will have '
        for tier, adjective, drop in (
            ('Guaranteed','Zusätzliche seltene','will drop additional Rare'),
            ('Chance','Chance auf zusätzliche','has a chance to drop additional'),
        ):
            add(category,f'{tier}{slug}',f'{adjective} {obj} – {german}',
                f'Empowered Monster {drop} {obj}; {obj} dropped by Empowered Monster {mod_verb}{fragment}')

VARIANTS = tuple(_VARIANTS)
VARIANT_BY_ID = {item.variant_id:item for item in VARIANTS}
if len(VARIANTS) != len(VARIANT_BY_ID):
    raise RuntimeError('Duplicate reward variant ID')


def variants_for(icon_id: str) -> tuple[RewardVariant, ...]:
    icon_id = normalise_icon_id(icon_id)
    return tuple(v for v in VARIANTS if v.icon_id == icon_id)


def get_variant(variant_id: str) -> RewardVariant | None:
    return VARIANT_BY_ID.get(variant_id)


def _clean(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', (value or '').lower()).strip()


def match_tooltip(text: str, icon_id: str) -> RewardVariant | None:
    """Only accept unambiguous strong matches; never trust an icon to supply the tier."""
    clean = _clean(text)
    icon_id = normalise_icon_id(icon_id)
    if not clean or len(clean) < 16:
        return None
    matches = [v for v in variants_for(icon_id) if _clean(v.tooltip_en) in clean]
    return matches[0] if len(matches) == 1 else None
