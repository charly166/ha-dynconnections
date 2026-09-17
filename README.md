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
destination stop and location device are picked directly in the card's own
editor, and the actual search for the next 5 connections is triggered by a
button press – no background polling.

Built with the **Region Stuttgart (VVS)** as the initial target area, using
the same EFA (Elektronische Fahrplanauskunft) backend that powers
[efa.vvs.de](https://efa.vvs.de), the VVS's own public journey planner, as
its data source.

## Features

- **Everything configured in the card itself** – no Settings dialog per
  route: add the card, pick a location device and search for a destination
  stop right in the card's visual editor
- **Multiple routes** – just add another card with a different device/
  destination combination (e.g. "home" and "work"); no extra setup steps
- **Departure stop suggestions** based on the live GPS location of the
  configured `device_tracker` (e.g. your phone via the Companion App),
  shown as a dropdown with a manual refresh button; each stop shows small
  badges for the modes serving it (S-Bahn, U-Bahn/Stadtbahn, bus, regional
  train), like on vvs.de's own stop search – same badges appear next to
  destination search results in the card editor
- **Optional desired departure time** – leave empty to search from "now"
  (shown as a hint next to the field)
- **Search button** – connections are only looked up when you actually want
  them, not on a timer
- **Next 5 connections** rendered directly in the card as a timetable
  (line with a mode icon – S-Bahn, Stadtbahn/U-Bahn, bus, regional/express
  train, etc. –, direction, departure incl. delay, platform, arrival,
  transfers, duration)
- **Full itinerary on demand**: connections with a transfer can be expanded
  to show every leg (line, direction, stop, time, platform) plus any
  walking connections between platforms
- No account/API key needed – the EFA endpoint is free and unauthenticated

**Note:** since routes live entirely in card configuration (not in Home
Assistant entities), there's currently no sensor/button to hook into
automations – everything is driven by pressing the search button in the
card.

## Data source

This integration queries `efa.vvs.de/vvs` directly – the same backend the
public [efa.vvs.de](https://efa.vvs.de) journey planner website itself uses
for stop search, nearby-stop lookup, and trip planning. Since it's VVS's own
regional system (not a nationwide long-distance aggregator), it covers local
Stadtbahn, tram, and bus lines properly.

**Caveat:** this is the internal endpoint of the public website, not an
officially documented/licensed third-party API (an earlier version of this
integration used [transport.rest](https://v6.db.transport.rest), a wrapper
around Deutsche Bahn's HAFAS API – that underlying HAFAS API was shut off by
DB, breaking journey search entirely, which is why this integration switched
to querying VVS directly). It could change or be rate-limited/blocked without
notice. Requests only happen on device-location change and button press
(never on a timer), to keep load on VVS's servers minimal. If this endpoint
ever becomes unreliable, the officially licensed alternative is the
[EFA-JSON-API / TRIAS-API from MobiData BW](https://mobidata-bw.de/dataset/trias)
(covers all of Baden-Württemberg, requires registering for access).

## Privacy note

The configured device's GPS coordinates are sent to `efa.vvs.de` only
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

## 1. Enable the integration

**Settings → Devices & Services → Add Integration** → search for "HA
DynConnections" → confirm. There are no fields to fill in – this step just
activates the backend (and the card) for your Home Assistant instance.

## 2. Add the card and configure your route

1. Edit dashboard → **Add Card** → search for **"HA DynConnections"** (or
   scroll to Manual and use `type: custom:ha-dynconnections-card`)
2. In the card editor that opens:
   - Pick your **location device** (any `device_tracker` with GPS
     coordinates, typically your phone via the Companion App)
   - **Search for your destination stop** by name and pick the correct one
     from the results
   - Optionally set a **title** (defaults to "Nach `<destination>`")
3. Save. The card shows a departure-stop dropdown (auto-populated from your
   device's current location), an optional time picker, a search button,
   and the resulting timetable.

Want a second route (e.g. to work instead of home)? Just add another card
and configure it with a different device/destination – no need to touch
Settings again.

The card registers itself as a Lovelace dashboard resource automatically on
setup (storage-mode dashboards). If your dashboard uses legacy YAML mode,
add this manually to `ui-lovelace.yaml`:
```yaml
resources:
  - url: /ha_dynconnections/ha-dynconnections-card.js?v=5
    type: module
```

## 3. Usage

1. The **departure stop** dropdown is populated from your device's current
   location when the card first loads; use the ⟳ button next to it to
   refresh after moving
2. Optionally set a **desired departure time** (leave empty for "now")
3. Press **search** – the card shows the next 5 connections
4. For a connection with a transfer, click the transfer count to expand the
   full itinerary (every leg with its stop, time, and platform)

## Technical Notes

- Pure Python standard library + `aiohttp` (already bundled with Home
  Assistant) – no extra pip packages are installed
- The Lovelace card (including its visual editor) is a plain Vanilla Web
  Component, no build step, and loads no external web fonts (system fonts
  only); it talks to the integration exclusively via WebSocket commands
  (`ha_dynconnections/search_stops`, `ha_dynconnections/nearby_stops`,
  `ha_dynconnections/search_journeys`) - see `websocket_api.py`
- `iot_class: cloud_polling` – requests to `efa.vvs.de` only happen on
  device-location change (nearby-stop lookup) and on button press (journey
  search); there is no periodic background polling for connections
- Route configuration (location device, destination stop) and search state
  live entirely in the card's own config/runtime state, not in Home
  Assistant entities – see "Features" above for the trade-off

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
    ├── api.py                Slim client for VVS's EFA backend
    ├── brand/                 Local icons for "Devices & Services" (HA 2026.3+)
    │   ├── icon.png / icon@2x.png
    │   └── logo.png / logo@2x.png
    ├── config_flow.py        Single, field-less confirmation step
    ├── const.py
    ├── frontend.py            Automatic Lovelace resource registration
    ├── manifest.json
    ├── strings.json / translations/
    ├── websocket_api.py       Backend for the card (stop search, nearby stops, journeys)
    └── www/
        └── ha-dynconnections-card.js    Lovelace card + its visual editor (GUI)
```

## Minimum Requirements

- Home Assistant **2024.12.0** or newer

## License

MIT – see [LICENSE](LICENSE) for details.
