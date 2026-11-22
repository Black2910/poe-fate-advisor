# PoE Fate Advisor v1.3.1 – Lernende Icon-Bibliothek + einfacher Update-Manager

Windows-Tool für **Path of Exile 1**, Liga 3.30, insbesondere den **Toxic Rain Pathfinder**. Alle Spielaktionen bleiben manuell: Der Advisor liest auf Tastendruck einen Screenshot, führt keine Spielklicks aus und greift nicht auf den PoE-Prozess zu.

## Einmalige Installation (empfohlen)

1. Vorherigen Fate Advisor **vollständig beenden**, auch neben der Windows-Uhr.
2. ZIP entpacken und **`Einmal_installieren.bat`** doppelklicken. Das erfordert **Python 3.10 oder neuer**, aber keine Administratorrechte.
3. Die Installation landet fest unter **`%LOCALAPPDATA%\PoEFateAdvisor`**. Der Installer versucht eine Desktop-Verknüpfung **„PoE Fate Advisor“** anzulegen.
4. Bei der ersten Nutzung diese Verknüpfung bzw. `start_windows.bat` im Installationsordner ausführen. Beim ersten Start werden Python-Abhängigkeiten installiert. Danach kann der **leise Start** verwendet werden.
5. Deine alten Einstellungen in `~\.poe_fate_advisor_config.json` werden automatisch weiterbenutzt. Ein früher im Windows-Anmeldetresor gespeicherter API-Key bleibt dort und wird nicht in den Programmordner kopiert.

Das einmalige Entpacken ist leider nötig, weil v1.2 noch keinen Update-Manager besitzt. **Ab v1.3** ersetzt der Update-Tab den Ordnerwechsel.

## Fate-Auswahl wie bisher

- **F7**: einen kostenlosen **Lern-Screenshot ohne API** im Spiel aufnehmen. Danach über ⚙ → „Loot-Icons lernen“ die Symbole prüfen und bestätigen.
- **F8**: genau ein Screenshot, maximal eine OpenAI-Vision-Abfrage; obere Fate-Reihe wird lokal isoliert.
- **F6**: tatsächlich im Spiel gewählte Fate für die Zone merken (kein Ingame-Klick).
- **F9**: Overlay und Kartenrahmen ein-/ausblenden.
- **Spielmodus**: großes Fenster verbergen, kleines Overlay behalten.
- Nur sichtbare, angebotene Karten werden bewertet. Gesammelte Fates aus der unteren Reihe sind keine neuen Angebote.
- Loot-Kategorien werden lokal aus Symbolen ermittelt. Nicht erkannte Icons bleiben **unbekannt**, statt dass die KI einen Loot erfindet.

Die Auswahl mit 2–3 angebotenen Fates ist optimiert. Die detaillierte Bossaltar-Auswertung ist weiterhin nicht aktiviert.

## Neu: 45 Kategorien in einer lokalen SQLite-Datenbank

Der Tab **„Loot-Icons lernen“** enthält die 45 Reward-Icon-Kategorien aus den PoEDB-Fates-Daten. Kategorie ist **nicht** gleich exakt garantierter Gegenstand: Dasselbe Icon kann verschiedene Varianten/Modifikatoren bezeichnen.

**So trainierst du ein neues Icon:**

1. Fates öffnen, im Advisor den Tab `Loot-Icons lernen` auswählen.
2. Im Spiel **F7** drücken (ein Screenshot ohne API-Kosten) oder im Lern-Tab **„Screenshot GRATIS aufnehmen“** klicken bzw. eine gespeicherte Screenshot-Datei laden. Die F7-Taste funktioniert auch bei verborgenem Hauptfenster.
3. Karte 1/2/3 wählen. Eine große Vorschau zeigt das **zu speichernde Icon**. Wichtig: Icon und Kartennummer prüfen.
4. Im Dropdown die zutreffende Loot-Kategorie auswählen – beispielsweise **`Gold – Gold`**, `Wand – seltene Zauberstäbe` oder `Currency – zusätzliche Währungsgegenstände`.
5. **„Dieses Icon als Kategorie bestätigen + lernen“** wählen. Die Zuordnung wird erst nach ausdrücklicher Bestätigung lokal gespeichert. Eine falsch gewählte Kategorie kannst du über **„Eigene Beispiele löschen“** entfernen.

Die Datenbank liegt unter **`~\.poe_fate_advisor_data\reward_icons.sqlite3`** und die Bilder unter **`~\.poe_fate_advisor_data\samples`**. Sie bleiben bei Updates erhalten. Mit **„Bibliothek sichern (ZIP)“** und **„Bibliothek importieren“** kannst du sie zusätzlich sichern bzw. übertragen. Importierte Proben werden nicht automatisch als eigene verifizierte Beispiele ausgewiesen.

**Referenzbild-Abdeckung:** Fünf bestätigte ältere Beispiele sind beigelegt. Weitere PoEDB-Bilddateien werden über den Button **„PoEDB-Bilder aktualisieren“** und beim Start öffentlich heruntergeladen, soweit erreichbar, und lokal gecacht. **45 Kategorien heißt nicht, dass sofort jedes Symbol sicher erkannt wird**; unbekannte Kategorien bleiben offen und können durch einmaliges Bestätigen gelernt werden. Das Downloaden dieser öffentlichen Bilder verbraucht keine OpenAI-API-Tokens.

## Neu: Updates ohne neuen Programmordner

**Für zukünftige Versionen (z. B. v1.4):**

1. Hauptfenster öffnen → Tab **„Updates“**.
2. **„Update aus heruntergeladener ZIP installieren“** klicken, zukünftige vollständige Fate-Advisor-Release-ZIP wählen.
3. Der Advisor prüft Versionsnummer, ZIP-Pfade und Paketstruktur. Danach muss das Update ausdrücklich bestätigt werden.
4. Die App wird geschlossen, der separate Update-Prozess sichert die vorhandenen Programmdateien, aktualisiert den **gleichen Installationsordner** und startet die App neu.
5. **Einstellungen, Windows-Tresor-Key, Fate-Verlauf und trainierte Icon-Bibliothek bleiben außerhalb der aktualisierten Dateien.**

Die Versionssicherung und das Update-Log findest du unter **`~\.poe_fate_advisor_updates`**. Bei einem Abbruch werden bereits ersetzte Dateien soweit möglich zurückgesetzt. Wenn Windows den Neustart blockiert: Log prüfen und den Advisor über die Desktop-Verknüpfung starten.

**GitHub-Releases.** Im Update-Tab ist `Black2910/poe-fate-advisor` als Quelle vorbelegt; bei Bedarf kannst du `Besitzer/Repository` ändern. Nach „Online nach Update suchen“ kann der Advisor ein neueres Release herunterladen, sofern GitHub dafür eine SHA-256-Asset-Prüfsumme liefert. **Die Release-Quelle `Black2910/poe-fate-advisor` ist ab v1.3.1 voreingestellt. Online-Updates sind erst möglich, sobald das Repository öffentlich erreichbar ist und ein neueres GitHub-Release veröffentlicht wurde.** Ohne konfigurierte Quelle funktioniert sofort die ZIP-Update-Funktion. Automatische Installationen ohne Bestätigung erfolgen nicht.

### Sicherheit / Einschränkungen

- Ein ZIP-Update ist ausführbarer Programmcode; **nur ZIP-Dateien aus vertrauenswürdiger Quelle** installieren. ZIP-Prüfungen und SHA-256 bei GitHub-Releases verhindern nicht, dass der Herausgeber selbst unsicheren Code veröffentlicht.
- Keine Hintergrund-Screenshots, keine automatische Spielfigur-Steuerung.
- Screenshot-Bildverarbeitung und Windows-Update-Neustart wurden lokal getestet, aber **nicht im tatsächlichen Windows-Spiel** Ende-zu-Ende getestet. PoE-Auflösung, UI-Skalierung und Windows-Sicherheitseinstellungen können Probleme verursachen.
- Die OpenAI-API für F8 ist separat kostenpflichtig; das lokale Icon-Training kostet keine API-Tokens.

## Entwicklung und Tests

```bash
python -m unittest discover -s tests -v
```

Quellen zu Reward-IDs/Kategorien: [PoEDB – Fates](https://poedb.tw/us/Fates), öffentliche Bilder über `cdn.poedb.tw`. GitHub-Release-API: [GitHub Docs](https://docs.github.com/en/rest/releases/assets). Spielgrafiken gehören ihren jeweiligen Rechteinhabern. Nicht mit Grinding Gear Games verbunden.

## GitHub-Veröffentlichung

Dieses Quellcode-Paket enthält GitHub Actions für automatisierte Tests sowie zum Erzeugen eines Windows-Python-Release-ZIP bei einem `vX.Y.Z`-Tag. Die ZIP enthält den vollständigen Fate Advisor einschließlich Installer, ist aber **kein kompiliertes EXE** – Python wird auf Windows benötigt.

1. Repository auf GitHub als **Public** anlegen, damit der integrierte Updater Releases ohne Anmeldung erreichen kann. Keine README/License/.gitignore beim GitHub-Anlegen vorab erzeugen.
2. Quellcode auf `main` hochladen. GitHub Actions prüfen die Tests.
3. Für das erste Release einen Tag `v1.3.1` auf dem geprüften `main`-Commit erstellen und pushen. GitHub Actions veröffentlicht `PoE_Fate_Advisor_v1.3.1.zip`.
4. Ab v1.3.1 ist `Black2910/poe-fate-advisor` im Update-Tab als Quelle vorausgewählt; für die bereits installierte v1.3.0 musst du die Repo-Adresse einmal eintragen.

Beim Veröffentlichen keine API-Schlüssel, Screenshots oder persönlichen Konfigurationsdateien einchecken. Persönliche Daten verbleiben im Benutzerprofil. Die Nutzung und Weiterverteilung der im Projekt enthaltenen Spielgrafiken unterliegen den Rechten von Grinding Gear Games bzw. den jeweiligen Urhebern.
