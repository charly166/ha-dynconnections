# HA DynConnections – Home Assistant Custom Integration

<p align="center">
  <img src="docs/logo.png" alt="HA DynConnections Logo" width="360">
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="hacs_badge"></a>
  <a href="https://github.com/charly166/ha-dynconnections/releases"><img src="https://img.shields.io/github/v/release/charly166/ha-dynconnections" alt="GitHub Release"></a>
  <a href="https://github.com/charly166/ha-dynconnections/blob/main/LICENSE"><img src="https://img.shields.io/github/license/charly166/ha-dynconnections" alt="License"></a>
</p>

[Deutsche Version / German version](README.de.md)

---

A Home Assistant custom integration with its own Lovelace card for dynamic
public-transport connection lookups: your departure stop is suggested based
on a smartphone's live location (via the Home Assistant Companion App), your
destination stop is fixed in the integration's settings, and the actual
search for the next 5 connections is triggered by a button press – no
background polling.

Built with the **Region Stuttgart (VVS)** as the initial target area, using
the free [transport.rest](https://v6.db.transport.rest) API (Deutsche Bahn
HAFAS data) as its data source.

## Features

- **Departure stop suggestions** based on the live GPS location of any
  `device_tracker` entity (e.g. your phone via the Companion App) – shown as
  a dropdown (`select` entity), refreshed automatically whenever the device
  moves
- **Fixed destination stop**, chosen once during setup by searching its name,
  changeable later via Settings → Devices & Services → HA DynConnections →
  Configure
- **Optional desired departure time** (`datetime` entity) – leave empty to
  search from "now"
- **Search button** (`button` entity) – connections are only looked up when
  you actually want them, not on a timer
- **Next 5 connections** as a sensor with a `connections` attribute (line,
  direction, departure incl. delay, platform, arrival, transfers, duration),
  plus a bundled Lovelace card that renders it as a proper timetable
- Multiple configured routes supported (e.g. "home" and "work") – each is a
  separate config entry with its own set of entities
- No account/API key needed – transport.rest is free and unauthenticated

**Known limitation:** transport.rest is built on Deutsche Bahn's HAFAS `db`
profile, which officially covers "long-distance and regional traffic, plus
some local buses" (comparable to the DB Navigator app). Purely local VVS
tram/Stadtbahn or bus lines may not always be fully covered. If this turns
out to be a real gap for your routes, swapping `api.py`'s `TransportRestClient`
for a VVS-specific EFA client is the intended extension point – not built
here to keep the initial scope focused.

## Privacy note

The configured device's GPS coordinates are sent to transport.rest only
transiently, to look up nearby stops – nothing is stored beyond what Home
Assistant's own `device_tracker` history already retains.

## Installation

### Via HACS (recommended)

1. In Home Assistant, open **HACS**
2. Click the three-dot menu (top right) → **Custom repositories**
3. Add `https://github.com/charly166/ha-dynconnections` as repository type
   **Integration**
4. Search for **"HA DynConnections"** in HACS and download it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/ha_dynconnections` folder into your Home
   Assistant configuration's `custom_components` directory:
   ```
   <config>/custom_components/ha_dynconnections/
   ```
2. Restart Home Assistant

## 1. Set up the integration

**Settings → Devices & Services → Add Integration** → search for "HA
DynConnections":

1. Pick the **location device** – any `device_tracker` entity with GPS
   coordinates, typically your phone via the Companion App
   (`device_tracker.<your_phone>`)
2. Search for your **destination stop** by name, then pick the correct one
   from the results

## 2. Add the card to your dashboard

1. Edit dashboard → **Add Card** → scroll to the bottom → **Manual**
2. Paste (adjust the entity IDs to the ones created for your config entry –
   find them under Settings → Devices & Services → HA DynConnections →
   the device page):
   ```yaml
   type: custom:ha-dynconnections-card
   title: Nach Hause
   origin_entity: select.nach_hause_abfahrtshaltestelle
   datetime_entity: datetime.nach_hause_gewunschte_abfahrtszeit
   button_entity: button.nach_hause_verbindung_suchen
   sensor_entity: sensor.nach_hause_nachste_verbindungen
   ```
3. Save. The card shows a departure-stop dropdown, an optional time picker,
   a search button, and the resulting timetable.

The card registers itself as a Lovelace dashboard resource automatically on
setup (storage-mode dashboards). If your dashboard uses legacy YAML mode,
add this manually to `ui-lovelace.yaml`:
```yaml
resources:
  - url: /ha_dynconnections/ha-dynconnections-card.js?v=1
    type: module
```

**Without the card**, all four entities (`select`, `datetime`, `button`,
`sensor`) still work individually and can be placed in a normal Entities
card – you just won't get the timetable rendered as a table without either
this card or a separate community card (e.g. a Markdown card with a Jinja
template iterating the sensor's `connections` attribute, or a
"flex-table-card" pointed at that attribute).

## 3. Usage

1. The **departure stop** dropdown updates automatically as your phone
   moves; pick the correct one if several are nearby
2. Optionally set a **desired departure time**
3. Press **search** – the sensor updates with the next 5 connections

## Automation example

```yaml
automation:
  - alias: "Refresh connections when leaving a zone"
    trigger:
      - platform: zone
        entity_id: device_tracker.your_phone
        zone: zone.home
        event: leave
    action:
      - service: button.press
        target:
          entity_id: button.nach_hause_verbindung_suchen
```

## Technical Notes

- Pure Python standard library + `aiohttp` (already bundled with Home
  Assistant) – no extra pip packages are installed
- The Lovelace card is a plain Vanilla Web Component, no build step, and
  loads no external web fonts (system fonts only)
- `iot_class: cloud_polling` – requests to transport.rest only happen on
  device-location change (nearby-stop lookup) and on button press (journey
  search); there is no periodic background polling for connections
- Coordinator uses `update_interval=None` – it never refreshes on its own,
  only via the search button (or its `button.press` service, e.g. from an
  automation)

## Folder structure

```
ha-dynconnections/
├── LICENSE                MIT license
├── README.md / README.de.md
├── hacs.json               HACS metadata
├── .github/workflows/      HACS + hassfest validation
├── docs/logo.png           Full logo for README/repo
└── custom_components/ha_dynconnections/
    ├── __init__.py          Setup, static file serving
    ├── api.py                Slim transport.rest client
    ├── button.py              Search-trigger entity
    ├── config_flow.py        Setup dialog (location device + destination search) + options flow
    ├── const.py
    ├── coordinator.py        Manual-refresh-only coordinator (journey search)
    ├── datetime.py            Desired departure time entity
    ├── frontend.py            Automatic Lovelace resource registration
    ├── manifest.json
    ├── select.py              Departure-stop dropdown (updates from device location)
    ├── sensor.py              Next-5-connections result entity
    ├── strings.json / translations/
    └── www/
        └── ha-dynconnections-card.js    Lovelace card (GUI)
```

## Minimum Requirements

- Home Assistant **2024.12.0** or newer (the options flow relies on the
  `config_entry` property Home Assistant core provides to config flows since
  that release)

## License

MIT – see [LICENSE](LICENSE) for details.
