"""PoE Fate Advisor, a read-only, manually triggered Windows screenshot companion.

One F8 press => one screenshot => one optional OpenAI Vision analysis.
No game memory, client modification, file reads or automated game inputs.
"""
from __future__ import annotations

import base64
from io import BytesIO
import json
import os
import queue
from pathlib import Path
import re
import sys
import subprocess
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Any

from fate_engine import Fate, FATE_NAMES, rank_fates
from reward_catalog import classify_tooltip, icon_label, icon_legend, REWARD_ICONS
from reward_variants import variants_for, get_variant, normalise_icon_id, match_tooltip, VARIANTS
from selection_validation import position_label, verify_card_names, fail_closed_disagreement
from image_regions import fate_image_regions, to_full_image_boxes
from vision_sheet import create_visual_sheet
from icon_ranking import validate_geometry, score_and_choose
from icon_reference import independently_read_icons, start_icon_prefetch, crop_reward_icons, prefetch_official_icons
from icon_database import IconDatabase, DATA_HOME
from app_updates import VERSION, DEFAULT_GITHUB_REPO, inspect_package, backup_root, query_github_release, download_verified_release
from overlay import FateOverlay, GREEN, YELLOW
from card_marker import CardMarker, screen_card_rect
from tray import TrayController

APP_TITLE = "PoE Fate Advisor v1.3.2 | Toxic Rain Pathfinder"
CONFIG_FILE = Path.home() / ".poe_fate_advisor_config.json"
PHASES = ("Kampagne", "Frühe Maps", "Rote Maps")
GOALS = ("Ausgewogen", "Sicher", "Loot", "Viscera")
MODEL = os.getenv("POE_FATE_MODEL", "gpt-4.1-mini")
BG, SURFACE, EDIT, TEXT, MUTED, ACCENT = "#0b1220", "#182338", "#263650", "#edf3ff", "#9aaecb", "#67dbb3"

SYSTEM_RULES = """Du bist ein präziser Berater für die PoE-1-Liga 3.30 Covens of Umbra,
Build: Toxic Rain Pathfinder (beweglicher Distanzkämpfer, Chaos Damage over Time).
Der Nutzer löst pro Tastendruck exakt eine Bildschirmaufnahme aus.
Bei Coven-Auswahl wird als Bild AUSSCHLIESSLICH die obere Kartenreihe gezeigt.
Bereits gewählte Fates werden allenfalls im Textkontext genannt und dürfen NIEMALS als aktuelle Kandidaten erscheinen.

Unterscheide ZWEI SPIELPHASEN und deren Unterzustände:

1) COVEN-AUSWAHL: 1 bis 3 Karten nebeneinander, von links nach rechts nummeriert.
   Bei 2 Karten sind die Positionen LINKS=1 und RECHTS=2 (NICHT Mitte).
   An jeder Coven-Stelle darf der Spieler GENAU EINE der ANGEZEIGTEN Karten aufnehmen.
   Bewerte die Auswahl nach: konkreten Belohnungssymbolen (inkl. Sets),
   Risiko für frühes Toxic Rain, und bereits eingesammelten Fates.
   NUR sichtbar angebotene Karten duerfen empfohlen werden. Bereits gesammelte
   Fates sind Kontext, KEINE weiteren angebotenen Auswahlkarten.
   Nur hier best_number=1..Anzahl sichtbarer Karten, selected_numbers=[genau eine Zahl].

2) INVOKE FATES / BOSSALTAR: OBEN befindet sich das Ablagefeld, UNTEN
   der Deck-Vorrat bereits gesammelter Fate-Karten. Das ist KEINE neue
   Auswahl aus drei Karten. Führe nur eine Zustandsdiagnose durch.
   - 'empty': unten bereits eingesammelte Karten; oben noch keine; Kartenzahl z.B. 2/2.
   - 'one': eine Karte liegt oben; die zweite unten; ausgewaehlte Karte
     zeigt ihre ursprüngliche Belohnung. Tooltip im Beispiel: 20% mehr
     Schaden gegen Feinde auf Low Life.
   - 'merged': beide gleichen Fates wurden oben zusammengeführt,
     unten sind die Karten verdunkelt; oben sichtbar ein Fate mit DREI
     Belohnungssymbolen. Tooltip im Beispiel: 30% mehr Schaden gegen
     Feinde auf Low Life. Gleiche Fates verschmelzen, die Belohnung
     der ersten Fate wird verdreifacht, die der zweiten verworfen.
   Diese Werte und die 3 Symbole gelten nur für die BEISPIELBILDER:
   prüfe tatsächlichen Tooltip/Icons jedes Mal neu!
   Die Anzeige 2/2 BERICHTET den Kartenbestand in der Zone –
   sie ist NICHT '2 von 2 aktuell aktiviert' und bleibt nach dem
   Verschieben unverändert. Nicht aus 2/2 die Zahl Boss-Slots folgern.
   Bei Invocation: best_number=0 und selected_numbers=[].
   Gib im Text eine schrittweise Anleitung zum nächsten manuellen Schritt.
   Triff nie selbst eine Auswahl oder drücke in-game Tasten.

LOOT-BELOHNUNGEN – HÖCHSTE PRIORITÄT. Fate-Namen haben KEINE
festen Belohnungen. In verschiedenen echten Nutzerbildern hatte dieselbe
Fate einmal das RareArmour-Symbol und später das goldene Currency-Symbol inklusive Tooltip:
"Empowered Monster will drop additional Currency Items". Beides ist möglich.
AUS DEM FATE-NAMEN NIEMALS auf den Loot SCHLIESSEN. Die vorherige
Fate-Name=Loot-Regeln sind FALSCH und sind hiermit AUFGEHOBEN.

Für JEDE Karte trenne Fate-MECHANIK von Loot-Kategorie. Lies möglichst den
englischen Tooltip des Loot-Icons (falls eingeblendet) und schreibe seinen
wortgetreuen Inhalt in reward_tooltip NUR bei derjenigen Karte, deren Icon
den Tooltip ausgelöst hat. Nicht den Fate-Mechanik-Tooltip oben links damit
verwechseln. Wenn nur das Icon sichtbar ist, gib reward_tooltip="" und
reward_icon als exakte Icon-ID aus dem Verzeichnis unten; wenn nicht
sicher identifizierbar, reward_icon="unknown". rewards darf dann nur eine
Vermutung sein. Wenn weder Tooltip noch Symbol sicher zuordnenbar sind:
"unbekannt", nie einen konkreten Gegenstand erfinden.
Goldenes Bündel/Münzen-Symbol = Currency (Währung), NICHT RareArmour.
Blau-schwarze Rüstungssilhouette = RareArmour (Rüstungsart offen), NICHT Helm.
Drei bläuliche Pfeilspitzen = RareRanged (Fernkampfwaffen/Köcher).
Für mehrere identische Icons, Set-Klammern und spezielle Qualitäts-/
Affix-Boni keine Wirkungen aus der reinen Symbolform ableiten. Tooltips
sind höherwertig als Icons. Beachte die Anpassungen aus Patch 3.30.0c.

WENN Loot eines Kandidaten unklar ist, bewerte den Fate vorsichtig:
Keine sichere Gegenstandsqualität, keinen garantierten Drop und keine
unbelegte positive Loot-Aussage nennen. Erwähne das ausdrücklich.

Achte auf Tooltip-Fakten, insbesondere physische Explosionen nach
Projektile-Treffern, gestaffelte Projektilnovas und erhöhten
Schaden gegen Spieler mit Low Life. Bewerte für frühe Kampagne den
Überlebensaspekt höher als seltene, zufällige Ausrüstung.

Antworte ausschließlich als valides JSON mit genau diesen Feldern:
{
 "screen_type":"selection|invocation|unknown",
 "invocation_state":"empty|one|merged|other|not_applicable",
 "cards":[{"number":1,"name":"sichtbarer Kartenname","rewards":"unbekannt","reward_tooltip":"","reward_icon":"unknown","danger":"niedrig|mittel|hoch","notes":"Bossmechanik, NICHT Beute","box":[xmin,ymin,xmax,ymax]}],
 "best_number":0,
 "selected_numbers":[],
 "recommendation":"Deutsch, konkret, vorsichtig, mit Risiko-/Loot-Begründung",
 "confidence":"hoch|mittel|niedrig",
 "uncertainty":"Nur belegte Unsicherheiten"
}
Bei einer COVEN-AUSWAHL: Bestimme fuer JEDE tatsaechlich sichtbare Karte
ihre aeusseren Kartengrenzen als 'box' im Koordinatensystem des
OBEREN KARTEN-AUSSCHNITTS: [x_min,y_min,x_max,y_max] in relativen
Werten 0 bis 1000, wobei (0,0) oben links und (1000,1000) unten rechts ist.
Gemeint ist die ganze rechteckige Karte samt Titel und Belohnungssymbol.
Ignoriere die Tooltip-Leiste und andere UI-Elemente. Die tatsaechlich sichtbaren Karten muessen von links nach rechts nummeriert sein.
Keine fiktive dritte Karte ergaenzen. Ist die Karte bereits in vorherigen
Screenshots oder in der Historie, aber jetzt nicht zu sehen, ist sie
keine Option. Bei Unsicherheit best_number=0.
Falls die Position einer Karte nicht sicher bestimmbar ist: 'box':null.
Keine Box erfinden. Beim BOSSALTAR sind die Boxen nicht erforderlich.
Falls 'selection' best_number=1..Anzahl sichtbarer Karten, selected_numbers=[best_number].
Falls 'invocation' best_number=0, selected_numbers=[].
Bei 'unknown' best_number=0, selected_numbers=[].
Beschreibe keine garantierten Drops oder erfundenen Modifikatoren.
"""
SYSTEM_RULES += "\nLOOT-ICON-KATALOG (IDs aus PoEDB, nur Kategorie, nicht Fate-Zuordnung): " + icon_legend()

# Separate independent read: do not mention previous Fates, potential recommendations,
# preferred names or the content of the first model response. Otherwise the reader
# could repeat the same hallucination rather than transcribing the screenshot.
CARD_READER_RULES = """Du bist ausschließlich ein Ableser der JETZT ANGEBOTENEN Fate-Kartennamen.
Du siehst zwei Bilder: 1. ein schmales Bild des Fenstertitels ('Fates' oder
'Invoke Fates'), 2. NUR die obere Kartenreihe des Fate-Fensters. Die unten
bereits eingesammelten Fates wurden physisch aus dem Bild entfernt.

Wenn der Titel 'Invoke Fates' lautet: screen_type=invocation, visible_names=[].
Wenn der Titel 'Fates' lautet: screen_type=selection, sichtbare Kartentitel
in Links-Rechts-Reihenfolge, exakt 1 bis 3 Titel. Keine Namen ergänzen, keine
Vorhersagen machen. Bei Unsicherheit screen_type=unknown. Keine Empfehlungen.
Du bekommst KEINEN Fate-Verlauf und darfst keine weiteren Karten annehmen.
Antworte nur mit JSON:
{"screen_type":"selection|invocation|unknown", "visible_names":["..."], "confidence":"hoch|mittel|niedrig"}.
"""


def parse_json(raw: str) -> dict[str, Any]:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("KI-Antwort enthält kein JSON")
        return json.loads(s[start:end + 1])


def _encoded_jpeg(image, max_side: tuple[int,int] = (2048,1536)) -> str:
    from PIL import ImageOps
    reduced = ImageOps.contain(image.convert("RGB"), max_side)
    bio = BytesIO()
    reduced.save(bio, format="JPEG", quality=93, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(bio.getvalue()).decode("ascii")


def _no_safe_choice(reason: str, names: list[str] | None = None) -> dict[str, Any]:
    return fail_closed_disagreement({"screen_type": "selection"}, names or [], reason)


VISION_RULES = """Du liest genau EIN Bildblatt aus EINER Aufnahme der PoE-1 Fate-Auswahl.
Darin sind klar markiert: ORIGINALTITEL, A=OBERE ANGEBOTENE KARTEN,
B=VERGRÖSSERTE UNTERE HÄLFTE VON A (GLEICHE KARTEN),
Referenzbeispiele zweier sicher bestätigter Loot-Icons. Historische unten
bereits gesammelte Fates sind NICHT im Bild; NICHT hinzudenken.

Ermittle zuerst screen_type: 'Fates'=selection, 'Invoke Fates'=invocation,
sonst unknown. Bei selection lies exakt 1-3 OBEN tatsächlich sichtbare
Karten von links nach rechts (number=1..N), einschließlich Namen.
WICHTIG: KEINE Empfehlung einer Karte ausserhalb dieser Liste.

LOOT: Die kleinen runden Symbole unter den Karten (in Bild B vergrößert)
stellen die BELONHUNGSKATEGORIE dar. Fate-Namen sind KEINE Loot-Information!
Nutze Bild B und die bestätigten Referenzsymbole. Für JEDE Karte:
'reward_icon' = eine exakte ID aus der angehängten Liste ODER 'unknown'.
'reward_icon_confidence'=hoch|mittel|niedrig. Bei geringem Vertrauen
unknown. Symbol-ID NIE anhand Fate-Name oder der Farbpalette allein erraten.
Ein Icon sagt NICHT zuverlässig die genaue Untervariante aus: z.B.
gewöhnliche vs. wertvollere Currency, genaue Gegenstandsmodifikatoren,
Qualitätsstufe, garantierter Spezial-Gegenstand. Diese Varianten NICHT erfinden.
Falls ein Belohnungstooltip auf dem Bild steht, kann er zusätzlich exakt
als reward_tooltip transkribiert werden; er ist NICHT notwendig.
Referenzsymbole unten zeigen Currency und RareArmour; diese gehören
KEINER im Bild gezeigten Karte, sondern sind reine Vergleiche.
Bei Set-Klammern: nur sichtbar markieren, keine garantierte Set-Belohnung erfinden.

Beschreibe in 'notes' NUR Boss-Gefahr / Mechanik; keine Loot-Behauptungen.
Einzelne Fate-Fähigkeiten im Kartenbild müssen von Loot getrennt bleiben.
Antwort AUSSCHLIESSLICH JSON, nicht Markdown:
{
 "screen_type":"selection|invocation|unknown",
 "invocation_state":"empty|one|merged|other|not_applicable",
 "cards":[{"number":1,"name":"...","reward_icon":"Currency|RareArmour|unknown|...",
 "reward_icon_confidence":"hoch|mittel|niedrig","reward_tooltip":"",
 "rewards":"", "danger":"niedrig|mittel|hoch", "notes":"...", "box":null}],
 "best_number":0,"selected_numbers":[],"recommendation":"",
 "confidence":"hoch|mittel|niedrig","names_confidence":"hoch|mittel|niedrig","uncertainty":""
}
"names_confidence" bewertet NUR die LESBARKEIT der Karten-NAMEN. Unbekannte Loot-Icons senken NUR reward_icon_confidence, niemals names_confidence.
'best_number'=0 und selected_numbers=[] (Empfehlung wird ausschließlich lokal
nach Validierung der oberen Karten bestimmt). Nur die Karten und ihre Icons ablesen.
Für invocation keine neue Empfehlung, cards=[]; Staat other zulässig.
Kennst du das Symbol nicht -> unknown, statt erfinden.
ICON-IDs: """ + icon_legend()


# Only the locally detected selectable-card row is sent to this reader.
# The model must not decide whether the user is at a Coven or an altar.
# A narrow JSON schema reduces irrelevant/repeated screen classification errors.
SELECTION_CARD_SCHEMA = {
    "type":"object", "additionalProperties":False,
    "properties": {
        "names_confidence": {"type":"string","enum":["hoch","mittel","niedrig"]},
        "cards": {"type":"array", "items":{
            "type":"object","additionalProperties":False,
            "properties":{
                "number":{"type":"integer"},
                "name":{"type":"string"},
                "danger":{"type":"string","enum":["niedrig","mittel","hoch"]},
                "notes":{"type":"string"},
            },
            "required":["number","name","danger","notes"]
        }}
    },
    "required":["names_confidence","cards"]
}

SELECTION_RULES = """Transcribe Path of Exile Fates. The software has isolated
ONLY the current offered TOP card row. For each card, read the printed NAME,
then describe the combat risk ONLY (not the loot). Count from LEFT to RIGHT,
exactly one result per offered card; never include previously selected cards.
Do not try to decode loot symbols. All reward ICON recognition is performed
LOCALLY from a separate library of reference images, so neither guess the
loot nor mention it. Return ONLY the requested structured JSON schema.
names_confidence rates printed titles, NOT the small reward icons.
"""


def _model_cards_payload(raw: dict, expected_count: int) -> dict:
    """Do not allow a model's global screen_type field to veto local geometry."""
    cards=raw.get('cards', [])
    if not isinstance(cards,list) or not cards:
        return _no_safe_choice(
            f'KI hat keine Kartennamen geliefert (lokal {expected_count} Karten erkannt).'
            ' Analysebild über Einstellungen prüfen.')
    names_confidence=raw.get('names_confidence', raw.get('confidence','niedrig'))
    icon_uncertain=any(c.get('reward_icon_confidence')=='niedrig' or c.get('reward_icon')=='unknown' for c in cards if isinstance(c,dict))
    overall_confidence=('mittel' if names_confidence=='hoch' and icon_uncertain else names_confidence)
    return {
        'screen_type':'selection', 'invocation_state':'not_applicable',
        'cards':cards, 'names_confidence':names_confidence,
        'confidence':overall_confidence,
        'best_number':0, 'selected_numbers':[],
        'recommendation':'', 'uncertainty':''
    }


def analyse_image(pil_image, api_key: str, phase: str, goal: str,
                  prior: list[Fate]) -> dict[str, Any]:
    """One F8 = one screenshot = one structured-output API request.

    First detect the card geometry locally, then transcribe ONLY those cards;
    no global screen-type decision from the model. This prevents the recurring
    'Keine sichere neue Coven-Auswahl erkannt' veto on clearly visible cards.
    """
    from openai import OpenAI
    from PIL import ImageOps
    screenshot=ImageOps.contain(pil_image.convert('RGB'),(2048,1536))
    view=fate_image_regions(screenshot)
    count=view.cards_count
    # With >=2 cards in the top visible row the current Coven-selection
    # geometry can be validated locally. Single-card and boss altar layouts
    # need separate treatment: refuse to mark rather than confuse history.
    if not view.geometry_confident or count not in (2,3):
        return _no_safe_choice('Keine eindeutige obere Auswahlreihe mit 2 oder 3 Karten'
                               ' gefunden. Bei Bossaltären keine neue Fate markieren.')
    sheet=create_visual_sheet(view,with_reference=False)
    client=OpenAI(api_key=api_key,timeout=35.0,max_retries=0)
    response=client.responses.create(
        model=MODEL,store=False,instructions=SELECTION_RULES,
        max_output_tokens=1200,
        text={'format':{'type':'json_schema','name':'fate_card_reading',
                        'strict':True,'schema':SELECTION_CARD_SCHEMA}},
        input=[{'role':'user','content':[
            {'type':'input_text','text':f'THERE ARE EXACTLY {count} CURRENTLY OFFERED CARDS IN SECTION A. Read {count} card titles left to right and assess only combat danger. Loot icons are processed on the computer separately. All cards are currently selectable.'},
            {'type':'input_image','image_url':_encoded_jpeg(sheet,max_side=(1600,1600)),'detail':'high'},
        ]}],
    )
    raw_text=getattr(response,'output_text','')
    if not raw_text:
        return _no_safe_choice('API hat keine lesbare Kartenantwort geliefert;'
                               ' mögliche Ausgabegrenze/Antwortunterbrechung.')
    try:
        reading=parse_json(raw_text)
    except (ValueError,TypeError,KeyError) as err:
        return _no_safe_choice('KI-Antwort nicht als Kartenliste lesbar: '+str(err)[:140])
    # Legacy/mock replies may include an explicit altar verdict, but the
    # production schema never asks the model to classify the selection UI.
    if reading.get('screen_type')=='invocation' and not reading.get('cards'):
        return {'screen_type':'invocation','invocation_state':reading.get('invocation_state','other'),
                'cards':[],'best_number':0,'selected_numbers':[],
                'confidence':'mittel','recommendation':'Bossaltar erkannt. Keine neue Fate speichern.'}
    if not isinstance(reading.get('cards'),list) or not reading.get('cards'):
        return _no_safe_choice(f'KI hat keine Kartennamen geliefert (lokal {count} Karten erkannt).')
    result=normalize_analysis_result(_model_cards_payload(reading,count))
    result=validate_geometry(result,view)
    if result.get('visual_verification')!='geometry_confirmed':return result
    # Read and validate actual reward artwork separately, without asking AI
    # to guess from its own list of 45 text labels. An uncertain icon remains
    # UNKNOWN, never a valuable Currency or other invented reward.
    independently_verified_icons = independently_read_icons(screenshot, view)
    for card, observed in zip(result['cards'], independently_verified_icons):
        if observed.category in ('unknown', ''):
            card['reward_icon'] = 'unknown'
            card['reward_icon_confidence'] = 'niedrig'
            card['rewards'] = 'Loot-Symbol nicht sicher erkannt'
            card['loot_evidence'] = 'unknown'
        else:
            card['reward_icon'] = observed.category
            card['reward_icon_confidence'] = ('hoch' if observed.similarity >= .86 else 'mittel')
            card['rewards'] = icon_label(observed.category) + ' (Symbolkategorie; Variante offen)'
            card['loot_evidence'] = 'verified_image'
        card['icon_match_similarity'] = observed.similarity
        card['icon_reference_source'] = observed.source
    best,reason=score_and_choose(result['cards'],prior,phase,goal)
    result['best_number']=best
    result['selected_numbers']=[best] if best else []
    result['recommendation']=reason
    result['offered_names']=[c['name'] for c in result['cards']]
    if any(c.get('loot_evidence')=='unknown' for c in result['cards']):
        result['uncertainty']='Mindestens ein Loot-Symbol nicht anhand eines verifizierten Bildvergleichs bestätigt; Kategorie dort unbekannt.'
        if result.get('confidence')=='hoch':
            result['confidence']='mittel'
    return result

def apply_visual_verification(result: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    """For real screenshots require a separate reading of the candidate titles."""
    if result.get("screen_type") != "selection":
        return _no_safe_choice("Bildanalyse hat die bereits erkannten angebotenen Karten nicht als Auswahl erkannt.", verification.get("visible_names", []))
    valid, visible_names, why = verify_card_names(result.get("cards", []), verification)
    if not valid:
        return fail_closed_disagreement(result, visible_names, why)
    if result.get("confidence") == "niedrig":
        return fail_closed_disagreement(result, visible_names, "Die Empfehlung selbst wurde nur mit geringer Sicherheit erkannt.")
    result["visual_verification"] = "confirmed"
    if result.get("best_number") == 0:
        result["recommendation"] = "Kartennamen erkannt, aber keine eindeutige Fate-Empfehlung möglich."
    return result


def normalize_analysis_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate advice and never treat an invocation screenshot as a new Fate pick."""
    cards = result.get("cards", [])
    if not isinstance(cards, list):
        raise ValueError("Unerwartetes Antwortformat: cards")
    kind = result.get("screen_type", "unknown")
    if kind not in ("selection", "invocation", "unknown"):
        kind = "unknown"
    result["screen_type"] = kind
    if kind == "invocation":
        if result.get("invocation_state") not in ("empty", "one", "merged", "other"):
            result["invocation_state"] = "other"
    else:
        result["invocation_state"] = "not_applicable"
    # Fate-Karten koennen nur an den Coven-Stationen gewaehlt werden.
    # Invoke-Screens duerfen KEINE erneute Speicherung ausloesen.
    best = result.get("best_number", 0)
    try:
        best = int(best)
    except (ValueError, TypeError):
        best = 0
    indices = {int(c["number"]) for c in cards if isinstance(c, dict)
               and str(c.get("number", "")).isdigit()}
    # ICON-FIRST by default. Reward tooltips are OPTIONAL, never required.
    # Category comes from the visible icon; exact bonus variants cannot be
    # inferred from a category icon even with high model confidence.
    for card in cards:
        if not isinstance(card,dict):continue
        icon=card.get('reward_icon','unknown')
        degree=card.get('reward_icon_confidence','niedrig')
        if degree not in ('hoch','mittel') or not icon_label(icon):
            icon='unknown'
        card['reward_icon']=icon
        verified=classify_tooltip(card.get('reward_tooltip',''))
        if verified:
            card['rewards']=verified
            card['loot_evidence']='tooltip'
        elif icon!='unknown':
            card['rewards']=icon_label(icon) + ' (Symbolkategorie; Variante offen)'
            card['loot_evidence']='icon'
        else:
            card['rewards']='Belohnungssymbol unbekannt'
            card['loot_evidence']='unknown'
        # notes are only about combat risks; do not echo unverified loot prose
        card['notes']=str(card.get('notes',''))[:220]
    if kind != "selection" or best not in indices or best not in (1, 2, 3):
        result["best_number"] = 0
        result["selected_numbers"] = []
    else:
        result["best_number"] = best
        result["selected_numbers"] = [best]
    # Never display the model's free-form answer: it may refer to a
    # nonexistent card or invent a reward. Local verified ranking replaces it.
    if kind == "selection":
        result["recommendation"] = "Kartennamen/Icons werden noch geometrisch überprüft."
    return result


class RegionPicker(tk.Toplevel):
    """Transparent click-and-drag geometry only: no game screenshot is taken here."""
    def __init__(self, root, callback):
        super().__init__(root)
        self.callback = callback
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.30)
        self.configure(bg="black")
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(400, 40, text="Fate-Karten mit gedrückter Maus einrahmen  |  ESC = Abbrechen",
                                fill="white", font=("Segoe UI", 16, "bold"))
        self.start = None
        self.rectangle = None
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.finish)
        self.bind("<Escape>", lambda _: self.destroy())
        self.focus_force()

    def start_drag(self, event):
        self.start = (event.x, event.y)
        if self.rectangle:
            self.canvas.delete(self.rectangle)
        self.rectangle = self.canvas.create_rectangle(event.x, event.y, event.x + 1, event.y + 1,
                                                      outline="#65efae", width=3, fill="")

    def drag(self, event):
        if self.start and self.rectangle:
            self.canvas.coords(self.rectangle, self.start[0], self.start[1], event.x, event.y)

    def finish(self, event):
        if not self.start:
            return
        x0, y0 = self.start
        x1, y1 = event.x, event.y
        left, top = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        self.destroy()
        if width >= 100 and height >= 60:
            self.callback((left, top, width, height))


class AdvisorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("940x750")
        self.root.minsize(750, 620)
        self.root.configure(bg=BG)
        self.phase = tk.StringVar(value="Kampagne")
        self.goal = tk.StringVar(value="Ausgewogen")
        self.api_key = tk.StringVar(value=os.getenv("OPENAI_API_KEY", ""))
        self.remember_api_key = tk.BooleanVar(value=False)
        self.region: tuple[int, int, int, int] | None = None
        self.prior: list[Fate] = []
        self.last_cards: list[dict[str, Any]] = []
        self.last_candidate_view = None
        self.last_best = 0
        self.last_bests: list[int] = []
        self.last_screen_type = "unknown"
        self.busy = False
        self._capture_pending = False
        self._poll_after_id = None
        self._capture_after_id = None
        self._events: queue.SimpleQueue = queue.SimpleQueue()
        self._hotkey_listener = None
        self.overlay = None
        self.marker = None
        self._live_capture_region = None
        self._pending_capture_region = None
        self.overlay_pos = None
        self.overlay_compact = False
        self.overlay_opacity = tk.DoubleVar(value=.95)
        self.github_repo = tk.StringVar(value=DEFAULT_GITHUB_REPO)
        self.update_status = tk.StringVar(value='Bereit')
        self.learn_card = tk.StringVar(value='1')
        self.learn_category = tk.StringVar(value='')
        self.learn_variant = tk.StringVar(value='Nicht festgelegt (nur Icon-Kategorie)')
        self.learn_tooltip = tk.StringVar(value='')
        self.learn_status = tk.StringVar(value='Erst einen Screenshot laden oder aufnehmen.')
        self.last_icon_crops = []
        self._db = IconDatabase()
        self._db.import_existing_sources()
        self._load_config()
        if sys.platform == 'win32':
            start_icon_prefetch()  # one-time public art-cache, not an API call
        self._style()
        self._build()
        self.overlay = FateOverlay(
            self.root, self.capture, self.confirm_ai_choice, self.reset_zone,
            self.show_settings, self._save_config,
            geometry=self.overlay_pos, compact=self.overlay_compact,
            opacity=self.overlay_opacity.get(),
            on_visibility=self._sync_marker_visibility,
        )
        self.marker = CardMarker(self.root)
        self.update_history()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._install_hotkey()
        self.tray = TrayController(self._events.put)
        self.tray.start()
        self._poll_after_id = self.root.after(70, self._drain_events)
        self.confirm_button.configure(state="disabled")
        self.log('v1.3 bereit. Icons lokal lernen · Updates aus ZIP installieren · F8 analysiert wie zuvor.')

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", background=EDIT, foreground=TEXT, padding=(12, 8), borderwidth=0)
        style.map("TButton", background=[("active", "#325072")])
        style.configure("Accent.TButton", background="#15745e", foreground="white", padding=(12, 8))
        style.map("Accent.TButton", background=[("active", "#23947a")])
        style.configure("TCombobox", fieldbackground=EDIT, background=EDIT, foreground=TEXT, arrowcolor=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=EDIT, foreground=TEXT, padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", SURFACE)])

    def _build(self):
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)
        tk.Label(container, text="PoE Fate Advisor v1.3", font=("Segoe UI", 20, "bold"),
                 bg=BG, fg=ACCENT).pack(anchor="w")
        tk.Label(container, text="Toxic Rain Pathfinder · Patch 3.30 · Manuelle Screenshots, keine Spielautomatisierung",
                 font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(anchor="w", pady=(2, 14))

        top = ttk.Frame(container)
        top.pack(fill="x", pady=(0, 12))
        ttk.Label(top, text="Spielphase:").pack(side="left", padx=(0, 8))
        ttk.Combobox(top, textvariable=self.phase, values=PHASES, state="readonly", width=14).pack(side="left", padx=(0, 20))
        ttk.Label(top, text="Ziel:").pack(side="left", padx=(0, 8))
        ttk.Combobox(top, textvariable=self.goal, values=GOALS, state="readonly", width=14).pack(side="left")
        ttk.Button(top, text="Neue Zone / Reset", command=self.reset_zone).pack(side="right")

        gamerow = ttk.Frame(container)
        gamerow.pack(fill="x", pady=(0, 10))
        ttk.Button(gamerow, text="Spielmodus: Hauptfenster verbergen", style="Accent.TButton",
                   command=self.enter_game_mode).pack(side="left", padx=(0, 10))
        ttk.Button(gamerow, text="Overlay zeigen (F9)", command=self.show_overlay).pack(side="left", padx=(0, 18))
        ttk.Label(gamerow, text="Overlay-Deckkraft", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        ttk.Scale(gamerow, from_=0.70, to=1.0, variable=self.overlay_opacity,
                  command=self.change_opacity, length=100).pack(side="left")

        tabs = ttk.Notebook(container)
        tabs.pack(fill="both", expand=True)
        live = ttk.Frame(tabs, padding=12)
        manual = ttk.Frame(tabs, padding=12)
        tabs.add(live, text="Live-Screenshot mit KI")
        tabs.add(manual, text="Offline: manuell vergleichen")
        learning = ttk.Frame(tabs, padding=12)
        updates = ttk.Frame(tabs, padding=12)
        tabs.add(learning, text='Loot-Icons lernen')
        tabs.add(updates, text='Updates')

        keyrow = ttk.Frame(live)
        keyrow.pack(fill="x", pady=(0, 6))
        ttk.Label(keyrow, text="OpenAI API-Key:").pack(side="left", padx=(0, 10))
        tk.Entry(keyrow, textvariable=self.api_key, show="*", bg=EDIT, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(live, text="API-Key im Windows-Anmeldetresor speichern (freiwillig)",
                        variable=self.remember_api_key,
                        command=self._save_config).pack(anchor="w", pady=(2, 5))
        ttk.Label(live, text="Ohne Häkchen wird der Key nicht gespeichert. API-Nutzung kostet separat; Screenshots gehen zur Analyse an OpenAI.",
                  style="Muted.TLabel", wraplength=760).pack(anchor="w", pady=(0, 12))
        regionrow = ttk.Frame(live)
        regionrow.pack(fill="x", pady=(0, 7))
        ttk.Button(regionrow, text="1. Vollständigen Fate-Bereich markieren", command=self.choose_region).pack(side="left", padx=(0, 8))
        ttk.Button(regionrow, text="2. Screenshot (F8)", style="Accent.TButton",
                   command=self.capture).pack(side="left", padx=(0, 8))
        ttk.Button(regionrow, text="Screenshot-Datei öffnen", command=self.open_image).pack(side="left")
        ttk.Button(live, text="Erkannten OBEREN Kartenbereich anzeigen", command=self.preview_candidate_area).pack(anchor="w", pady=(0, 6))
        self.region_label = ttk.Label(live, text=self.region_description(), style="Muted.TLabel")
        self.region_label.pack(anchor="w", pady=(0, 12))
        ttk.Label(live, text="F8 = ein Screenshot + Overlay · F6 = im Spiel gewählte Fate merken · F9 = Overlay ein/aus.",
                  style="Muted.TLabel", wraplength=770).pack(anchor="w", pady=(0, 8))
        ttk.Label(live, text="Loot-Kategorie wird aus dem kleinen Symbol unter jeder Karte gelesen. Kein Tooltip und kein Maus-Hover nötig.",
                  style="Muted.TLabel", wraplength=770).pack(anchor="w", pady=(0, 8))
        ttk.Label(live, text="Hinweis: Die automatische Auswahl ist für Coven-Angebote mit 2–3 Karten optimiert; Bossaltäre werden nicht als neue Fate gespeichert.",
                  style="Muted.TLabel", wraplength=770).pack(anchor="w", pady=(0, 8))
        ttk.Label(live, text="Empfehlung / Bossaltar-Analyse", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.output = tk.Text(live, bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                              wrap="word", font=("Segoe UI", 11), height=15, padx=14, pady=12)
        self.output.pack(fill="both", expand=True, pady=(8, 10))
        self.output.configure(state="disabled")
        bottom = ttk.Frame(live)
        bottom.pack(fill="x")
        self.confirm_button = ttk.Button(bottom, text="Gewählte Coven-Fate merken",
                                         command=self.confirm_ai_choice)
        self.confirm_button.pack(side="left", padx=(0, 10))
        self.progress = ttk.Label(bottom, text="Bereit", style="Muted.TLabel")
        self.progress.pack(side="left")

        ttk.Label(manual, text="Ohne API: drei Fate-Namen und die sichtbaren Belohnungen eingeben. ",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 15))
        self.manual_names, self.manual_rewards = [], []
        for i in range(3):
            line = ttk.Frame(manual)
            line.pack(fill="x", pady=(0, 15))
            ttk.Label(line, text=f"Karte {i + 1}:", width=10).pack(side="left")
            name_var, reward_var = tk.StringVar(), tk.StringVar()
            self.manual_names.append(name_var)
            self.manual_rewards.append(reward_var)
            ttk.Combobox(line, textvariable=name_var, values=FATE_NAMES, width=18).pack(side="left", padx=(0, 8))
            tk.Entry(line, textvariable=reward_var, bg=EDIT, fg=TEXT, insertbackground=TEXT,
                     relief="flat", font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)
        ttk.Label(manual, text="Beispiele: additional Currency Items, Rare Bow, RareArmour, Divine Orb. Gleicher Fate-Name kann anderen Loot haben!",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Button(manual, text="Fates offline vergleichen", command=self.manual_rank,
                   style="Accent.TButton").pack(anchor="w")
        self.manual_output = tk.Text(manual, bg=SURFACE, fg=TEXT, relief="flat", wrap="word",
                                     font=("Segoe UI", 11), height=12, padx=14, pady=12)
        self.manual_output.pack(fill="both", expand=True, pady=(12, 8))
        self.manual_output.configure(state="disabled")
        ttk.Button(manual, text="Offline-Empfehlung merken", command=self.confirm_manual_choice).pack(anchor="w")
        self.offline_result: list = []

        self._build_learning_tab(learning)
        self._build_update_tab(updates)

        footer = ttk.Frame(container)
        footer.pack(fill="x", pady=(12, 0))
        self.history = ttk.Label(footer, text="In dieser Zone gewählt: —", style="Muted.TLabel")
        self.history.pack(anchor="w")
        ttk.Label(footer, text="Inoffizielles Community-Tool – nicht mit Grinding Gear Games verbunden.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(footer, text="Loot-Kategorien direkt aus Icons: Tooltip nicht nötig. Exakte Untervarianten können unklar bleiben.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        self.update_history()

    # ---------- User-confirmed reward-icon library ----------
    def _build_learning_tab(self, parent):
        ttk.Label(parent, text='F7 = kostenloser Screenshot. Icon + separater Loot-Buff-Katalog; Lernen nur nach Bestätigung.',
                  style='Muted.TLabel', wraplength=760).pack(anchor='w', pady=(0,8))
        top = ttk.Frame(parent); top.pack(fill='x', pady=(0,8))
        ttk.Button(top, text='F7 · Screenshot GRATIS aufnehmen', command=self.capture_for_learning,
                   style='Accent.TButton').pack(side='left', padx=(0,8))
        ttk.Button(top, text='Bilddatei laden', command=self.load_learning_image).pack(side='left', padx=(0,8))
        ttk.Button(top, text='PoEDB-Bilder aktualisieren', command=self.refresh_public_icons).pack(side='left')
        pane = ttk.Frame(parent); pane.pack(fill='x', pady=(4,10))
        ttk.Label(pane,text='Karte:').pack(side='left')
        self.learn_card_select=ttk.Combobox(pane,textvariable=self.learn_card,values=['1','2','3'],
                                           state='readonly',width=4)
        self.learn_card_select.pack(side='left',padx=(5,15))
        self.learn_card_select.bind('<<ComboboxSelected>>', lambda e:self.show_training_crop())
        ttk.Label(pane,text='Belohnung (Icon-Kategorie):').pack(side='left',padx=(0,5))
        self.learn_cat_select=ttk.Combobox(pane,textvariable=self.learn_category,
                                         values=[f'{"RareShields" if k == "Shield" else k} – {v}' for k,v in sorted(REWARD_ICONS.items())],
                                         state='readonly',width=43)
        self.learn_cat_select.pack(side='left',fill='x',expand=True)
        self.learn_cat_select.bind('<<ComboboxSelected>>',lambda _e:self.update_variant_options())
        ttk.Label(parent,text='Genaue Loot-Variante (optional; bei gleichem Icon nicht automatisch erkennbar):',
                  style='Muted.TLabel').pack(anchor='w',pady=(3,2))
        self.learn_variant_select=ttk.Combobox(parent,textvariable=self.learn_variant,
                                              values=['Nicht festgelegt (nur Icon-Kategorie)'],
                                              state='readonly',width=90)
        self.learn_variant_select.pack(fill='x',pady=(0,5))
        tooltip_line=ttk.Frame(parent);tooltip_line.pack(fill='x',pady=(0,8))
        ttk.Label(tooltip_line,text='Loot-Tooltip (optional):').pack(side='left',padx=(0,6))
        ttk.Entry(tooltip_line,textvariable=self.learn_tooltip,width=53).pack(side='left',fill='x',expand=True)
        ttk.Button(tooltip_line,text='Variante aus Tooltip finden',command=self.suggest_variant_from_tooltip).pack(side='left',padx=(8,0))
        self.learn_category.trace_add('write',lambda *_args:self.update_variant_options())
        self.update_variant_options()
        ttk.Label(parent,text='Nur Icon-Kategorie wird beim nächsten F8 automatisch erkannt. Varianten aus Tooltips sind getrennt gespeicherte Beobachtungen.',
                  style='Muted.TLabel',wraplength=760).pack(anchor='w',pady=(0,5))
        previewrow = ttk.Frame(parent); previewrow.pack(fill='x')
        self.learn_preview=tk.Label(previewrow,text='Noch kein Icon',bg=SURFACE,fg=MUTED,
                                    width=16,height=7)
        self.learn_preview.pack(side='left',padx=(0,18),pady=(0,8))
        right=ttk.Frame(previewrow); right.pack(side='left',fill='both',expand=True)
        ttk.Button(right,text='Dieses Icon als Kategorie bestätigen + lernen',
                   command=self.confirm_training_icon,style='Accent.TButton').pack(anchor='w',pady=(0,6))
        ttk.Label(right,textvariable=self.learn_status,style='Muted.TLabel',
                  wraplength=520).pack(anchor='w')
        bar=ttk.Frame(parent);bar.pack(fill='x',pady=(8,5))
        ttk.Button(bar,text='Bibliothek sichern (ZIP)',command=self.export_icon_library).pack(side='left',padx=(0,8))
        ttk.Button(bar,text='Bibliothek importieren',command=self.import_icon_library).pack(side='left',padx=(0,8))
        ttk.Button(bar,text='Liste aktualisieren',command=self.refresh_icon_catalog).pack(side='left',padx=(0,8))
        ttk.Button(bar,text='Eigene Beispiele löschen',command=self.delete_user_icons).pack(side='left')
        table=ttk.Frame(parent);table.pack(fill='both',expand=True)
        self.learn_tree=ttk.Treeview(table,columns=('label','count','confirmed'),show='headings',height=7)
        for name,title,width in [('label','Icon-Kategorie',370),('count','Bilder',70),('confirmed','Davon selbst bestätigt',160)]:
            self.learn_tree.heading(name,text=title)
            self.learn_tree.column(name,width=width,stretch=name=='label')
        scrollbar=ttk.Scrollbar(table,orient='vertical',command=self.learn_tree.yview)
        self.learn_tree.configure(yscrollcommand=scrollbar.set)
        self.learn_tree.pack(side='left',fill='both',expand=True)
        scrollbar.pack(side='left',fill='y')
        self.refresh_icon_catalog()

    def set_learning_screenshot(self, picture):
        """Populate crops from ONE existing shot, before any network work."""
        try:
            view=fate_image_regions(picture)
            if not view.geometry_confident or view.cards_count not in (2,3):
                self.last_icon_crops=[]
                if hasattr(self,'learn_status'):
                    self.learn_status.set('Keine sichere obere Kartenreihe gefunden.')
                return
            self.last_icon_crops=crop_reward_icons(picture,view)
            if hasattr(self,'learn_card_select'):
                self.learn_card_select.configure(values=[str(x+1) for x in range(len(self.last_icon_crops))])
                self.learn_card.set('1')
                self.show_training_crop()
                self.learn_status.set(f'{len(self.last_icon_crops)} Icons gefunden. Kategorie nur nach Prüfung bestätigen.')
        except Exception as err:
            self.last_icon_crops=[]
            if hasattr(self,'learn_status'):
                self.learn_status.set('Bildzuordnung fehlgeschlagen: '+str(err)[:80])

    def show_training_crop(self):
        try:
            number=int(self.learn_card.get())
            if not 1<=number<=len(self.last_icon_crops):
                raise ValueError('Keine Karte in dieser Position')
            from PIL import ImageTk
            crop=self.last_icon_crops[number-1].resize((120,120))
            img=ImageTk.PhotoImage(crop)
            self.learn_preview.configure(image=img,text='',width=120,height=120)
            self.learn_preview.image=img
        except (ValueError,IndexError):
            self.learn_preview.configure(image='',text='Noch kein Icon',width=16,height=7)
            self.learn_preview.image=None

    def update_variant_options(self):
        if not hasattr(self,'learn_variant_select'):
            return
        category=normalise_icon_id(self.learn_category.get().split(' – ',1)[0])
        options=['Nicht festgelegt (nur Icon-Kategorie)']
        options += [f'{v.variant_id} – {v.label_de}' for v in variants_for(category)]
        self.learn_variant_select.configure(values=options)
        if self.learn_variant.get() not in options:
            self.learn_variant.set(options[0])

    def suggest_variant_from_tooltip(self):
        category=normalise_icon_id(self.learn_category.get().split(' – ',1)[0])
        match=match_tooltip(self.learn_tooltip.get(), category)
        if match:
            self.learn_variant.set(f'{match.variant_id} – {match.label_de}')
            self.learn_status.set('Passende Variante gefunden – erst nach Prüfung bestätigen.')
        else:
            self.learn_status.set('Keine eindeutige Variante im Tooltip gefunden. Bitte manuell wählen oder nur das Icon lernen.')

    def confirm_training_icon(self):
        try:
            idx=int(self.learn_card.get())-1
            if idx<0 or idx>=len(self.last_icon_crops):
                raise ValueError('Bitte zuerst einen Screenshot aufnehmen oder laden.')
            category=normalise_icon_id(self.learn_category.get().split(' – ',1)[0])
            if category not in REWARD_ICONS:
                raise ValueError('Bitte eine bekannte Kategorie aus der Liste wählen.')
            selected_variant=self.learn_variant.get().split(' – ',1)[0]
            variant=get_variant(selected_variant)
            if variant and variant.icon_id != category:
                raise ValueError('Die Variante passt nicht zur gewählten Icon-Kategorie.')
            if selected_variant != 'Nicht festgelegt (nur Icon-Kategorie)' and not variant:
                raise ValueError('Bitte eine gültige Loot-Variante auswählen.')
            summary=(f'Genauer Loot-Buff: {variant.label_de}\n' if variant else
                     'Genaue Variante: unbekannt (wird nicht aus dem Icon abgeleitet)\n')
            if not messagebox.askyesno('Lernbeispiel bestätigen',
                  f'Stimmt das sichtbare Icon von Karte {idx+1} wirklich mit\n'
                  f'{category}: {REWARD_ICONS[category]} überein?\n'
                  +summary+'\nNur bestätigen, wenn du die Bedeutung sicher kennst.'):
                return
            changed=self._db.add_sample(category,self.last_icon_crops[idx])
            if variant:
                self._db.record_variant(category, self.last_icon_crops[idx], variant.variant_id,
                                        self.learn_tooltip.get())
            self.refresh_icon_catalog()
            message=('Bild gelernt: ' if changed else 'Dieses Bild ist bereits gespeichert: ')+REWARD_ICONS[category]
            if variant:
                message+=f'. Loot-Variante als Beobachtung erfasst: {variant.label_de} (NICHT per Icon vorhersagbar).'
            else:
                message+='. Genaue Variante bleibt unbekannt.'
            self.learn_status.set(message)
        except Exception as err:
            messagebox.showerror('Icon lernen',str(err))

    def load_learning_image(self):
        filename=filedialog.askopenfilename(filetypes=[('Screenshot','*.png *.jpg *.jpeg *.webp')])
        if not filename:return
        from PIL import Image
        try:
            with Image.open(filename) as pic:self.set_learning_screenshot(pic.copy())
        except Exception as err:
            self.learn_status.set('Bild nicht ladbar: '+str(err))

    def capture_for_learning(self):
        if self.busy or self._capture_pending:return
        self._capture_pending=True
        self.marker.hide(clear=True)
        self.overlay.suspend_for_capture()
        self._capture_after_id=self.root.after(160,self._capture_learning_once)

    def _capture_learning_once(self):
        self._capture_after_id=None
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                if self.region:
                    x,y,w,h=self.region
                    monitor={'left':x,'top':y,'width':w,'height':h}
                else: monitor=sct.monitors[1]
                shot=sct.grab(monitor)
                img=Image.frombytes('RGB',(shot.width,shot.height),shot.rgb)
            self.set_learning_screenshot(img)
            if self.last_icon_crops:
                self.overlay.set_message('LERNMODUS',f'{len(self.last_icon_crops)} Loot-Icons erfasst',
                     '⚙ Einstellungen → Loot-Icons lernen',
                     'Screenshot kostenlos; Kategorie im Lernmodus bestätigen.',GREEN,can_save=False)
        except Exception as err:
            self.learn_status.set('Lern-Screenshot fehlgeschlagen: '+str(err))
        finally:
            self._capture_pending=False
            self.overlay.resume_after_capture()

    def delete_user_icons(self):
        category=normalise_icon_id(self.learn_category.get().split(' – ',1)[0])
        if category not in REWARD_ICONS:
            messagebox.showinfo('Kategorie wählen','Bitte zunächst die Kategorie auswählen, die du korrigieren möchtest.')
            return
        if not messagebox.askyesno('Eigene Lernbeispiele löschen',
             f'Alle von dir bestätigten Bilder für {REWARD_ICONS[category]} löschen?\n'
             'Öffentliche Vorlagen bleiben erhalten.'):
            return
        try:
            count=self._db.remove_user_samples(category)
            self.refresh_icon_catalog()
            self.learn_status.set(f'{count} eigene Bilder für {category} gelöscht.')
        except Exception as err:
            messagebox.showerror('Löschen fehlgeschlagen',str(err))

    def refresh_icon_catalog(self):
        if not hasattr(self,'learn_tree'):return
        self._db.import_existing_sources()
        tree=self.learn_tree
        for child in tree.get_children():tree.delete(child)
        for cat in self._db.list_categories():
            tree.insert('', 'end', values=(f'{cat.icon_id} – {cat.description}',cat.samples,cat.user_confirmed))

    def refresh_public_icons(self):
        self.learn_status.set('Hole öffentliche PoEDB-Bildvorlagen … Keine OpenAI-Kosten.')
        def work():
            try:
                prefetch_official_icons()
                count=self._db.import_existing_sources()
                self._events.put(('icons_refreshed',count))
            except Exception as err:
                self._events.put(('icons_failed',str(err)))
        threading.Thread(target=work,daemon=True).start()

    def export_icon_library(self):
        path=filedialog.asksaveasfilename(defaultextension='.zip',
                 initialfile='PoE_Fate_Icon_Bibliothek.zip',filetypes=[('ZIP','*.zip')])
        if not path:return
        try:
            self._db.export_backup(Path(path))
            self.learn_status.set('Bibliothek gesichert unter '+path)
        except Exception as err:messagebox.showerror('Export fehlgeschlagen',str(err))

    def import_icon_library(self):
        path=filedialog.askopenfilename(filetypes=[('Icon-Bibliothek ZIP','*.zip')])
        if not path:return
        try:
            added=self._db.import_backup(Path(path))
            self.refresh_icon_catalog()
            self.learn_status.set(f'{added} neue Referenzbilder importiert.')
        except Exception as err:messagebox.showerror('Import fehlgeschlagen',str(err))

    # ---------- User-controlled program updates ----------
    def _build_update_tab(self,parent):
        ttk.Label(parent,text='Einmalig v1.3 installieren, danach Updates bequem hier einspielen.',
                  style='Muted.TLabel',wraplength=730).pack(anchor='w',pady=(0,12))
        ttk.Label(parent,text='Aktuelle Version: v'+VERSION).pack(anchor='w',pady=(0,9))
        ttk.Button(parent,text='Update aus heruntergeladener ZIP installieren …',
                   command=self.choose_update_zip,style='Accent.TButton').pack(anchor='w',pady=(0,12))
        ttk.Label(parent,text='Optional: GitHub-Releases (nur wenn ein eigenes Release-Repository existiert)',
                  style='Muted.TLabel',wraplength=700).pack(anchor='w',pady=(0,7))
        line=ttk.Frame(parent);line.pack(fill='x',pady=(0,12))
        ttk.Label(line,text='Repository:').pack(side='left',padx=(0,7))
        ttk.Entry(line,textvariable=self.github_repo,width=34).pack(side='left',padx=(0,8))
        ttk.Button(line,text='Online nach Update suchen',command=self.check_online_update).pack(side='left')
        ttk.Label(parent,textvariable=self.update_status,style='Muted.TLabel',wraplength=750).pack(anchor='w',pady=(0,12))
        ttk.Label(parent,text='Ablauf: ZIP prüfen → ausdrücklich bestätigen → altes Programm schließen → '
                  'Update mit Sicherung installieren → Advisor neu starten. '
                  'API-Key (Windows-Tresor), Einstellungen und trainierte Icons bleiben erhalten.',
                  wraplength=760,style='Muted.TLabel').pack(anchor='w',pady=(0,12))
        ttk.Label(parent,text='Wichtig: Installiere nur ZIP-Dateien aus vertrauenswürdiger Quelle. '
                  'Ein Update enthält ausführbaren Programmcode.',
                  wraplength=760,style='Muted.TLabel').pack(anchor='w')

    def choose_update_zip(self):
        filename=filedialog.askopenfilename(title='Neues Fate-Advisor-Release wählen',
                                            filetypes=[('Fate-Advisor ZIP','*.zip')])
        if filename:self.install_update_zip(Path(filename))

    def install_update_zip(self,path:Path):
        try:
            info=inspect_package(path)
            if not messagebox.askyesno('Update installieren?',
                f'Version {VERSION} → {info["version"]}\n\n'
                f'Das Programm wird beendet, aktualisiert und neu gestartet.\n'
                f'{len(info["members"])} Programmdateien, Sicherung der alten Version.\n\n'
                'Nur fortfahren, wenn du dieser ZIP-Datei vertraust.'):
                return
            pending=backup_root()/('pending_'+info['version'].replace('.','_')+'.zip')
            shutil.copy2(path,pending)
            self._save_config()
            script=Path(__file__).resolve().parent/'updater_worker.py'
            args=[sys.executable,str(script),'--pid',str(os.getpid()),'--zip',str(pending),
                  '--install',str(Path(__file__).resolve().parent),'--python',sys.executable]
            flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0
            subprocess.Popen(args,creationflags=flags,cwd=str(script.parent),close_fds=True)
            self.close()
        except Exception as err:
            messagebox.showerror('Update konnte nicht gestartet werden',str(err))

    def check_online_update(self):
        self._save_config()
        repo=self.github_repo.get().strip()
        self.update_status.set('Prüfe GitHub-Releases …')
        def work():
            try:self._events.put(('release_checked',query_github_release(repo)))
            except Exception as err:self._events.put(('release_failed',str(err)))
        threading.Thread(target=work,daemon=True).start()

    def _on_release_checked(self,info):
        if info is None:
            self.update_status.set('Keine neuere Version im eingetragenen GitHub-Repository gefunden.')
            return
        self.update_status.set(f'Update v{info.version} gefunden: {info.name}')
        if not messagebox.askyesno('Neues Release',
             f'Version {info.version} ist verfügbar.\n\n'
             'Soll das ZIP heruntergeladen und über SHA-256 geprüft werden?'):
            return
        self.update_status.set(f'Lade Update v{info.version} …')
        def worker():
            try:
                path=download_verified_release(info,backup_root())
                self._events.put(('release_downloaded',str(path)))
            except Exception as err:self._events.put(('release_failed',str(err)))
        threading.Thread(target=worker,daemon=True).start()

    def region_description(self):
        return f"Ausschnitt: {self.region}" if self.region else "Ausschnitt: nicht gesetzt (F8 erfasst sonst Hauptmonitor)"

    def _load_config(self):
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if data.get("phase") in PHASES:
                self.phase.set(data["phase"])
            if data.get("goal") in GOALS:
                self.goal.set(data["goal"])
            r = data.get("region")
            if isinstance(r, list) and len(r) == 4 and all(isinstance(x, int) for x in r):
                self.region = tuple(r)
            pos = data.get("overlay_position")
            if isinstance(pos, list) and len(pos) == 2 and all(isinstance(x, int) for x in pos):
                self.overlay_pos = (pos[0], pos[1])
            self.overlay_compact = bool(data.get("overlay_compact", False))
            self.overlay_opacity.set(max(.7, min(1., float(data.get("overlay_opacity", .95)))))
            remember = bool(data.get("remember_api_key", False))
            self.remember_api_key.set(remember)
            if remember and not self.api_key.get().strip():
                try:
                    import keyring
                    secret = keyring.get_password("PoE Fate Advisor", "OpenAI API")
                    if secret:
                        self.api_key.set(secret)
                except Exception:
                    pass
            self.github_repo.set(str(data.get('github_repo') or DEFAULT_GITHUB_REPO))
            saved = data.get("zone_fates", [])
            if isinstance(saved, list):
                self.prior = [Fate(x["name"], x.get("rewards", "")) for x in saved[:12]
                              if isinstance(x, dict) and isinstance(x.get("name"), str)]
        except (OSError, ValueError, TypeError):
            pass

    def _save_config(self):
        try:
            overlay = getattr(self, "overlay", None)
            data = {
                "phase": self.phase.get(), "goal": self.goal.get(), "region": self.region,
                "overlay_position": list(overlay.position) if overlay else self.overlay_pos,
                "overlay_compact": overlay.compact if overlay else self.overlay_compact,
                "overlay_opacity": self.overlay_opacity.get(),
                "zone_fates": [{"name": fate.name, "rewards": fate.rewards} for fate in self.prior],
                "remember_api_key": self.remember_api_key.get(),
                "github_repo": self.github_repo.get().strip(),
            }
            CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            # Store secrets only via OS credentials; never in the config JSON.
            if sys.platform == "win32":
                try:
                    import keyring
                    if self.remember_api_key.get() and self.api_key.get().strip():
                        keyring.set_password("PoE Fate Advisor", "OpenAI API", self.api_key.get().strip())
                    elif not self.remember_api_key.get():
                        try:
                            keyring.delete_password("PoE Fate Advisor", "OpenAI API")
                        except keyring.errors.PasswordDeleteError:
                            pass
                except Exception:
                    # A disabled/unavailable vault must never break the app.
                    pass
        except OSError:
            pass

    def _install_hotkey(self):
        try:
            from pynput import keyboard
            # One key release -> one queued user action. The listener thread never
            # invokes Tk methods or interacts with the game.
            actions = {keyboard.Key.f8: "capture", keyboard.Key.f7: "learn",
                       keyboard.Key.f6: "save", keyboard.Key.f9: "overlay"}
            def released(key):
                action = actions.get(key)
                if action:
                    self._events.put(("action", action))
            self._hotkey_listener = keyboard.Listener(on_release=released)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as err:
            self.log("Globale Hotkeys nicht verfügbar: " + str(err))

    def _drain_events(self):
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "result":
                    self.show_analysis(payload)
                elif kind == "error":
                    self.show_error(payload)
                elif kind == 'release_checked':
                    self._on_release_checked(payload)
                elif kind == 'release_failed':
                    self.update_status.set('Online-Prüfung fehlgeschlagen: '+str(payload)[:170])
                elif kind == 'release_downloaded':
                    self.update_status.set('Download geprüft; bereit zur Installation')
                    self.install_update_zip(Path(payload))
                elif kind == 'icons_refreshed':
                    self.refresh_icon_catalog()
                    self.learn_status.set('Öffentliche Vorlagen aktualisiert; '+str(payload)+' neue Bilder indexiert.')
                elif kind == 'icons_failed':
                    self.learn_status.set('Aktualisierung der Icon-Vorlagen fehlgeschlagen: '+str(payload)[:130])
                elif kind == "action":
                    if payload == "capture":
                        self.capture()
                    elif payload == "learn":
                        self.capture_for_learning()
                    elif payload == "save":
                        self.confirm_ai_choice(silent=True)
                    elif payload == "overlay":
                        self.toggle_overlay()
                    elif payload == "settings":
                        self.show_settings()
                    elif payload == "reset":
                        self.reset_zone()
                    elif payload == "quit":
                        self.close()
                        return
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self._poll_after_id = self.root.after(70, self._drain_events)

    def _sync_marker_visibility(self, visible: bool):
        if not self.marker:
            return
        if not visible:
            self.marker.hide()
        elif self.marker._box and not self.busy:
            self.marker.show()

    def change_opacity(self, value):
        if self.overlay:
            self.overlay.set_opacity(float(value))

    def enter_game_mode(self):
        self._save_config()
        self.overlay.show()
        if self.marker and self.marker._box:
            self.marker.show()
        self.root.withdraw()

    def show_settings(self):
        if self.marker:
            self.marker.hide()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def show_overlay(self):
        self.overlay.show()
        if self.marker and self.marker._box and not self.busy:
            self.marker.show()

    def toggle_overlay(self):
        if self.overlay.is_visible:
            self.overlay.hide()
            self.marker.hide()
        else:
            self.overlay.show()
            if self.marker._box and not self.busy:
                self.marker.show()

    def log(self, message: str, widget=None):
        widget = widget or self.output
        if not hasattr(self, "output"):
            return
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", message)
        widget.configure(state="disabled")

    def choose_region(self):
        self.marker.hide(clear=True)
        self.overlay.suspend_for_capture()
        picker = RegionPicker(self.root, self.set_region)
        def cleanup(event):
            if event.widget is picker:
                self.overlay.resume_after_capture()
        picker.bind("<Destroy>", cleanup)

    def set_region(self, region):
        self.region = region
        self.region_label.configure(text=self.region_description())
        self._save_config()

    def capture(self):
        """One deliberate F8/click captures exactly one frame; never polls PoE."""
        if self.busy or self._capture_pending:
            return
        if not self.api_key.get().strip():
            self.log("Für die Bildanalyse brauchst du einen OpenAI-API-Key. "
                     "Gib ihn in den Einstellungen ein, oder verwende den Offline-Tab.")
            self.overlay.set_error("API-Key fehlt · ⚙ Einstellungen öffnen")
            return
        self._save_config()
        self._capture_pending = True
        self.marker.hide(clear=True)
        self.overlay.suspend_for_capture()
        # Let Windows finish removing the overlay from its compositor before
        # grabbing one frame (especially important on windowed-fullscreen PoE).
        self._capture_after_id = self.root.after(160, self._capture_once)

    def _capture_once(self):
        self._capture_after_id = None
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                if self.region:
                    x, y, w, h = self.region
                    monitor = {"left": x, "top": y, "width": w, "height": h}
                else:
                    monitor = sct.monitors[1]
                shot = sct.grab(monitor)  # ONLY screenshot for this explicit action.
                picture = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
            self.start_analysis(picture, (monitor["left"], monitor["top"], shot.width, shot.height))
        except Exception as err:
            self.show_error("Screenshot fehlgeschlagen: " + str(err))
        finally:
            self._capture_pending = False
            self.overlay.resume_after_capture()

    def preview_candidate_area(self):
        """Preview pixels from the LAST screenshot, without taking a new one."""
        if self.last_candidate_view is None:
            messagebox.showinfo("Noch kein Scan", "Erst F8 drücken oder Screenshot-Datei öffnen.")
            return
        from PIL import ImageTk
        preview = tk.Toplevel(self.root)
        preview.title("v1.3 – KI sieht ausschließlich die obere Kartenreihe")
        preview.configure(bg=BG)
        tk.Label(preview, text="AUSSCHLIESSLICH OBERE ANGEBOTENE FATES (nicht bereits gewählte unten)",
                 bg=BG, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(padx=10, pady=10)
        img = self.last_candidate_view.copy()
        img.thumbnail((1100, 650))
        photo = ImageTk.PhotoImage(img)
        panel = tk.Label(preview, image=photo, bg=BG)
        panel.image = photo
        panel.pack(padx=10, pady=10)
        ttk.Button(preview, text="Schließen", command=preview.destroy).pack(pady=10)

    def open_image(self):
        filename = filedialog.askopenfilename(filetypes=[("Bilder", "*.png *.jpg *.jpeg *.webp"), ("Alle Dateien", "*.*")])
        if not filename:
            return
        if not self.api_key.get().strip():
            self.log("API-Key fehlt. Nutze alternativ die Offline-Wertung.")
            return
        from PIL import Image
        try:
            with Image.open(filename) as image:
                self.start_analysis(image.copy(), None)
        except Exception as err:
            self.log("Bild konnte nicht geöffnet werden: " + str(err))

    def start_analysis(self, picture, live_region=None):
        if self.busy:
            return
        self.marker.hide(clear=True)
        self._pending_capture_region = live_region
        start_icon_prefetch()  # Public art cache only; independent of OpenAI API.
        self.set_learning_screenshot(picture)
        self.last_candidate_view = fate_image_regions(picture).offered.copy()
        self.busy = True
        self.progress.configure(text="Analysiere Bild …")
        self.log("1 Screenshot · 1 KI-Anfrage · Icon-Erkennung ohne Hover. Obere Fate-Reihe wird lokal abgegrenzt.")
        self.overlay.set_busy("Belohnung, Risiko und mögliche Duplikate werden bewertet.")
        key, phase, goal, prior = self.api_key.get().strip(), self.phase.get(), self.goal.get(), list(self.prior)
        def work():
            try:
                result = analyse_image(picture, key, phase, goal, prior)
                self._events.put(("result", result))
            except Exception as err:
                self._events.put(("error", str(err)))
        threading.Thread(target=work, daemon=True).start()

    def show_error(self, message: str):
        self.marker.hide(clear=True)
        self._pending_capture_region = None
        self.busy = False
        self.progress.configure(text="Fehler")
        self.log("Analyse fehlgeschlagen:\n" + message + "\n\nPrüfe API-Key, Guthaben und Internetzugang.")
        self.last_bests = []
        self.last_best = 0
        self.last_screen_type = "unknown"
        self.confirm_button.configure(state="disabled")
        self.overlay.set_error(message)

    def show_analysis(self, result: dict[str, Any]):
        self.busy = False
        # Position comes only from a LIVE screenshot: file-imported images have no screen coordinates.
        rect = screen_card_rect(result, self._pending_capture_region)
        self._pending_capture_region = None
        self.marker.hide(clear=True)
        if rect and self.overlay.is_visible:
            self.marker.place(rect)
        self.progress.configure(text="Analyse abgeschlossen")
        self.last_cards = [c for c in result.get("cards", []) if isinstance(c, dict)]
        self.last_screen_type = result.get("screen_type", "unknown")
        self.last_best = int(result.get("best_number", 0))
        self.last_bests = list(result.get("selected_numbers", []))
        lines = []
        if self.last_screen_type == "selection" and self.last_best:
            card = next((c for c in self.last_cards
                         if str(c.get("number")) == str(self.last_best)), {})
            lines.append("ANGEBOTEN: " + ", ".join(c.get("name", "?") for c in self.last_cards) + "\n")
            lines.append(f"NIMM EINE KARTE: {self.last_best} – {card.get('name', '?')}\n")
            self.confirm_button.configure(state="normal")
        elif self.last_screen_type == "invocation":
            labels = {"empty": "noch keine Fate eingesetzt", "one": "eine Fate eingesetzt",
                      "merged": "doppelte Fates verschmolzen", "other": "weiterer Altarzustand"}
            state = result.get("invocation_state", "other")
            lines.append("BOSSALTAR: " + labels.get(state, state) + "\n")
            lines.append("Hier keine neue Fate zum Deck hinzufügen: die Karten sind bereits gesammelt.\n")
            self.confirm_button.configure(state="disabled")
        elif self.last_screen_type == "selection":
            lines.append("AUSWAHL NICHT SICHER ERKANNT – keine Fate auswählen lassen oder speichern.\n")
            self.confirm_button.configure(state="disabled")
        else:
            lines.append("BILDSCHIRM NICHT SICHER ERKANNT\n")
            self.confirm_button.configure(state="disabled")
        lines.append(str(result.get("recommendation", "")) + "\n")
        lines.append("Erkennung: " + self.last_screen_type + " | Sicherheit: " +
                     str(result.get("confidence", "unbekannt")))
        lines.append("-----------------------------------------")
        for card in self.last_cards:
            lines.append(f"\n{card.get('number','?')}. {card.get('name', '?')} · Risiko: {card.get('danger', '?')}")
            lines.append("Belohnung: " + str(card.get("rewards", "unbekannt")))
            lines.append(str(card.get("notes", "")))
        uncertain = result.get("uncertainty", "")
        if uncertain:
            lines.extend(["", "Nicht sicher erkennbar: " + str(uncertain)])
        self.log("\n".join(lines))
        self.overlay.set_result(result)

    def confirm_ai_choice(self, silent=False):
        if self.last_screen_type != "selection" or len(self.last_bests) != 1:
            if not silent:
                messagebox.showinfo("Keine neue Coven-Auswahl",
                                    "Nur eine neue Coven-Auswahl kann gespeichert werden. "
                                    "Am Bossaltar sind die Karten bereits im Deck.")
            return
        number = self.last_bests[0]
        card = next((c for c in self.last_cards if str(c.get("number")) == str(number)), None)
        if not card or not card.get("name"):
            return
        self.marker.hide(clear=True)
        self.prior.append(Fate(name=str(card["name"]), rewards=str(card.get("rewards", ""))))
        self.update_history()
        self._save_config()
        self.overlay.set_message("GESPEICHERT", f"{card['name']} gemerkt",
                                 "Erst F8 an der nächsten Coven-Stelle",
                                 "Gespeichert nach deiner manuellen Auswahl im Spiel.",
                                 GREEN, can_save=False)
        self.log(f"Gesammelte Fate gespeichert: {card['name']}\n"
                 "Nur bestätigen, wenn du sie wirklich an der Coven-Stelle aufgenommen hast."
                 "\nBei einer neuen Zone: Reset drücken.")
        self.last_best = 0
        self.last_bests = []
        self.last_screen_type = "unknown"
        self.confirm_button.configure(state="disabled")

    def manual_rank(self):
        fates = [Fate(n.get(), r.get()) for n, r in zip(self.manual_names, self.manual_rewards) if n.get().strip()]
        self.offline_result = rank_fates(fates, self.prior, self.phase.get(), self.goal.get())
        if not self.offline_result:
            self.log("Wähle zuerst mindestens einen Fate-Namen.", self.manual_output)
            return
        lines = [f"EMPFEHLUNG (heuristisch): {self.offline_result[0].name}",
                 "Achtung: Diese Offline-Wertung kann die konkreten Symbole und Set-Klammern NICHT sehen.\n"]
        for i, fate in enumerate(self.offline_result, 1):
            lines.append(f"{i}. {fate.name} · Schätzwert {fate.score:.1f}\n   {fate.summary}")
        self.log("\n\n".join(lines), self.manual_output)

    def confirm_manual_choice(self):
        if not self.offline_result:
            messagebox.showinfo("Keine Auswahl", "Zuerst die Offline-Wertung starten.")
            return
        selected = self.offline_result[0]
        self.prior.append(Fate(selected.name, selected.rewards))
        self.update_history()
        self._save_config()
        self.log(f"Gemerkt: {selected.name}", self.manual_output)
        self.offline_result = []

    def update_history(self):
        names = " → ".join(x.name for x in self.prior) if self.prior else "—"
        self.history.configure(text=f"In dieser Zone gewählt: {names}")
        if getattr(self, "overlay", None):
            self.overlay.set_prior([fate.name for fate in self.prior])

    def reset_zone(self):
        self.marker.hide(clear=True)
        self.prior.clear()
        self.last_cards.clear()
        self.last_best = 0
        self.last_bests.clear()
        self.last_screen_type = "unknown"
        self.confirm_button.configure(state="disabled")
        self.offline_result.clear()
        self.update_history()
        self.log("Neue Zone begonnen: Fate-Historie zurückgesetzt.")
        if self.overlay:
            self.overlay.set_ready()
        self._save_config()

    def close(self):
        self.marker.hide(clear=True)
        self._save_config()
        for after_id in (self._poll_after_id, self._capture_after_id):
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        if getattr(self, "tray", None):
            self.tray.stop()
        if self.overlay:
            self.overlay.destroy()
        if self.marker:
            self.marker.destroy()
        self.root.destroy()


if __name__ == "__main__":
    app = tk.Tk()
    AdvisorApp(app)
    app.mainloop()
