// HA DynConnections – Lovelace-Karte (Vanilla Web Component, kein Build-Schritt).
//
// Bewusst kein externes Web-Font geladen (System-Fonts reichen), um keine
// unnötigen Drittanbieter-Requests von Besuchern auszulösen.
//
// Die gesamte Konfiguration (Standort-Gerät, Zielhaltestelle) passiert im
// visuellen Karten-Editor (HaDynConnectionsCardEditor weiter unten) - nicht
// mehr über feste Entity-IDs. Card-Konfiguration:
//   type: custom:ha-dynconnections-card
//   device_tracker: device_tracker.xxx
//   destination_id: "5006075"
//   destination_name: "Charlottenplatz"
//   title: "Nach Hause"   # optional
//
// Laufzeitstatus (gewählte Abfahrtshaltestelle, letzte Suchergebnisse) lebt
// bewusst nur im Arbeitsspeicher der Karte, nicht persistiert - bleibt beim
// Neuladen des Dashboards einfach zurückgesetzt.

const DOMAIN = "ha_dynconnections";

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function formatTime(iso) {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function delayHtml(minutes) {
  return minutes ? ` <span class="delay">+${minutes}</span>` : "";
}

// Hebt das Gleis farblich hervor, wenn es vom ursprünglich geplanten
// abweicht (Gleiswechsel), mit dem geplanten Gleis als Tooltip.
function platformHtml(platform, plannedPlatform) {
  if (!platform) return "-";
  if (!plannedPlatform || plannedPlatform === platform) return escapeHtml(platform);
  return `<span class="platform-changed" title="Ursprünglich geplant: ${escapeHtml(plannedPlatform)}">${escapeHtml(platform)}</span>`;
}

// Kleine farbige Verkehrsmittel-Badges, angelehnt an die auf vvs.de/
// efa.vvs.de selbst verwendete Farbgebung (grüner Kreis "S" für S-Bahn,
// blau für Stadtbahn/U-Bahn, rot für Bus) - eigene Nachbildung des Stils,
// keine übernommenen Grafiken. Werden sowohl für die Haltestellenauswahl
// (Kategorien aus api.py's _stop_modes()/EFAs STOP_MOT_LIST) als auch für
// die Linien in der Verbindungs-Tabelle verwendet (siehe lineModeCategory()),
// damit beide dieselbe visuelle Sprache sprechen.
const MODE_BADGES = {
  sbahn: { label: "S", bg: "#00a650" },
  ubahn: { label: "U", bg: "#0075bf" },
  stadtbahn: { label: "U", bg: "#0075bf" },
  tram: { label: "T", bg: "#0075bf" },
  bus: { label: "BUS", bg: "#e30613" },
  zug: { label: "R", bg: "#6e6e6e" },
  seilbahn: { icon: "mdi:gondola", bg: "#6e6e6e" },
  schiff: { icon: "mdi:ferry", bg: "#0075bf" },
};

function modeBadgesHtml(modes) {
  return (modes || [])
    .map((m) => MODE_BADGES[m])
    .filter(Boolean)
    .map((b) =>
      b.label
        ? `<span class="mode-badge" style="background:${b.bg}">${b.label}</span>`
        : `<span class="mode-badge" style="background:${b.bg}"><ha-icon icon="${b.icon}"></ha-icon></span>`
    )
    .join("");
}

// Ordnet eine Linie derselben Badge-Kategorie wie die Haltestellenauswahl
// zu. Primär anhand des EFA "product"-Felds (z.B. "S-Bahn", "Stadtbahn",
// "Bus", "Nachtbus") - das ist zuverlässiger als der Linienname, dessen
// Format "<Produkt> <Code>" ist (z.B. "S-Bahn S1", "R-Bahn RE14").
// Regionalzüge (RE/RB/MEX) und Fernverkehr (ICE/IC/EC) teilen sich bei EFA
// oft dasselbe generische Produkt ("R-Bahn"/"Zug") und werden - wie schon
// bei den Haltestellen-Badges - in derselben grauen "R"-Kategorie
// zusammengefasst, statt eine eigene Fernverkehr-Kategorie zu erfinden.
function lineModeCategory(line, product) {
  const p = (product || "").toLowerCase();
  const tokens = (line || "").toUpperCase().split(/\s+/);

  if (p === "s-bahn") return "sbahn";
  if (p === "stadtbahn") return "stadtbahn";
  if (p === "nachtbus" || p.includes("sev") || p.includes("bus")) return "bus";
  if (p === "fussweg") return null;
  if (tokens.some((t) => /^(ICE|IC|EC)\d*$/.test(t))) return "zug";
  if (p === "r-bahn" || p === "zug" || tokens.some((t) => /^(MEX|RE|RB|IRE)\d*$/.test(t))) return "zug";
  return null;
}

function lineBadgeHtml(line, product) {
  return modeBadgesHtml([lineModeCategory(line, product)]);
}

class HaDynConnectionsCard extends HTMLElement {
  constructor() {
    super();
    this._handleOutsideClick = this._handleOutsideClick.bind(this);
  }

  disconnectedCallback() {
    window.removeEventListener("click", this._handleOutsideClick);
  }

  _handleOutsideClick() {
    if (this._originListOpen) {
      this._originListOpen = false;
      this._render();
    }
  }

  setConfig(config) {
    const next = config || {};
    if (this._config && JSON.stringify(this._config) === JSON.stringify(next)) {
      return;
    }
    this._config = next;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._originStops = this._originStops || [];
    this._selectedOriginId = this._selectedOriginId || null;
    this._connections = this._connections || [];
    this._departureValue = this._departureValue || "";
    this._expandedRows = this._expandedRows || new Set();
    this._originListOpen = this._originListOpen || false;
    this._render();
  }

  set hass(hass) {
    // Bewusst NUR beim allerersten Zuweisen neu rendern: Home Assistant
    // ruft diesen Setter sehr häufig auf (bei praktisch jeder
    // Zustandsänderung irgendwo im System), nicht nur bei tatsächlich für
    // diese Karte relevanten Änderungen. Ein Re-Render bei jedem Aufruf
    // würde das komplette Shadow-DOM neu aufbauen und dabei z.B. ein
    // gerade geöffnetes Zeit-Auswahlfeld schließen/den Fokus verlieren.
    // Alle für die Anzeige relevanten Daten (Haltestellen, Ergebnisse)
    // liegen ohnehin in explizitem State, der nur durch Nutzeraktionen
    // (Button-Klicks) aktualisiert wird - ein reaktives Re-Render bei
    // jedem hass-Update ist dafür nicht nötig.
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._render();
      if (this._config?.device_tracker) {
        this._refreshNearbyStops();
      }
    }
  }

  static getConfigElement() {
    return document.createElement("ha-dynconnections-card-editor");
  }

  static getStubConfig() {
    return {};
  }

  getCardSize() {
    return 5;
  }

  async _refreshNearbyStops() {
    const trackerState = this._hass.states[this._config.device_tracker];
    const lat = trackerState?.attributes?.latitude;
    const lon = trackerState?.attributes?.longitude;
    if (lat == null || lon == null) {
      this._stopsError = "Das gewählte Gerät liefert aktuell keinen Standort.";
      this._render();
      return;
    }
    this._stopsError = null;
    this._loadingStops = true;
    this._render();
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: `${DOMAIN}/nearby_stops`,
        latitude: lat,
        longitude: lon,
      });
      this._originStops = result.stops || [];
      if (!this._originStops.some((s) => s.id === this._selectedOriginId)) {
        this._selectedOriginId = this._originStops[0]?.id || null;
      }
    } catch (err) {
      this._stopsError = err.message || "Haltestellen konnten nicht geladen werden.";
    } finally {
      this._loadingStops = false;
      this._render();
    }
  }

  async _search() {
    if (!this._selectedOriginId || !this._config.destination_id) {
      return;
    }
    this._searching = true;
    this._searchError = null;
    this._render();
    try {
      const departure = this._departureValue ? new Date(this._departureValue).toISOString() : undefined;
      const result = await this._hass.connection.sendMessagePromise({
        type: `${DOMAIN}/search_journeys`,
        origin_id: this._selectedOriginId,
        destination_id: this._config.destination_id,
        ...(departure ? { departure } : {}),
      });
      this._connections = result.connections || [];
      this._expandedRows = new Set();
    } catch (err) {
      this._searchError = err.message || "Verbindungssuche fehlgeschlagen.";
    } finally {
      this._searching = false;
      this._render();
    }
  }

  _render() {
    if (!this._hass || !this._config) {
      return;
    }

    if (!this._config.device_tracker || !this._config.destination_id) {
      this.shadowRoot.innerHTML = `
        <style>${HaDynConnectionsCard._styles()}</style>
        <ha-card>
          <div class="card-content">
            <p class="empty">Bitte im Karten-Editor ein Standort-Gerät und eine Zielhaltestelle wählen (Dashboard bearbeiten → Karte bearbeiten).</p>
          </div>
        </ha-card>
      `;
      return;
    }

    const title = this._config.title || `Nach ${this._config.destination_name || "?"}`;
    const selectedStop = this._originStops.find((s) => s.id === this._selectedOriginId);
    const toggleLabel = this._loadingStops
      ? "Lädt…"
      : selectedStop
        ? escapeHtml(selectedStop.name)
        : "– keine Haltestelle –";

    this.shadowRoot.innerHTML = `
      <style>${HaDynConnectionsCard._styles()}</style>
      <ha-card>
        <div class="header">${escapeHtml(title)}</div>
        <div class="card-content">
          ${this._stopsError ? `<p class="error">${escapeHtml(this._stopsError)}</p>` : ""}
          <div class="controls">
            <!-- Bewusst <div>, nicht <label>: ein <label>, das einen Button
                 umschließt, leitet jeden Klick irgendwo im Label (auch auf
                 die Listeneinträge weiter unten) zusätzlich als synthetischen
                 Klick an diesen Button weiter - das öffnete die Liste sofort
                 wieder, direkt nachdem ein Eintrag sie geschlossen hatte. -->
            <div class="field">
              Von
              <span class="row">
                <div class="combobox">
                  <button type="button" id="origin-toggle" class="combobox-toggle" ${this._loadingStops ? "disabled" : ""}>
                    <span class="stop-name">${toggleLabel}</span>
                    ${selectedStop ? modeBadgesHtml(selectedStop.modes) : ""}
                    <span class="caret">▾</span>
                  </button>
                  ${
                    this._originListOpen
                      ? `<ul class="combobox-list">
                          ${this._originStops
                            .map(
                              (stop) => `
                            <li data-id="${escapeHtml(stop.id)}" class="${stop.id === this._selectedOriginId ? "selected" : ""}">
                              <span class="stop-name">${escapeHtml(stop.name)}</span> ${modeBadgesHtml(stop.modes)}
                            </li>`
                            )
                            .join("")}
                        </ul>`
                      : ""
                  }
                </div>
                <button id="refresh" title="Haltestellen neu laden" ${this._loadingStops ? "disabled" : ""}>⟳</button>
              </span>
            </div>
            <label>
              Abfahrt <span class="hint">(leer = jetzt)</span>
              <input id="departure" type="datetime-local" value="${escapeHtml(this._departureValue)}" />
            </label>
            <button id="search" ${this._searching || !this._selectedOriginId ? "disabled" : ""}>
              ${this._searching ? "Suche läuft…" : "Verbindung suchen"}
            </button>
          </div>
          ${this._searchError ? `<p class="error">${escapeHtml(this._searchError)}</p>` : ""}
          ${this._renderTable()}
        </div>
      </ha-card>
    `;

    window.removeEventListener("click", this._handleOutsideClick);

    const originToggle = this.shadowRoot.getElementById("origin-toggle");
    if (originToggle) {
      originToggle.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._originListOpen = !this._originListOpen;
        this._render();
      });
    }
    this.shadowRoot.querySelectorAll(".combobox-list li").forEach((li) => {
      li.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._selectedOriginId = li.dataset.id;
        this._originListOpen = false;
        this._render();
      });
    });
    if (this._originListOpen) {
      window.addEventListener("click", this._handleOutsideClick);
    }

    this.shadowRoot.getElementById("refresh").addEventListener("click", () => this._refreshNearbyStops());
    this.shadowRoot.getElementById("departure").addEventListener("change", (ev) => {
      this._departureValue = ev.target.value;
    });
    this.shadowRoot.getElementById("search").addEventListener("click", () => this._search());

    this.shadowRoot.querySelectorAll(".toggle-details").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.dataset.idx);
        if (this._expandedRows.has(idx)) {
          this._expandedRows.delete(idx);
        } else {
          this._expandedRows.add(idx);
        }
        this._render();
      });
    });
  }

  _renderTable() {
    if (!this._connections.length) {
      return `<p class="empty">Noch keine Suche gestartet oder keine Verbindungen gefunden.</p>`;
    }
    const rows = this._connections
      .map((c, idx) => {
        const legCount = (c.legs || []).filter((l) => !l.walking).length;
        const expanded = this._expandedRows.has(idx);
        const transfersCell =
          legCount > 1
            ? `<button class="toggle-details" data-idx="${idx}">${c.transfers ?? legCount - 1} ${expanded ? "▲" : "▼"}</button>`
            : `${c.transfers ?? 0}`;

        return `
        <tr>
          <td>${lineBadgeHtml(c.line, c.product)} ${escapeHtml(c.line || "-")}</td>
          <td>${escapeHtml(c.direction || "-")}</td>
          <td>${formatTime(c.departure)}${delayHtml(c.delay_minutes)}</td>
          <td>${platformHtml(c.platform, c.planned_platform)}</td>
          <td>${formatTime(c.arrival)}${delayHtml(c.arrival_delay_minutes)}</td>
          <td>${transfersCell}</td>
          <td>${c.duration_minutes != null ? `${c.duration_minutes} min` : "-"}</td>
        </tr>
        ${expanded ? `<tr class="details-row"><td colspan="7">${this._renderItinerary(c.legs || [])}</td></tr>` : ""}`;
      })
      .join("");

    return `
      <table>
        <thead>
          <tr>
            <th>Linie</th><th>Richtung</th><th>Abfahrt</th><th>Gleis</th><th>Ankunft</th><th>Umst.</th><th>Dauer</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  _renderItinerary(legs) {
    const steps = legs.map((leg) => {
      if (leg.walking) {
        const duration = leg.duration_minutes != null ? ` (${leg.duration_minutes} min)` : "";
        return `<div class="leg walk"><ha-icon icon="mdi:walk"></ha-icon> Fußweg${duration}</div>`;
      }
      return `
        <div class="leg">
          <div class="leg-line">${lineBadgeHtml(leg.line, leg.product)} <strong>${escapeHtml(leg.line || "-")}</strong> Richtung ${escapeHtml(leg.direction || "-")}</div>
          <div class="leg-stop">ab <strong>${escapeHtml(leg.departure_stop || "-")}</strong> ${formatTime(leg.departure)}${delayHtml(leg.delay_minutes)}${leg.departure_platform ? ` (${platformHtml(leg.departure_platform, leg.planned_departure_platform)})` : ""}</div>
          <div class="leg-stop">an <strong>${escapeHtml(leg.arrival_stop || "-")}</strong> ${formatTime(leg.arrival)}${delayHtml(leg.arrival_delay_minutes)}${leg.arrival_platform ? ` (${platformHtml(leg.arrival_platform, leg.planned_arrival_platform)})` : ""}</div>
        </div>`;
    });
    return `<div class="itinerary">${steps.join("")}</div>`;
  }

  static _styles() {
    return `
      .header { font-size: 1.2em; font-weight: 500; padding: 16px 16px 0; color: var(--primary-text-color); }
      .card-content { padding: 16px; font-family: var(--paper-font-body1_-_font-family, inherit); }
      .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 16px; }
      label, .field { display: flex; flex-direction: column; font-size: 0.85em; color: var(--secondary-text-color); gap: 4px; }
      .hint { font-weight: normal; font-style: italic; opacity: 0.8; }
      .row { display: flex; gap: 4px; align-items: start; }
      select, input, button { font: inherit; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
      button { cursor: pointer; background: var(--primary-color); color: var(--text-primary-color, #fff); border: none; padding: 8px 14px; }
      button:disabled { opacity: 0.6; cursor: default; }
      #refresh { padding: 6px 10px; }
      .combobox { position: relative; }
      .combobox-toggle { display: flex; align-items: center; gap: 6px; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); min-width: 160px; text-align: left; }
      .combobox-toggle .stop-name { flex: 1; }
      .combobox-toggle .caret { opacity: 0.6; }
      .combobox-list { position: absolute; z-index: 5; top: calc(100% + 2px); left: 0; min-width: 220px; margin: 0; padding: 4px 0; list-style: none; background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 6px; box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,0.2)); max-height: 240px; overflow-y: auto; }
      .combobox-list li { display: flex; align-items: center; gap: 6px; padding: 8px 10px; cursor: pointer; }
      .combobox-list li .stop-name { flex: 1; }
      .combobox-list li:hover, .combobox-list li.selected { background: var(--secondary-background-color, rgba(0,0,0,0.06)); }
      .mode-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 4px; color: #fff; font-size: 0.7em; font-weight: 700; line-height: 1; }
      .mode-badge ha-icon { --mdc-icon-size: 13px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--divider-color); font-size: 0.9em; }
      th { color: var(--secondary-text-color); font-weight: 500; }
      .delay { color: var(--error-color, #db4437); font-weight: 600; }
      .platform-changed { color: var(--error-color, #db4437); font-weight: 600; text-decoration: underline dotted; cursor: help; }
      .empty { color: var(--secondary-text-color); font-style: italic; }
      .error { color: var(--error-color, #db4437); }
      .toggle-details { background: none; border: none; color: var(--primary-color); padding: 2px 4px; font: inherit; cursor: pointer; }
      .details-row td { padding: 0 8px 12px; border-bottom: 1px solid var(--divider-color); }
      .itinerary { display: flex; flex-direction: column; gap: 10px; padding: 8px 0 0 8px; border-left: 2px solid var(--divider-color); margin-left: 6px; }
      .leg { font-size: 0.9em; }
      .leg-line { margin-bottom: 2px; }
      .leg-stop { color: var(--secondary-text-color); padding-left: 2px; }
      .leg.walk { color: var(--secondary-text-color); font-style: italic; }
      .leg.walk ha-icon { --mdc-icon-size: 16px; vertical-align: text-bottom; }
    `;
  }
}

// Visueller Karten-Editor: Standort-Gerät und Zielhaltestelle werden hier
// gewählt, nicht mehr per YAML/Entity-ID. Bewusst kein <ha-entity-picker>
// verwendet - das ist ein undokumentiertes, internes HA-Frontend-Element
// ohne Garantie, dass es beim Laden der Karte bereits registriert ist. Ein
// natives <select> ist dafür genauso zuverlässig wie der Rest der Karte.
class HaDynConnectionsCardEditor extends HTMLElement {
  setConfig(config) {
    // Der Dashboard-Editor ruft setConfig() ggf. erneut auf, nachdem er ein
    // von uns gefeuertes config-changed-Event verarbeitet hat. Ist der Inhalt
    // identisch, ist das ein reines Echo - kein Re-Render, sonst würde eine
    // gerade laufende Eingabe (z.B. im Zielhaltestellen-Suchfeld) den Fokus
    // verlieren, obwohl sich inhaltlich nichts geändert hat.
    const next = config || {};
    if (this._config && JSON.stringify(this._config) === JSON.stringify(next)) {
      return;
    }
    this._config = next;
    this._render();
  }

  set hass(hass) {
    // Wie bei der Haupt-Karte: nur beim ersten Zuweisen rendern, siehe
    // ausführliche Begründung dort. Ohne diese Guard würde jedes
    // hass-Update (sehr häufig, unabhängig von Nutzeraktionen) das
    // Formular neu aufbauen und dabei den Fokus aus einem gerade
    // getippten Eingabefeld (z.B. der Zielhaltestellen-Suche) werfen.
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._render();
    }
  }

  _emitConfigChanged() {
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true })
    );
  }

  async _searchDestination(query) {
    if (!query) return;
    this._destinationError = null;
    this._destinationResults = null;
    this._render();
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: `${DOMAIN}/search_stops`,
        query,
      });
      this._destinationResults = result.stops || [];
    } catch (err) {
      this._destinationError = err.message || "Suche fehlgeschlagen.";
    }
    this._render();
  }

  _render() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    if (!this._hass || !this._config) {
      return;
    }

    const trackers = Object.values(this._hass.states)
      .filter((s) => s.entity_id.startsWith("device_tracker."))
      .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id));

    this.shadowRoot.innerHTML = `
      <style>${HaDynConnectionsCardEditor._styles()}</style>
      <div class="form">
        <label>
          Titel (optional)
          <input id="title" type="text" value="${escapeHtml(this._config.title || "")}" placeholder="Nach ${escapeHtml(this._config.destination_name || "...")}" />
        </label>

        <label>
          Standort-Gerät
          <select id="device_tracker">
            <option value="">– wählen –</option>
            ${trackers
              .map(
                (t) =>
                  `<option value="${escapeHtml(t.entity_id)}" ${t.entity_id === this._config.device_tracker ? "selected" : ""}>${escapeHtml(t.attributes.friendly_name || t.entity_id)}</option>`
              )
              .join("")}
          </select>
        </label>

        <label>
          Zielhaltestelle
          <span class="row">
            <input id="destination_query" type="text" placeholder="Haltestelle suchen…" />
            <button id="destination_search">Suchen</button>
          </span>
        </label>

        ${
          this._config.destination_name
            ? `<p class="current">Aktuelles Ziel: <strong>${escapeHtml(this._config.destination_name)}</strong></p>`
            : ""
        }
        ${this._destinationError ? `<p class="error">${escapeHtml(this._destinationError)}</p>` : ""}
        ${
          this._destinationResults
            ? `<ul class="results">
                ${this._destinationResults
                  .map(
                    (stop) =>
                      `<li data-id="${escapeHtml(stop.id)}" data-name="${escapeHtml(stop.name)}"><span class="stop-name">${escapeHtml(stop.name)}</span> ${modeBadgesHtml(stop.modes)}</li>`
                  )
                  .join("")}
                ${this._destinationResults.length === 0 ? "<li><em>Keine Treffer</em></li>" : ""}
              </ul>`
            : ""
        }
      </div>
    `;

    this.shadowRoot.getElementById("title").addEventListener("change", (ev) => {
      this._config = { ...this._config, title: ev.target.value };
      this._emitConfigChanged();
    });

    this.shadowRoot.getElementById("device_tracker").addEventListener("change", (ev) => {
      this._config = { ...this._config, device_tracker: ev.target.value };
      this._emitConfigChanged();
      this._render();
    });

    this.shadowRoot.getElementById("destination_search").addEventListener("click", () => {
      this._searchDestination(this.shadowRoot.getElementById("destination_query").value.trim());
    });

    this.shadowRoot.querySelectorAll(".results li[data-id]").forEach((li) => {
      li.addEventListener("click", () => {
        this._config = { ...this._config, destination_id: li.dataset.id, destination_name: li.dataset.name };
        this._destinationResults = null;
        this._emitConfigChanged();
        this._render();
      });
    });
  }

  static _styles() {
    return `
      .form { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
      label { display: flex; flex-direction: column; font-size: 0.85em; color: var(--secondary-text-color, #666); gap: 4px; }
      .row { display: flex; gap: 8px; }
      input, select, button { font: inherit; padding: 8px; border-radius: 6px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, #fff); color: var(--primary-text-color, #000); }
      button { cursor: pointer; }
      .current { margin: 0; font-size: 0.9em; }
      .error { color: var(--error-color, #db4437); margin: 0; }
      .results { list-style: none; margin: 0; padding: 0; border: 1px solid var(--divider-color, #ccc); border-radius: 6px; max-height: 200px; overflow-y: auto; }
      .results li { display: flex; align-items: center; gap: 6px; padding: 8px; cursor: pointer; }
      .results li .stop-name { flex: 1; }
      .results li:hover { background: var(--secondary-background-color, #f0f0f0); }
      .mode-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 4px; color: #fff; font-size: 0.7em; font-weight: 700; line-height: 1; }
      .mode-badge ha-icon { --mdc-icon-size: 13px; }
    `;
  }
}

customElements.define("ha-dynconnections-card", HaDynConnectionsCard);
customElements.define("ha-dynconnections-card-editor", HaDynConnectionsCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ha-dynconnections-card",
  name: "HA DynConnections",
  description: "Zeigt die nächsten Verbindungen von deinem Standort zur konfigurierten Zielhaltestelle.",
});
