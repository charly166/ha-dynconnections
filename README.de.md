# HA DynConnections – Home Assistant Custom Integration

<p align="center">
  <img src="docs/logo.png" alt="HA DynConnections Logo" width="360">
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="hacs_badge"></a>
  <a href="https://github.com/charly166/ha-dynconnections/releases"><img src="https://img.shields.io/github/v/release/charly166/ha-dynconnections" alt="GitHub Release"></a>
  <a href="https://github.com/charly166/ha-dynconnections/blob/main/LICENSE"><img src="https://img.shields.io/github/license/charly166/ha-dynconnections" alt="License"></a>
</p>

[English version](README.md)

---

Eine Home-Assistant-Custom-Integration mit eigener Lovelace-Karte für eine
dynamische ÖPNV-Verbindungsauskunft: die Abfahrtshaltestelle wird anhand des
Live-Standorts eines Smartphones vorgeschlagen (über die Home Assistant
Companion App), Zielhaltestelle und Standort-Gerät werden direkt im Editor
der Karte selbst gewählt, und die eigentliche Suche nach den nächsten 5
Verbindungen wird per Button-Druck ausgelöst – kein Hintergrund-Polling.

Gebaut mit der **Region Stuttgart (VVS)** als erstem Zielgebiet, als
Datenquelle dient dasselbe EFA-Backend (Elektronische Fahrplanauskunft), das
auch [efa.vvs.de](https://efa.vvs.de), die offizielle VVS-Fahrplanauskunft,
selbst nutzt.

## Funktionen

- **Alles wird in der Karte selbst konfiguriert** – kein Einstellungsdialog
  pro Strecke: Karte hinzufügen, Standort-Gerät wählen und Zielhaltestelle
  suchen, direkt im visuellen Editor der Karte
- **Mehrere Strecken** – einfach eine weitere Karte mit anderer
  Geräte-/Ziel-Kombination hinzufügen (z.B. "nach Hause" und "zur Arbeit"),
  keine zusätzlichen Einrichtungsschritte nötig
- **Vorschläge für die Abfahrtshaltestelle** basierend auf dem Live-Standort
  des konfigurierten `device_tracker` (z.B. dein Handy über die Companion
  App), als Dropdown mit manuellem Aktualisieren-Button; jede Haltestelle
  zeigt kleine Badges für die dort verkehrenden Verkehrsmittel (S-Bahn,
  U-Bahn/Stadtbahn, Bus, Regionalzug) – wie bei der Haltestellensuche auf
  vvs.de selbst; dieselben Badges erscheinen auch bei den Zielsuche-
  Ergebnissen im Karten-Editor
- **Optionale Wunsch-Abfahrtszeit** – leer lassen für eine Suche ab "jetzt"
  (als Hinweis direkt neben dem Feld angezeigt)
- **Such-Button** – Verbindungen werden nur abgefragt, wenn du es willst,
  nicht per Timer
- **Die nächsten 5 Verbindungen** werden direkt in der Karte als Timetable
  angezeigt (Linie mit demselben farbigen Verkehrsmittel-Badge wie bei der
  Haltestellenauswahl, Richtung, Abfahrt inkl. Verspätung, Gleis, Ankunft,
  Umstiege, Dauer)
- **Vollständige Reiseroute bei Bedarf**: Verbindungen mit Umstieg lassen
  sich aufklappen und zeigen dann jede Etappe (Linie, Richtung, Haltestelle,
  Zeit, Gleis) inklusive eventueller Fußwege zwischen Bahnsteigen
- Kein Account/API-Key nötig – die EFA-Schnittstelle ist kostenlos und ohne
  Authentifizierung nutzbar

**Hinweis:** Da Strecken komplett in der Karten-Konfiguration leben (nicht
in Home-Assistant-Entitäten), gibt es aktuell keinen Sensor/Button zum
Andocken von Automationen – die Bedienung läuft ausschließlich über den
Such-Button in der Karte.

## Datenquelle

Diese Integration fragt `efa.vvs.de/vvs` direkt an – dasselbe Backend, das
auch die öffentliche Fahrplanauskunft-Website [efa.vvs.de](https://efa.vvs.de)
selbst für Haltestellensuche, Umkreissuche und Verbindungssuche verwendet. Da
es sich um das VVS-eigene, regionale System handelt (kein bundesweiter
Fernverkehrs-Aggregator), sind lokale Stadtbahn-, Straßenbahn- und Buslinien
darüber korrekt abgedeckt.

**Wichtiger Hinweis:** Dies ist die interne Schnittstelle der öffentlichen
Website, keine offiziell dokumentierte/lizenzierte Drittanbieter-API (eine
frühere Version dieser Integration nutzte [transport.rest](https://v6.db.transport.rest),
einen Wrapper um die HAFAS-API der Deutschen Bahn – diese zugrunde liegende
HAFAS-API wurde von der DB abgeschaltet, wodurch die Verbindungssuche
komplett ausfiel, weshalb diese Integration auf eine direkte VVS-Anfrage
umgestellt wurde). Die Schnittstelle kann sich jederzeit ohne Ankündigung
ändern oder eingeschränkt/blockiert werden. Anfragen erfolgen nur bei
Standortänderung und Button-Druck (nie per Timer), um die Last auf den
VVS-Servern gering zu halten. Sollte sich diese Schnittstelle als
unzuverlässig erweisen, wäre die offiziell lizenzierte Alternative die
[EFA-JSON-API / TRIAS-API von MobiData BW](https://mobidata-bw.de/dataset/trias)
(deckt ganz Baden-Württemberg ab, erfordert eine Registrierung).

## Datenschutz-Hinweis

Die GPS-Koordinaten des konfigurierten Geräts werden nur transient an
`efa.vvs.de` übertragen, um nahegelegene Haltestellen zu ermitteln – es
wird nichts darüber hinaus gespeichert, was Home Assistants eigene
`device_tracker`-Historie nicht ohnehin schon vorhält.

## Installation

### Über HACS (empfohlen)

1. In Home Assistant **HACS** öffnen
2. Drei-Punkte-Menü (oben rechts) → **Benutzerdefinierte Repositories**
3. `https://github.com/charly166/ha-dynconnections` als Repository-Typ
   **Integration** hinzufügen
4. In HACS nach **"HA DynConnections"** suchen und herunterladen
5. Home Assistant neu starten

### Manuell

1. Den Ordner `custom_components/ha_dynconnections` in das
   `custom_components`-Verzeichnis deiner Home-Assistant-Konfiguration
   kopieren:
   ```
   <config>/custom_components/ha_dynconnections/
   ```
2. Home Assistant neu starten

## 1. Integration aktivieren

**Einstellungen → Geräte & Dienste → Integration hinzufügen** → nach "HA
DynConnections" suchen → bestätigen. Es gibt keine Felder auszufüllen –
dieser Schritt aktiviert nur das Backend (und die Karte) für deine
Home-Assistant-Instanz.

## 2. Karte hinzufügen und Strecke konfigurieren

1. Dashboard bearbeiten → **Karte hinzufügen** → nach **"HA DynConnections"**
   suchen (oder ganz nach unten scrollen zu "Manuell" und
   `type: custom:ha-dynconnections-card` verwenden)
2. Im sich öffnenden Karten-Editor:
   - **Standort-Gerät** wählen (jeder `device_tracker` mit GPS-Koordinaten,
     typischerweise dein Handy über die Companion App)
   - **Zielhaltestelle suchen** per Name und die passende aus den
     Ergebnissen auswählen
   - Optional einen **Titel** setzen (Standard: "Nach `<Ziel>`")
3. Speichern. Die Karte zeigt ein Dropdown für die Abfahrtshaltestelle
   (automatisch befüllt aus dem aktuellen Standort deines Geräts), eine
   optionale Zeitwahl, einen Such-Button und darunter die Timetable.

Eine zweite Strecke (z.B. zur Arbeit statt nach Hause)? Einfach eine weitere
Karte hinzufügen und mit anderem Gerät/Ziel konfigurieren – ohne nochmal in
die Einstellungen zu müssen.

Die Karte registriert sich beim Setup automatisch als Lovelace-Dashboard-
Ressource (Storage-Modus-Dashboards). Nutzt dein Dashboard den alten
YAML-Modus, füge das manuell in `ui-lovelace.yaml` ein:
```yaml
resources:
  - url: /ha_dynconnections/ha-dynconnections-card.js?v=6
    type: module
```

## 3. Nutzung

1. Das Dropdown für die **Abfahrtshaltestelle** wird beim ersten Laden der
   Karte aus dem aktuellen Standort deines Geräts befüllt; über den
   ⟳-Button daneben nach einer Standortänderung aktualisieren
2. Optional eine **Wunsch-Abfahrtszeit** setzen (leer lassen für "jetzt")
3. **Suchen** drücken – die Karte zeigt die nächsten 5 Verbindungen
4. Bei einer Verbindung mit Umstieg auf die Umstiegsanzahl klicken, um die
   vollständige Reiseroute aufzuklappen (jede Etappe mit Haltestelle, Zeit
   und Gleis)

## Technische Hinweise

- Reine Python-Standardbibliothek + `aiohttp` (in Home Assistant bereits
  enthalten) – keine zusätzlichen pip-Pakete werden installiert
- Die Lovelace-Karte (inkl. ihres visuellen Editors) ist eine reine
  Vanilla-Web-Component ohne Build-Schritt und lädt keine externen
  Web-Fonts (nur Systemschriften); sie spricht ausschließlich über
  WebSocket-Befehle mit der Integration
  (`ha_dynconnections/search_stops`, `ha_dynconnections/nearby_stops`,
  `ha_dynconnections/search_journeys` - siehe `websocket_api.py`)
- `iot_class: cloud_polling` – Anfragen an `efa.vvs.de` erfolgen nur bei
  Standortänderung des Geräts (Haltestellen-Vorschläge) und bei Button-Druck
  (Verbindungssuche); es gibt kein periodisches Hintergrund-Polling für
  Verbindungen
- Streckenkonfiguration (Standort-Gerät, Zielhaltestelle) und Suchstatus
  leben komplett in der Karten-Konfiguration/-Laufzeit, nicht in
  Home-Assistant-Entitäten – siehe Trade-off unter "Funktionen"

## Ordnerstruktur

```
ha-dynconnections/
├── LICENSE                MIT-Lizenz
├── README.md / README.de.md
├── hacs.json               HACS-Metadaten
├── .github/workflows/      HACS- + hassfest-Validierung
├── docs/logo.png           Vollständiges Logo für README/Repo
└── custom_components/ha_dynconnections/
    ├── __init__.py          Setup, statische Dateiauslieferung
    ├── api.py                Schlanker Client für das VVS-EFA-Backend
    ├── brand/                 Lokale Icons für "Geräte & Dienste" (HA 2026.3+)
    │   ├── icon.png / icon@2x.png
    │   └── logo.png / logo@2x.png
    ├── config_flow.py        Einziger, feldloser Bestätigungsschritt
    ├── const.py
    ├── frontend.py            Automatische Lovelace-Ressourcen-Registrierung
    ├── manifest.json
    ├── strings.json / translations/
    ├── websocket_api.py       Backend für die Karte (Haltestellensuche, Umkreissuche, Verbindungssuche)
    └── www/
        └── ha-dynconnections-card.js    Lovelace-Karte + ihr visueller Editor (GUI)
```

## Mindestanforderungen

- Home Assistant **2024.12.0** oder neuer

## Lizenz

MIT – siehe [LICENSE](LICENSE) für Details.
