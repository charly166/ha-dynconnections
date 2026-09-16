"""DateTime-Entität für die optionale Wunsch-Abfahrtszeit.

Bleibt der Wert leer, sucht der Coordinator ab "jetzt" (Standardverhalten der
EFA `XSLT_TRIP_REQUEST2`-Schnittstelle ohne `itdDate`/`itdTime`-Parameter).
"""
from __future__ import annotations

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DynConnectionsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DynConnectionsDepartureDateTime(data["coordinator"], entry)])


class DynConnectionsDepartureDateTime(RestoreEntity, DateTimeEntity):
    """Gewünschte Abfahrtszeit - leer bedeutet "jetzt"."""

    _attr_has_entity_name = True
    _attr_translation_key = "departure_at"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: DynConnectionsCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_departure_at"
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            value = dt_util.parse_datetime(last_state.state)
            self._attr_native_value = value
            self._coordinator.departure_at = value

    async def async_set_value(self, value) -> None:
        self._attr_native_value = value
        self._coordinator.departure_at = value
        self.async_write_ha_state()
