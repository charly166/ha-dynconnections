"""DataUpdateCoordinator für die Verbindungssuche.

Bewusst mit `update_interval=None`: es gibt kein automatisches Polling, die
Verbindungssuche wird ausschließlich durch den Such-Button (oder dessen
`button.press`-Service, z.B. aus einer Automation) ausgelöst. Herkunfts-
haltestelle und Wunschzeit werden von der Select- bzw. DateTime-Entität
direkt auf dem Coordinator gesetzt, sobald der Nutzer sie ändert - der
Coordinator selbst merkt sich nur den zuletzt gewählten Stand.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VvsEfaClient, VvsEfaError, summarize_journey
from .const import DOMAIN, JOURNEY_RESULTS

_LOGGER = logging.getLogger(__name__)


class DynConnectionsCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Führt die Verbindungssuche für eine Config Entry aus."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: VvsEfaClient,
        destination_id: str,
        destination_name: str,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.client = client
        self.destination_id = destination_id
        self.destination_name = destination_name
        self.origin_stop_id: str | None = None
        self.origin_stop_name: str | None = None
        self.departure_at: datetime | None = None

    async def _async_update_data(self) -> list[dict[str, Any]]:
        if not self.origin_stop_id:
            raise UpdateFailed("Keine Abfahrtshaltestelle ausgewählt.")

        try:
            journeys = await self.client.journeys(
                self.origin_stop_id,
                self.destination_id,
                departure=self.departure_at,
                results=JOURNEY_RESULTS,
            )
        except VvsEfaError as err:
            raise UpdateFailed(str(err)) from err

        return [summarize_journey(journey) for journey in journeys]
