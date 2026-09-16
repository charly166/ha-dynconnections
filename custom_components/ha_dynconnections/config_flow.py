"""Config-Flow: wählt das Standort-Device (device_tracker) und die Zielhaltestelle.

Die Zielhaltestelle wird per Namenssuche gegen die VVS-EFA-Schnittstelle ermittelt, da
die API keine Autocomplete-Combobox im Config-Flow-Formular selbst erlaubt -
stattdessen zeigt ein zweiter Schritt die gefundenen Treffer als Auswahlliste.

Der Options-Flow erlaubt, die Zielhaltestelle später zu ändern sowie Anzahl
und Suchradius der Haltestellen-Vorschläge (für die Select-Entität) anzupassen.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VvsEfaClient, VvsEfaError
from .const import (
    CONF_DESTINATION_ID,
    CONF_DESTINATION_NAME,
    CONF_DEVICE_TRACKER,
    CONF_NEARBY_DISTANCE,
    CONF_NEARBY_RESULTS,
    DEFAULT_NEARBY_DISTANCE,
    DEFAULT_NEARBY_RESULTS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_TRACKER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="device_tracker")
        ),
        vol.Required("destination_query"): str,
    }
)


async def _search_destinations(hass: HomeAssistant, query: str) -> dict[str, str]:
    session = async_get_clientsession(hass)
    client = VvsEfaClient(session)
    results = await client.search_locations(query)
    return {str(stop["id"]): stop.get("name", str(stop["id"])) for stop in results if stop.get("id")}


class DynConnectionsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Einrichtungsassistent für HA DynConnections."""

    VERSION = 1

    def __init__(self) -> None:
        self._device_tracker: str | None = None
        self._destination_candidates: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._device_tracker = user_input[CONF_DEVICE_TRACKER]
            try:
                self._destination_candidates = await _search_destinations(
                    self.hass, user_input["destination_query"]
                )
            except VvsEfaError:
                errors["base"] = "cannot_connect"
            else:
                if not self._destination_candidates:
                    errors["base"] = "no_stops_found"
                else:
                    return await self.async_step_destination()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_destination(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            destination_id = user_input[CONF_DESTINATION_ID]
            destination_name = self._destination_candidates[destination_id]

            await self.async_set_unique_id(f"{self._device_tracker}::{destination_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Nach {destination_name}",
                data={
                    CONF_DEVICE_TRACKER: self._device_tracker,
                    CONF_DESTINATION_ID: destination_id,
                    CONF_DESTINATION_NAME: destination_name,
                },
                options={
                    CONF_NEARBY_RESULTS: DEFAULT_NEARBY_RESULTS,
                    CONF_NEARBY_DISTANCE: DEFAULT_NEARBY_DISTANCE,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_DESTINATION_ID): vol.In(self._destination_candidates),
            }
        )
        return self.async_show_form(
            step_id="destination", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "DynConnectionsOptionsFlow":
        return DynConnectionsOptionsFlow()


class DynConnectionsOptionsFlow(config_entries.OptionsFlow):
    """Erlaubt, die Zielhaltestelle sowie die Haltestellen-Vorschlagsliste anzupassen.

    `self.config_entry` wird von Home Assistant automatisch bereitgestellt
    (seit Core 2024.12) und darf hier nicht manuell im `__init__` gesetzt
    werden - siehe das gleiche, bereits einmal live aufgetretene Problem im
    Schwesterprojekt HA MoviesDB (führt seit Core 2025.12 zu einer
    AttributeError / 500er beim Öffnen der Konfiguration).
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current_destination_name = self.config_entry.data.get(CONF_DESTINATION_NAME)

        if user_input is not None:
            destination_query = user_input.get("destination_query")
            data = dict(self.config_entry.data)

            if destination_query:
                try:
                    candidates = await _search_destinations(self.hass, destination_query)
                except VvsEfaError:
                    errors["base"] = "cannot_connect"
                else:
                    if not candidates:
                        errors["base"] = "no_stops_found"
                    else:
                        # Nimmt den besten (ersten) Treffer der Namenssuche - für ein
                        # zweistufiges Auswahlformular wie im Config-Flow reicht der
                        # Options-Flow-Rahmen an dieser Stelle nicht sauber aus.
                        destination_id, destination_name = next(iter(candidates.items()))
                        data[CONF_DESTINATION_ID] = destination_id
                        data[CONF_DESTINATION_NAME] = destination_name

            if not errors:
                self.hass.config_entries.async_update_entry(self.config_entry, data=data)
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_NEARBY_RESULTS: int(user_input[CONF_NEARBY_RESULTS]),
                        CONF_NEARBY_DISTANCE: int(user_input[CONF_NEARBY_DISTANCE]),
                    },
                )

        schema = vol.Schema(
            {
                vol.Optional("destination_query", description={"suggested_value": ""}): str,
                vol.Required(
                    CONF_NEARBY_RESULTS,
                    default=self.config_entry.options.get(
                        CONF_NEARBY_RESULTS, DEFAULT_NEARBY_RESULTS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Required(
                    CONF_NEARBY_DISTANCE,
                    default=self.config_entry.options.get(
                        CONF_NEARBY_DISTANCE, DEFAULT_NEARBY_DISTANCE
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=100, max=5000)),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"current_destination": current_destination_name},
        )
