"""PoE Covens reward outcome catalogue, distinct from the 45 *visual* icons.

Different outcomes often use identical artwork. A confirmed tooltip may identify an
outcome, while an image match can identify ONLY its icon category. Never infer an
outcome from the icon alone. Dataset transcribed from PoEDB Fates rewards (2026-11-22),
including 3.30.0c replacement modifiers. New game patches may add further outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from reward_catalog import REWARD_ICONS

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
