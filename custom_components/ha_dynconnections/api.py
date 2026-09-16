"""Schlanker asynchroner Client für die kostenlose transport.rest API (v6.db.transport.rest).

Es wird bewusst kein zusätzliches Python-Paket genutzt, sondern nur die in
Home Assistant ohnehin vorhandene aiohttp-Session, damit die Integration
keine externen Requirements benötigt.

API-Dokumentation: https://v6.db.transport.rest/api.html
Die API nutzt das HAFAS "db"-Profil der Deutschen Bahn und deckt laut eigener
Doku Fern-, Regionalverkehr und einige lokale Buslinien ab (wie die DB
Navigator App). Lokale VVS-Stadtbahn-/Buslinien sind darüber unter Umständen
nicht vollständig abgedeckt - siehe README, Abschnitt "Bekannte Grenzen".
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import async_timeout
from aiohttp import ClientSession

from .const import TRANSPORT_REST_BASE_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class TransportRestError(Exception):
    """Fehler bei der Kommunikation mit transport.rest."""


class TransportRestClient:
    """Kapselt die wenigen transport.rest-Endpunkte, die diese Integration braucht.

    Die API benötigt keine Authentifizierung (Rate-Limit: 100 Anfragen/Minute,
    für den persönlichen Gebrauch dieser Integration völlig ausreichend, da
    Anfragen nur bei Standortänderung und Button-Druck erfolgen).
    """

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def _request(self, path: str, params: dict[str, Any]) -> Any:
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(
                    f"{TRANSPORT_REST_BASE_URL}{path}", params=params
                )
        except Exception as err:  # noqa: BLE001
            raise TransportRestError(f"Anfrage an transport.rest fehlgeschlagen: {err}") from err

        if resp.status != 200:
            raise TransportRestError(f"transport.rest antwortete mit Status {resp.status}")

        try:
            return await resp.json()
        except Exception as err:  # noqa: BLE001
            raise TransportRestError(f"Ungültige Antwort von transport.rest: {err}") from err

    async def search_locations(self, query: str, *, results: int = 5) -> list[dict[str, Any]]:
        """Sucht Haltestellen anhand ihres Namens (für die Zielhaltestellen-Auswahl)."""
        data = await self._request(
            "/locations",
            {"query": query, "results": results, "stops": "true", "poi": "false"},
        )
        return [loc for loc in data if loc.get("type") == "stop"]

    async def nearby_stops(
        self, latitude: float, longitude: float, *, results: int = 5, distance: int | None = None
    ) -> list[dict[str, Any]]:
        """Liefert die nächstgelegenen Haltestellen zu einer Koordinate."""
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "results": results,
            "stops": "true",
            "poi": "false",
        }
        if distance is not None:
            params["distance"] = distance
        data = await self._request("/locations/nearby", params)
        return [loc for loc in data if loc.get("type") == "stop"]

    async def journeys(
        self,
        origin_id: str,
        destination_id: str,
        *,
        departure: datetime | None = None,
        results: int = 5,
    ) -> list[dict[str, Any]]:
        """Sucht Verbindungen zwischen zwei Haltestellen-IDs."""
        params: dict[str, Any] = {
            "from": origin_id,
            "to": destination_id,
            "results": results,
            "stopovers": "false",
        }
        if departure is not None:
            params["departure"] = departure.isoformat()
        data = await self._request("/journeys", params)
        return data.get("journeys", [])


def summarize_journey(journey: dict[str, Any]) -> dict[str, Any]:
    """Fasst ein transport.rest-Journey-Objekt zu einer flachen Timetable-Zeile zusammen."""
    legs = [leg for leg in journey.get("legs", []) if not leg.get("walking")]
    if not legs:
        legs = journey.get("legs", [])
    first_leg = legs[0] if legs else {}
    last_leg = legs[-1] if legs else {}

    departure = first_leg.get("departure") or first_leg.get("plannedDeparture")
    planned_departure = first_leg.get("plannedDeparture")
    arrival = last_leg.get("arrival") or last_leg.get("plannedArrival")
    planned_arrival = last_leg.get("plannedArrival")

    delay_seconds = first_leg.get("departureDelay") or 0
    transit_legs = [leg for leg in journey.get("legs", []) if leg.get("line")]

    duration_minutes = None
    if departure and arrival:
        try:
            duration_minutes = round(
                (datetime.fromisoformat(arrival) - datetime.fromisoformat(departure)).total_seconds()
                / 60
            )
        except ValueError:
            duration_minutes = None

    return {
        "line": (first_leg.get("line") or {}).get("name"),
        "direction": first_leg.get("direction"),
        "departure": departure,
        "planned_departure": planned_departure,
        "delay_minutes": round(delay_seconds / 60) if delay_seconds else 0,
        "platform": first_leg.get("departurePlatform") or first_leg.get("plannedDeparturePlatform"),
        "arrival": arrival,
        "planned_arrival": planned_arrival,
        "duration_minutes": duration_minutes,
        "transfers": max(0, len(transit_legs) - 1),
        "lines": [leg["line"]["name"] for leg in transit_legs if leg.get("line", {}).get("name")],
    }
