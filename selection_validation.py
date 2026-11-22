"""Validate visible Fate choices independently of the recommendation model.

A model's own `cards` list is NOT evidence that a recommended Fate was on screen.
For live use a second, independent vision pass transcribes only the visible titles
(without receiving the recommendation or previously collected Fates).
On disagreement we disable recommendations, F6 saving and the green marker.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def normal_name(value: object) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w]+", "", value, flags=re.UNICODE)


def position_label(number: int, total: int) -> str:
    """2-card screens have LEFT and RIGHT, not LEFT and MIDDLE."""
    if total == 2:
        return {1: "LINKS", 2: "RECHTS"}.get(number, "?")
    if total == 3:
        return {1: "LINKS", 2: "MITTE", 3: "RECHTS"}.get(number, "?")
    if total == 1:
        return "EINZIGE KARTE" if number == 1 else "?"
    return "?"


def verify_card_names(cards: list, verification: dict[str, Any]) -> tuple[bool, list[str], str]:
    """Check ordered visible titles from an independent screenshot-reading pass.

    Non-confirmation is the safe default. In particular, comparing the chosen
    name against the first model's *own* cards would accept hallucinations.
    """
    if not isinstance(verification, dict) or verification.get("screen_type") != "selection":
        return False, [], "Die zweite Bildprüfung erkennt keine sichere Coven-Auswahl."
    if verification.get("confidence") not in {"hoch", "mittel"}:
        return False, [], "Die Kartentitel sind in der zweiten Bildprüfung nicht sicher lesbar."
    visible = verification.get("visible_names")
    if not isinstance(visible, list) or not 1 <= len(visible) <= 3:
        return False, [], "Die zweite Bildprüfung konnte die sichtbaren Karten nicht sicher zählen."
    if not all(isinstance(name, str) and normal_name(name) and name.strip() for name in visible):
        return False, [], "Mindestens ein Fate-Name war nicht lesbar."
    if not isinstance(cards, list) or len(cards) != len(visible):
        return False, visible, "Die Anzahl erkannter Karten stimmt nicht überein."
    try:
        ordered = sorted(cards, key=lambda c: int(c["number"]))
        numbers = [int(card["number"]) for card in ordered]
        if numbers != list(range(1, len(visible) + 1)):
            return False, visible, "Die Kartennummerierung ist nicht plausibel."
        observed_names = [str(card["name"]) for card in ordered]
    except (KeyError, TypeError, ValueError, AttributeError):
        return False, visible, "Nicht alle Fate-Karten haben einen lesbaren Namen."
    if [normal_name(name) for name in observed_names] != [normal_name(name) for name in visible]:
        return False, visible, "Die Fate-Namen stimmen zwischen den Bildprüfungen nicht überein."
    return True, visible, ""


def fail_closed_disagreement(result: dict[str, Any], verified_names: list[str], reason: str) -> dict[str, Any]:
    """Discard unverified model claims even in detailed UI text/logs."""
    result["screen_type"] = "selection"
    result["best_number"] = 0
    result["selected_numbers"] = []
    result["confidence"] = "niedrig"
    result["visual_verification"] = "mismatch"
    result["recommendation"] = (
        "KEINE Fate empfohlen: Karten auf dem Screenshot nicht zuverlässig erkannt. "
        "Bitte F8 erneut drücken, wenn alle Kartentitel sichtbar sind."
    )
    result["uncertainty"] = reason
    result["cards"] = [
        {"number": i, "name": name, "rewards": "Nicht geprüft",
         "loot_evidence": "unknown", "danger": "unbekannt", "notes": "Nur unverifizierte Texterkennung", "box": None}
        for i, name in enumerate(verified_names, 1)
    ]
    return result
