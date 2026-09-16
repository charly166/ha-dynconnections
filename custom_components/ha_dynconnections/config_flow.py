"""Config-Flow: reine Bestätigung, ohne Felder.

Standort-Gerät und Zielhaltestelle werden nicht mehr hier, sondern direkt im
visuellen Editor der Lovelace-Karte gewählt (pro Karteninstanz, siehe
www/ha-dynconnections-card.js). Diese Integration ist daher Single-Instance:
sie registriert nur die WebSocket-Befehle und die Karten-Ressource.
"""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class DynConnectionsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Einmalige Bestätigung, um HA DynConnections zu aktivieren."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="HA DynConnections", data={})

        return self.async_show_form(step_id="user")
