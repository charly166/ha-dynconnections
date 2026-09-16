"""Sensor-Plattform: zeigt die zuletzt gesuchten Verbindungen als Timetable an.

Der State ist die Abfahrtszeit der nächsten Verbindung (praktisch für
Automationen/Vorschau), die vollständige Liste der bis zu 5 Verbindungen
liegt im Attribut `connections` (von der Lovelace-Karte als Tabelle
gerendert, alternativ per Markdown-Karte/Template nutzbar).
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DynConnectionsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DynConnectionsSensor(data["coordinator"], entry)])


class DynConnectionsSensor(CoordinatorEntity[DynConnectionsCoordinator], SensorEntity):
    """Zeigt die zuletzt gesuchten Verbindungen zur konfigurierten Zielhaltestelle."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_connections"
    _attr_icon = "mdi:train-car"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: DynConnectionsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_next_connections"

    @property
    def native_value(self):
        connections = self.coordinator.data or []
        if not connections or not connections[0].get("departure"):
            return None
        return dt_util.parse_datetime(connections[0]["departure"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "origin": self.coordinator.origin_stop_name,
            "destination": self.coordinator.destination_name,
            "connections": self.coordinator.data or [],
        }
