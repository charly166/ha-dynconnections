// HA DynConnections – Lovelace-Karte (Vanilla Web Component, kein Build-Schritt).
//
// Bewusst kein externes Web-Font geladen (System-Fonts reichen), um keine
// unnötigen Drittanbieter-Requests von Besuchern auszulösen.
//
// Erwartete Card-Konfiguration (YAML):
//   type: custom:ha-dynconnections-card
//   origin_entity: select.xxx_abfahrtshaltestelle
//   datetime_entity: datetime.xxx_gewuenschte_abfahrtszeit
//   button_entity: button.xxx_verbindung_suchen
//   sensor_entity: sensor.xxx_naechste_verbindungen
//   title: "Nach Hause"   # optional

class HaDynConnectionsCard extends HTMLElement {
  setConfig(config) {
    for (const key of ["origin_entity", "datetime_entity", "button_entity", "sensor_entity"]) {
      if (!config[key]) {
        throw new Error(`ha-dynconnections-card: "${key}" muss in der Card-Konfiguration gesetzt sein.`);
      }
    }
    this._config = config;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  _render() {
    if (!this._config || !this._hass) {
      return;
    }
    const originState = this._hass.states[this._config.origin_entity];
    const datetimeState = this._hass.states[this._config.datetime_entity];
    const sensorState = this._hass.states[this._config.sensor_entity];

    if (!originState || !datetimeState || !sensorState) {
      this.shadowRoot.innerHTML = `<ha-card><div class="card-content">Entität(en) nicht gefunden. Bitte Card-Konfiguration prüfen.</div></ha-card>`;
      return;
    }

    const title = this._config.title || "HA DynConnections";
    const options = originState.attributes.options || [];
    const connections = (sensorState.attributes.connections || []);

    this.shadowRoot.innerHTML = `
      <style>${HaDynConnectionsCard._styles()}</style>
      <ha-card>
        <div class="header">${this._escape(title)}</div>
        <div class="card-content">
          <div class="controls">
            <label>
              Von
              <select id="origin">
                ${options
                  .map(
                    (opt) =>
                      `<option value="${this._escape(opt)}" ${opt === originState.state ? "selected" : ""}>${this._escape(opt)}</option>`
                  )
                  .join("")}
              </select>
            </label>
            <label>
              Abfahrt
              <input id="departure" type="datetime-local" value="${this._toLocalInputValue(datetimeState.state)}" />
            </label>
            <button id="search">Verbindung suchen</button>
          </div>
          ${this._renderTable(connections)}
        </div>
      </ha-card>
    `;

    this.shadowRoot.getElementById("origin").addEventListener("change", (ev) => {
      this._hass.callService("select", "select_option", {
        entity_id: this._config.origin_entity,
        option: ev.target.value,
      });
    });

    this.shadowRoot.getElementById("departure").addEventListener("change", (ev) => {
      const value = ev.target.value ? new Date(ev.target.value).toISOString() : null;
      this._hass.callService("datetime", "set_value", {
        entity_id: this._config.datetime_entity,
        datetime: value,
      });
    });

    this.shadowRoot.getElementById("search").addEventListener("click", () => {
      this._hass.callService("button", "press", { entity_id: this._config.button_entity });
    });
  }

  _renderTable(connections) {
    if (!connections.length) {
      return `<p class="empty">Noch keine Suche gestartet oder keine Verbindungen gefunden.</p>`;
    }
    const rows = connections
      .map(
        (c) => `
        <tr>
          <td>${this._escape(c.line || "-")}</td>
          <td>${this._escape(c.direction || "-")}</td>
          <td>${this._formatTime(c.departure)}${c.delay_minutes ? ` <span class="delay">+${c.delay_minutes}</span>` : ""}</td>
          <td>${this._escape(c.platform || "-")}</td>
          <td>${this._formatTime(c.arrival)}</td>
          <td>${c.transfers ?? "-"}</td>
          <td>${c.duration_minutes != null ? `${c.duration_minutes} min` : "-"}</td>
        </tr>`
      )
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

  _formatTime(iso) {
    if (!iso) return "-";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  _toLocalInputValue(iso) {
    if (!iso || iso === "unknown" || iso === "unavailable") return "";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  _escape(value) {
    return String(value).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));
  }

  static _styles() {
    return `
      .header { font-size: 1.2em; font-weight: 500; padding: 16px 16px 0; color: var(--primary-text-color); }
      .card-content { padding: 16px; font-family: var(--paper-font-body1_-_font-family, inherit); }
      .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 16px; }
      label { display: flex; flex-direction: column; font-size: 0.85em; color: var(--secondary-text-color); gap: 4px; }
      select, input, button { font: inherit; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
      button { cursor: pointer; background: var(--primary-color); color: var(--text-primary-color, #fff); border: none; padding: 8px 14px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--divider-color); font-size: 0.9em; }
      th { color: var(--secondary-text-color); font-weight: 500; }
      .delay { color: var(--error-color, #db4437); font-weight: 600; }
      .empty { color: var(--secondary-text-color); font-style: italic; }
    `;
  }
}

customElements.define("ha-dynconnections-card", HaDynConnectionsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ha-dynconnections-card",
  name: "HA DynConnections",
  description: "Zeigt die nächsten Verbindungen von deinem Standort zur konfigurierten Zielhaltestelle.",
});
