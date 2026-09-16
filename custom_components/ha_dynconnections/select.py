"""Select-Entität: Combobox mit den nächstgelegenen Haltestellen zum Standort-Device.

Die Optionsliste wird neu geladen, sobald sich der konfigurierte
`device_tracker` bewegt (GPS-Update über die Companion App). Die aktuell
gewählte Option wird direkt auf dem Coordinator hinterlegt (siehe
coordinator.py), damit der Such-Button beim Drücken weiß, von welcher
Haltestelle aus gesucht werden soll.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .api import VvsEfaClient, VvsEfaError
from .const import CONF_DEVICE_TRACKER, CONF_NEARBY_DISTANCE, CONF_NEARBY_RESULTS, DOMAIN
from .coordinator import DynConnectionsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entity = DynConnectionsOriginSelect(hass, data["client"], data["coordinator"], entry)
    async_add_entities([entity])


class DynConnectionsOriginSelect(RestoreEntity, SelectEntity):
    """Zeigt die nächstgelegenen Haltestellen zum Standort-Device als Auswahl an."""

    _attr_has_entity_name = True
    _attr_translation_key = "origin_stop"
    _attr_icon = "mdi:map-marker-radius"

    def __init__(
        self,
        hass: HomeAssistant,
        client: VvsEfaClient,
        coordinator: DynConnectionsCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self.hass = hass
        self._client = client
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_origin_stop"
        self._attr_options: list[str] = []
        self._attr_current_option: str | None = None
        self._name_to_id: dict[str, str] = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state:
            self._attr_current_option = last_state.state
            self._attr_options = [last_state.state]

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._entry.data[CONF_DEVICE_TRACKER]],
                self._handle_device_tracker_update,
            )
        )

        tracker_state = self.hass.states.get(self._entry.data[CONF_DEVICE_TRACKER])
        if tracker_state is not None:
            await self._async_refresh_options(tracker_state.attributes)

    @callback
    def _handle_device_tracker_update(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return
        self.hass.async_create_task(self._async_refresh_options(new_state.attributes))

    async def _async_refresh_options(self, attributes: dict[str, Any]) -> None:
        latitude = attributes.get("latitude")
        longitude = attributes.get("longitude")
        if latitude is None or longitude is None:
            return

        try:
            stops = await self._client.nearby_stops(
                latitude,
                longitude,
                results=self._entry.options.get(CONF_NEARBY_RESULTS, 5),
                distance=self._entry.options.get(CONF_NEARBY_DISTANCE, 1000),
            )
        except VvsEfaError as err:
            _LOGGER.warning("Konnte nahegelegene Haltestellen nicht laden: %s", err)
            return

        self._name_to_id = {stop["name"]: str(stop["id"]) for stop in stops if stop.get("name")}
        self._attr_options = list(self._name_to_id)

        if self._attr_current_option not in self._attr_options and self._attr_options:
            await self.async_select_option(self._attr_options[0])
            return

        if self._attr_current_option in self._name_to_id:
            self._coordinator.origin_stop_id = self._name_to_id[self._attr_current_option]
            self._coordinator.origin_stop_name = self._attr_current_option

        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._coordinator.origin_stop_id = self._name_to_id.get(option)
        self._coordinator.origin_stop_name = option
        self.async_write_ha_state()
