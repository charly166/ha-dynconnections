"""Automatische Registrierung der Lovelace-Karte als Dashboard-Ressource.

Übernommen 1:1 vom Schwesterprojekt HA MoviesDB (dort ausführlich
dokumentierte Home-Assistant-Eigenheiten rund um `resource_mode` und das
"lazy loading" der Ressourcen-Collection, siehe dortige Kommentare).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CARD_FILENAME, CARD_VERSION, STATIC_BASE_PATH

_LOGGER = logging.getLogger(__name__)

RESOURCE_URL = f"{STATIC_BASE_PATH}/{CARD_FILENAME}"


class LovelaceResourceRegistration:
    """Verwaltet die Lovelace-Ressource für die Karte."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_register(self) -> None:
        """Registriert (oder aktualisiert) die Ressource, falls möglich."""
        lovelace = self.hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.debug("HA DynConnections: Lovelace ist noch nicht geladen.")
            return

        resource_mode = getattr(lovelace, "resource_mode", None)
        if resource_mode != "storage":
            _LOGGER.info(
                "HA DynConnections: Lovelace läuft im YAML-Modus, die Karten-Ressource "
                "kann nicht automatisch eingetragen werden. Bitte manuell "
                "hinzufügen (siehe README): %s?v=%s",
                RESOURCE_URL,
                CARD_VERSION,
            )
            return

        resources = lovelace.resources
        try:
            if not resources.loaded:
                await resources.async_load()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "HA DynConnections: Konnte Lovelace-Ressourcen nicht laden, "
                "automatische Registrierung übersprungen."
            )
            return

        await self._async_sync_resource(resources)

    async def _async_sync_resource(self, resources: Any) -> None:
        existing = [
            r for r in resources.async_items() if r["url"].split("?")[0] == RESOURCE_URL
        ]
        target_url = f"{RESOURCE_URL}?v={CARD_VERSION}"

        if not existing:
            _LOGGER.info("HA DynConnections: Registriere Karte als Lovelace-Ressource.")
            await resources.async_create_item({"res_type": "module", "url": target_url})
            return

        resource = existing[0]
        current_version = (
            resource["url"].split("?v=")[-1] if "?v=" in resource["url"] else None
        )
        if current_version != CARD_VERSION:
            _LOGGER.info(
                "HA DynConnections: Aktualisiere Karten-Ressource auf Version %s.", CARD_VERSION
            )
            await resources.async_update_item(
                resource["id"], {"res_type": "module", "url": target_url}
            )

    async def async_unregister(self) -> None:
        """Entfernt die Ressource wieder (beim vollständigen Entfernen der Integration)."""
        lovelace = self.hass.data.get("lovelace")
        if lovelace is None or getattr(lovelace, "resource_mode", None) != "storage":
            return
        resources = lovelace.resources
        if not resources.loaded:
            return
        for resource in list(resources.async_items()):
            if resource["url"].split("?")[0] == RESOURCE_URL:
                await resources.async_delete_item(resource["id"])
