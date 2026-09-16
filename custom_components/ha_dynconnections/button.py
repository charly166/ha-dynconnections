"""Such-Button: löst die eigentliche Verbindungssuche aus.

Bewusst als eigene Entität statt als Service: ein Button-Entity bringt die
`button.press`-Aktion automatisch mit (auch für Automationen nutzbar) und
lässt sich ohne eigene Karte direkt in jede Lovelace-Karte legen.
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DynConnectionsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DynConnectionsSearchButton(data["coordinator"], entry)])


class DynConnectionsSearchButton(ButtonEntity):
    """Startet die Verbindungssuche für die aktuell gewählte Haltestelle/Zeit."""

    _attr_has_entity_name = True
    _attr_translation_key = "search"
    _attr_icon = "mdi:magnify"

    def __init__(self, coordinator: DynConnectionsCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_search"

    async def async_press(self) -> None:
        await self._coordinator.async_request_refresh()
