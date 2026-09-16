"""WebSocket-Befehle, über die die Lovelace-Karte mit der Integration spricht.

Die gesamte Bedienung (Standort-Gerät und Zielhaltestelle wählen, Verbindung
suchen) läuft in der Karte selbst - es gibt keine Entities. Diese Befehle
sind die einzige Verbindung zwischen Karte und dem VVS-EFA-Client.
"""
from __future__ import annotations

import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .api import VvsEfaClient, VvsEfaError, summarize_journey
from .const import DEFAULT_NEARBY_DISTANCE, DEFAULT_NEARBY_RESULTS, DOMAIN, JOURNEY_RESULTS

_LOGGER = logging.getLogger(__name__)


def _get_client(hass: HomeAssistant) -> VvsEfaClient | None:
    domain_data = hass.data.get(DOMAIN, {})
    return domain_data.get("client")


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/search_stops", vol.Required("query"): str}
)
@websocket_api.async_response
async def ws_search_stops(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    client = _get_client(hass)
    if client is None:
        connection.send_error(msg["id"], "not_configured", "Integration ist nicht eingerichtet.")
        return
    try:
        stops = await client.search_locations(msg["query"])
    except VvsEfaError as err:
        connection.send_error(msg["id"], "efa_error", str(err))
        return
    connection.send_result(msg["id"], {"stops": stops})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/nearby_stops",
        vol.Required("latitude"): vol.Coerce(float),
        vol.Required("longitude"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_nearby_stops(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    client = _get_client(hass)
    if client is None:
        connection.send_error(msg["id"], "not_configured", "Integration ist nicht eingerichtet.")
        return
    try:
        stops = await client.nearby_stops(
            msg["latitude"],
            msg["longitude"],
            results=DEFAULT_NEARBY_RESULTS,
            distance=DEFAULT_NEARBY_DISTANCE,
        )
    except VvsEfaError as err:
        connection.send_error(msg["id"], "efa_error", str(err))
        return
    connection.send_result(msg["id"], {"stops": stops})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/search_journeys",
        vol.Required("origin_id"): str,
        vol.Required("destination_id"): str,
        vol.Optional("departure"): str,
    }
)
@websocket_api.async_response
async def ws_search_journeys(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    client = _get_client(hass)
    if client is None:
        connection.send_error(msg["id"], "not_configured", "Integration ist nicht eingerichtet.")
        return

    departure = datetime.fromisoformat(msg["departure"]) if msg.get("departure") else None

    try:
        journeys = await client.journeys(
            msg["origin_id"],
            msg["destination_id"],
            departure=departure,
            results=JOURNEY_RESULTS,
        )
    except VvsEfaError as err:
        connection.send_error(msg["id"], "efa_error", str(err))
        return

    connection.send_result(msg["id"], {"connections": [summarize_journey(j) for j in journeys]})


def async_register_commands(hass: HomeAssistant) -> None:
    """Registriert alle WebSocket-Befehle (nur einmal global nötig)."""
    websocket_api.async_register_command(hass, ws_search_stops)
    websocket_api.async_register_command(hass, ws_nearby_stops)
    websocket_api.async_register_command(hass, ws_search_journeys)
