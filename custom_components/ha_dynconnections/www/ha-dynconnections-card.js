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

// Ordnet einer Linie ein passendes mdi-Icon zu. Primär anhand des EFA
// "product"-Felds (z.B. "S-Bahn", "Stadtbahn", "Bus", "Nachtbus") - das ist
// zuverlässiger als der Linienname, dessen Format "<Produkt> <Code>" ist
// (z.B. "S-Bahn S1", "R-Bahn RE14"). Regionalzüge (RE/RB/MEX) und
// Fernverkehr (ICE/IC/EC) teilen sich bei EFA oft dasselbe generische
// Produkt ("R-Bahn"/"Zug"), daher zusätzlich der Liniencode als Tie-Breaker.
function lineIcon(line, product) {
  const p = (product || "").toLowerCase();
  const tokens = (line || "").toUpperCase().split(/\s+/);

  if (p === "s-bahn") return "mdi:subway-variant";
  if (p === "stadtbahn") return "mdi:subway";
  if (p === "nachtbus") return "mdi:bus-clock";
  if (p.includes("sev")) return "mdi:bus-alert";
  if (p.includes("bus")) return "mdi:bus";
  if (p === "fussweg") return "mdi:walk";
  if (tokens.some((t) => /^(ICE|IC|EC)\d*$/.test(t))) return "mdi:train-variant";
  if (p === "r-bahn" || p === "zug" || tokens.some((t) => /^(MEX|RE|RB|IRE)\d*$/.test(t))) return "mdi:train";
  return "mdi:transit-connection-variant";
}

class HaDynConnectionsCard extends HTMLElement {
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

    this.shadowRoot.innerHTML = `
      <style>${HaDynConnectionsCard._styles()}</style>
      <ha-card>
        <div class="header">${escapeHtml(title)}</div>
        <div class="card-content">
          ${this._stopsError ? `<p class="error">${escapeHtml(this._stopsError)}</p>` : ""}
          <div class="controls">
            <label>
              Von
              <span class="row">
                <select id="origin" ${this._loadingStops ? "disabled" : ""}>
                  ${this._originStops
                    .map(
                      (stop) =>
                        `<option value="${escapeHtml(stop.id)}" ${stop.id === this._selectedOriginId ? "selected" : ""}>${escapeHtml(stop.name)}</option>`
                    )
                    .join("")}
                </select>
                <button id="refresh" title="Haltestellen neu laden" ${this._loadingStops ? "disabled" : ""}>⟳</button>
              </span>
            </label>
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

    this.shadowRoot.getElementById("origin").addEventListener("change", (ev) => {
      this._selectedOriginId = ev.target.value;
    });
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
          <td><ha-icon icon="${lineIcon(c.line, c.product)}"></ha-icon> ${escapeHtml(c.line || "-")}</td>
          <td>${escapeHtml(c.direction || "-")}</td>
          <td>${formatTime(c.departure)}${c.delay_minutes ? ` <span class="delay">+${c.delay_minutes}</span>` : ""}</td>
          <td>${escapeHtml(c.platform || "-")}</td>
          <td>${formatTime(c.arrival)}</td>
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
          <div class="leg-line"><ha-icon icon="${lineIcon(leg.line, leg.product)}"></ha-icon> <strong>${escapeHtml(leg.line || "-")}</strong> Richtung ${escapeHtml(leg.direction || "-")}</div>
          <div class="leg-stop">ab <strong>${escapeHtml(leg.departure_stop || "-")}</strong> ${formatTime(leg.departure)}${leg.delay_minutes ? ` <span class="delay">+${leg.delay_minutes}</span>` : ""}${leg.departure_platform ? ` (${escapeHtml(leg.departure_platform)})` : ""}</div>
          <div class="leg-stop">an <strong>${escapeHtml(leg.arrival_stop || "-")}</strong> ${formatTime(leg.arrival)}${leg.arrival_platform ? ` (${escapeHtml(leg.arrival_platform)})` : ""}</div>
        </div>`;
    });
    return `<div class="itinerary">${steps.join("")}</div>`;
  }

  static _styles() {
    return `
      .header { font-size: 1.2em; font-weight: 500; padding: 16px 16px 0; color: var(--primary-text-color); }
      .card-content { padding: 16px; font-family: var(--paper-font-body1_-_font-family, inherit); }
      .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 16px; }
      label { display: flex; flex-direction: column; font-size: 0.85em; color: var(--secondary-text-color); gap: 4px; }
      .hint { font-weight: normal; font-style: italic; opacity: 0.8; }
      .row { display: flex; gap: 4px; }
      select, input, button { font: inherit; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
      button { cursor: pointer; background: var(--primary-color); color: var(--text-primary-color, #fff); border: none; padding: 8px 14px; }
      button:disabled { opacity: 0.6; cursor: default; }
      #refresh { padding: 6px 10px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--divider-color); font-size: 0.9em; }
      th { color: var(--secondary-text-color); font-weight: 500; }
      td ha-icon { --mdc-icon-size: 18px; vertical-align: text-bottom; color: var(--secondary-text-color); }
      .delay { color: var(--error-color, #db4437); font-weight: 600; }
      .empty { color: var(--secondary-text-color); font-style: italic; }
      .error { color: var(--error-color, #db4437); }
      .toggle-details { background: none; border: none; color: var(--primary-color); padding: 2px 4px; font: inherit; cursor: pointer; }
      .details-row td { padding: 0 8px 12px; border-bottom: 1px solid var(--divider-color); }
      .itinerary { display: flex; flex-direction: column; gap: 10px; padding: 8px 0 0 8px; border-left: 2px solid var(--divider-color); margin-left: 6px; }
      .leg { font-size: 0.9em; }
      .leg-line { margin-bottom: 2px; }
      .leg-line ha-icon { --mdc-icon-size: 18px; vertical-align: text-bottom; color: var(--secondary-text-color); }
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
                      `<li data-id="${escapeHtml(stop.id)}" data-name="${escapeHtml(stop.name)}">${escapeHtml(stop.name)}</li>`
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
      .results li { padding: 8px; cursor: pointer; }
      .results li:hover { background: var(--secondary-background-color, #f0f0f0); }
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
