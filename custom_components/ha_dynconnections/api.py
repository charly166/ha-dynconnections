"""Schlanker asynchroner Client für die VVS-eigene EFA-Schnittstelle (efa.vvs.de/vvs).

Es wird bewusst kein zusätzliches Python-Paket genutzt, sondern nur die in
Home Assistant ohnehin vorhandene aiohttp-Session, damit die Integration
keine externen Requirements benötigt.

Dies ist dieselbe Schnittstelle, die auch https://efa.vvs.de als öffentliche
Fahrplanauskunft-Website selbst verwendet - unauthentifiziert per HTTPS/JSON
erreichbar, live gegengeprüft (Stopfinder, Koordinatensuche, Trip-Anfrage).

Wichtig: Dies ist keine offiziell dokumentierte/lizenzierte Drittanbieter-API
(anders als z.B. die kostenpflichtige/registrierungspflichtige
EFA-JSON-API/TRIAS-API von MobiData BW für Baden-Württemberg), sondern die
interne Schnittstelle der VVS-Webseite selbst. Sie kann sich daher jederzeit
ohne Ankündigung ändern - siehe README, Abschnitt "Datenquelle".

Bekannte EFA-Eigenheit: Antworten enthalten für Namen mit Sonderzeichen
(ß, Umlaute) gelegentlich doppelt kodierte UTF-8-Bytes ("Mojibake", z.B.
"KriegsbergstraÃŸe" statt "Kriegsbergstraße"). `_fix_mojibake()` korrigiert
das best-effort, ohne bei unerwarteten Eingaben Fehler zu werfen.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import async_timeout
from aiohttp import ClientSession

from .const import EFA_BASE_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class VvsEfaError(Exception):
    """Fehler bei der Kommunikation mit der VVS-EFA-Schnittstelle."""


def _fix_mojibake(value: str | None) -> str | None:
    if not value:
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return value


def _as_list(node: Any, singular_key: str | None = None) -> list[dict[str, Any]]:
    """Normalisiert EFAs Eigenheit, Listen mit nur einem Eintrag ohne Array
    zurückzugeben (teils sogar unter einem zusätzlichen Singular-Schlüssel)."""
    if node is None:
        return []
    if singular_key is not None and isinstance(node, dict) and singular_key in node:
        node = node[singular_key]
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return [node]
    return []


class VvsEfaClient:
    """Kapselt die wenigen EFA-Endpunkte, die diese Integration braucht.

    Die Schnittstelle benötigt keine Authentifizierung. Aus Rücksicht auf den
    Betreiber werden Anfragen ausschließlich durch Standortänderung und
    Button-Druck ausgelöst, nie periodisch (siehe coordinator.py).
    """

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {"outputFormat": "JSON", **params}
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(f"{EFA_BASE_URL}/{path}", params=query)
        except Exception as err:  # noqa: BLE001
            raise VvsEfaError(f"Anfrage an efa.vvs.de fehlgeschlagen: {err}") from err

        if resp.status != 200:
            raise VvsEfaError(f"efa.vvs.de antwortete mit Status {resp.status}")

        try:
            # EFA liefert den Content-Type "text/html", obwohl der Inhalt
            # JSON ist - content_type=None unterdrückt aiohttps deswegen
            # sonst ausgelöste ContentTypeError.
            return await resp.json(content_type=None)
        except Exception as err:  # noqa: BLE001
            raise VvsEfaError(f"Ungültige Antwort von efa.vvs.de: {err}") from err

    async def search_locations(self, query: str, *, results: int = 5) -> list[dict[str, Any]]:
        """Sucht Haltestellen anhand ihres Namens (für die Zielhaltestellen-Auswahl)."""
        data = await self._request(
            "XSLT_STOPFINDER_REQUEST",
            {"locationServerActive": 1, "type_sf": "any", "name_sf": query},
        )
        points = _as_list(data.get("stopFinder", {}).get("points"), singular_key="point")
        stops = [p for p in points if p.get("anyType") == "stop"][:results]
        return [
            {"id": stop["ref"]["id"], "name": _fix_mojibake(stop.get("object") or stop.get("name"))}
            for stop in stops
            if stop.get("ref", {}).get("id")
        ]

    async def nearby_stops(
        self, latitude: float, longitude: float, *, results: int = 5, distance: int | None = None
    ) -> list[dict[str, Any]]:
        """Liefert die nächstgelegenen Haltestellen zu einer Koordinate, nach Distanz sortiert."""
        data = await self._request(
            "XSLT_COORD_REQUEST",
            {
                "coord": f"{longitude}:{latitude}:WGS84[dd]",
                "coordListOutputFormat": "STRING",
                "max": results,
                "inclFilter": 1,
                "type_1": "STOP",
                "radius_1": distance or 1000,
            },
        )
        pins = _as_list(data.get("pins"))
        stops = [p for p in pins if p.get("type") == "STOP"]
        return [{"id": stop["id"], "name": _fix_mojibake(stop.get("desc"))} for stop in stops]

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
            "coordOutputFormat": "WGS84",
            "type_origin": "stop",
            "name_origin": origin_id,
            "type_destination": "stop",
            "name_destination": destination_id,
            "itdTripDateTimeDepArr": "dep",
            "calcNumberOfTrips": results,
        }
        if departure is not None:
            params["itdDate"] = departure.strftime("%Y%m%d")
            params["itdTime"] = departure.strftime("%H%M")
        data = await self._request("XSLT_TRIP_REQUEST2", params)
        return _as_list(data.get("trips"))


def _point_datetime(point: dict[str, Any], *, realtime: bool) -> str | None:
    dt = point.get("dateTime") or {}
    date_key, time_key = ("rtDate", "rtTime") if realtime else ("date", "time")
    date, time = dt.get(date_key), dt.get(time_key)
    if not date or not time:
        return None
    try:
        return datetime.strptime(f"{date} {time}", "%d.%m.%Y %H:%M").isoformat()
    except ValueError:
        return None


def summarize_journey(trip: dict[str, Any]) -> dict[str, Any]:
    """Fasst ein EFA-Trip-Objekt zu einer flachen Timetable-Zeile zusammen."""
    legs = _as_list(trip.get("legs"))
    transit_legs = [leg for leg in legs if leg.get("mode")]
    first_leg = transit_legs[0] if transit_legs else (legs[0] if legs else {})
    last_leg = transit_legs[-1] if transit_legs else (legs[-1] if legs else {})

    first_points = _as_list(first_leg.get("points"))
    last_points = _as_list(last_leg.get("points"))
    departure_point = next((p for p in first_points if p.get("usage") == "departure"), {})
    arrival_point = next((p for p in last_points if p.get("usage") == "arrival"), {})

    planned_departure = _point_datetime(departure_point, realtime=False)
    real_departure = _point_datetime(departure_point, realtime=True) or planned_departure

    delay_minutes = 0
    if planned_departure and real_departure and planned_departure != real_departure:
        delay_minutes = round(
            (datetime.fromisoformat(real_departure) - datetime.fromisoformat(planned_departure)).total_seconds()
            / 60
        )

    duration_minutes = None
    duration = trip.get("duration")
    if duration and ":" in duration:
        hours, minutes = duration.split(":")[:2]
        duration_minutes = int(hours) * 60 + int(minutes)

    mode = first_leg.get("mode") or {}

    return {
        "line": mode.get("name") or mode.get("number"),
        "direction": _fix_mojibake(mode.get("destination")),
        "departure": real_departure,
        "planned_departure": planned_departure,
        "delay_minutes": delay_minutes,
        "platform": departure_point.get("platform"),
        "arrival": _point_datetime(arrival_point, realtime=True) or _point_datetime(arrival_point, realtime=False),
        "planned_arrival": _point_datetime(arrival_point, realtime=False),
        "duration_minutes": duration_minutes,
        "transfers": int(trip.get("interchange", 0) or 0),
        "lines": [leg["mode"]["name"] for leg in transit_legs if leg.get("mode", {}).get("name")],
    }
