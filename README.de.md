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
Companion App), die Zielhaltestelle ist in den Einstellungen fest hinterlegt,
und die eigentliche Suche nach den nächsten 5 Verbindungen wird per
Button-Druck ausgelöst – kein Hintergrund-Polling.

Gebaut mit der **Region Stuttgart (VVS)** als erstem Zielgebiet, als
Datenquelle dient dasselbe EFA-Backend (Elektronische Fahrplanauskunft), das
auch [efa.vvs.de](https://efa.vvs.de), die offizielle VVS-Fahrplanauskunft,
selbst nutzt.

## Funktionen

- **Vorschläge für die Abfahrtshaltestelle** basierend auf dem Live-Standort
  eines beliebigen `device_tracker` (z.B. dein Handy über die Companion App)
  – als Dropdown (`select`-Entität), aktualisiert sich automatisch bei
  Standortänderung
- **Feste Zielhaltestelle**, einmalig bei der Einrichtung per Namenssuche
  festgelegt, später änderbar über Einstellungen → Geräte & Dienste → HA
  DynConnections → Konfigurieren
- **Optionale Wunsch-Abfahrtszeit** (`datetime`-Entität) – leer lassen für
  eine Suche ab "jetzt"
- **Such-Button** (`button`-Entität) – Verbindungen werden nur abgefragt,
  wenn du es willst, nicht per Timer
- **Die nächsten 5 Verbindungen** als Sensor mit `connections`-Attribut
  (Linie, Richtung, Abfahrt inkl. Verspätung, Gleis, Ankunft, Umstiege,
  Dauer), dazu eine mitgelieferte Lovelace-Karte, die daraus eine echte
  Timetable rendert
- Mehrere konfigurierte Strecken möglich (z.B. "nach Hause" und "zur
  Arbeit") – jede ist eine eigene Config Entry mit eigenen Entitäten
- Kein Account/API-Key nötig – die EFA-Schnittstelle ist kostenlos und ohne
  Authentifizierung nutzbar

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

## 1. Integration einrichten

**Einstellungen → Geräte & Dienste → Integration hinzufügen** → nach "HA
DynConnections" suchen:

1. **Standort-Gerät** wählen – jede `device_tracker`-Entität mit
   GPS-Koordinaten, typischerweise dein Handy über die Companion App
   (`device_tracker.<dein_handy>`)
2. **Zielhaltestelle** per Namenssuche finden, dann die passende aus den
   Ergebnissen auswählen

## 2. Karte zum Dashboard hinzufügen

1. Dashboard bearbeiten → **Karte hinzufügen** → ganz nach unten scrollen →
   **Manuell**
2. Einfügen (Entity-IDs an die für deine Config Entry erzeugten anpassen –
   zu finden unter Einstellungen → Geräte & Dienste → HA DynConnections →
   Geräteseite):
   ```yaml
   type: custom:ha-dynconnections-card
   title: Nach Hause
   origin_entity: select.nach_hause_abfahrtshaltestelle
   datetime_entity: datetime.nach_hause_gewunschte_abfahrtszeit
   button_entity: button.nach_hause_verbindung_suchen
   sensor_entity: sensor.nach_hause_nachste_verbindungen
   ```
3. Speichern. Die Karte zeigt ein Dropdown für die Abfahrtshaltestelle, eine
   optionale Zeitwahl, einen Such-Button und darunter die Timetable.

Die Karte registriert sich beim Setup automatisch als Lovelace-Dashboard-
Ressource (Storage-Modus-Dashboards). Nutzt dein Dashboard den alten
YAML-Modus, füge das manuell in `ui-lovelace.yaml` ein:
```yaml
resources:
  - url: /ha_dynconnections/ha-dynconnections-card.js?v=1
    type: module
```

**Auch ohne die Karte** funktionieren alle vier Entitäten (`select`,
`datetime`, `button`, `sensor`) einzeln und können in eine normale
Entities-Karte gelegt werden – nur die Timetable als Tabelle bekommst du
ohne diese Karte (oder eine separate Community-Karte, z.B. eine
Markdown-Karte mit Jinja-Template über das `connections`-Attribut, oder
eine "flex-table-card") nicht angezeigt.

## 3. Nutzung

1. Das Dropdown für die **Abfahrtshaltestelle** aktualisiert sich automatisch
   bei Standortänderung deines Handys; bei mehreren nahegelegenen
   Haltestellen die passende auswählen
2. Optional eine **Wunsch-Abfahrtszeit** setzen
3. **Suchen** drücken – der Sensor aktualisiert sich mit den nächsten 5
   Verbindungen

## Automatisierungs-Beispiel

```yaml
automation:
  - alias: "Verbindung beim Verlassen einer Zone aktualisieren"
    trigger:
      - platform: zone
        entity_id: device_tracker.dein_handy
        zone: zone.home
        event: leave
    action:
      - service: button.press
        target:
          entity_id: button.nach_hause_verbindung_suchen
```

## Technische Hinweise

- Reine Python-Standardbibliothek + `aiohttp` (in Home Assistant bereits
  enthalten) – keine zusätzlichen pip-Pakete werden installiert
- Die Lovelace-Karte ist eine reine Vanilla-Web-Component ohne Build-Schritt
  und lädt keine externen Web-Fonts (nur Systemschriften)
- `iot_class: cloud_polling` – Anfragen an `efa.vvs.de` erfolgen nur bei
  Standortänderung des Geräts (Haltestellen-Vorschläge) und bei Button-Druck
  (Verbindungssuche); es gibt kein periodisches Hintergrund-Polling für
  Verbindungen
- Der Coordinator nutzt `update_interval=None` – er aktualisiert sich nie von
  selbst, nur über den Such-Button (oder dessen `button.press`-Service, z.B.
  aus einer Automation)

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
    ├── button.py              Such-Auslöser-Entität
    ├── config_flow.py        Einrichtungsdialog (Standort-Gerät + Zielsuche) + Options-Flow
    ├── const.py
    ├── coordinator.py        Nur-manuell-Refresh-Coordinator (Verbindungssuche)
    ├── datetime.py            Wunsch-Abfahrtszeit-Entität
    ├── frontend.py            Automatische Lovelace-Ressourcen-Registrierung
    ├── manifest.json
    ├── select.py              Abfahrtshaltestellen-Dropdown (aktualisiert sich per Standort)
    ├── sensor.py              Ergebnis-Entität für die nächsten 5 Verbindungen
    ├── strings.json / translations/
    └── www/
        └── ha-dynconnections-card.js    Lovelace-Karte (GUI)
```

## Mindestanforderungen

- Home Assistant **2024.12.0** oder neuer (der Options-Flow nutzt die
  `config_entry`-Property, die Home Assistant Core Config-Flows seit dieser
  Version automatisch bereitstellt)

## Lizenz

MIT – siehe [LICENSE](LICENSE) für Details.
