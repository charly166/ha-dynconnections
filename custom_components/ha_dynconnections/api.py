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

from .const import DEFAULT_NEARBY_DISTANCE, EFA_BASE_URL

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


# EFAs feste "MOT" (means of transport)-Typennummerierung, wie sie z.B. auch
# als Filter-Parameter (excludedMeans) in der Trip-Anfrage auftaucht. Wird
# genutzt, um pro Haltestelle anzuzeigen, welche Verkehrsmittel dort
# abfahren (wie auf vvs.de/efa.vvs.de selbst, wo die Haltestellenauswahl
# entsprechende kleine Icons neben jedem Treffer zeigt).
_MOT_CATEGORY: dict[int, str] = {
    0: "zug", 1: "sbahn", 2: "ubahn", 3: "stadtbahn", 4: "tram",
    5: "bus", 6: "bus", 7: "bus", 8: "seilbahn", 9: "schiff",
    10: "bus", 13: "zug", 14: "zug", 15: "zug", 16: "zug",
    17: "bus", 18: "zug", 19: "bus", 20: "bus", 21: "bus",
}


def _stop_modes(codes: str | None) -> list[str]:
    """Wandelt eine kommagetrennte MOT-Codeliste (z.B. "3,5,11") in eine
    deduplizierte Liste bekannter Kategorien um ("sonstige"/unbekannte
    Codes werden verworfen, da dafür kein sinnvolles Icon existiert)."""
    if not codes:
        return []
    result: list[str] = []
    for part in codes.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        category = _MOT_CATEGORY.get(int(part))
        if category and category not in result:
            result.append(category)
    return result


def _stop_attr(stop: dict[str, Any], name: str) -> str | None:
    for attr in stop.get("attrs") or []:
        if attr.get("name") == name:
            return attr.get("value")
    return None


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
            {
                "id": stop["ref"]["id"],
                "name": _fix_mojibake(stop.get("object") or stop.get("name")),
                "modes": _stop_modes(stop.get("modes")),
            }
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
                "radius_1": distance or DEFAULT_NEARBY_DISTANCE,
            },
        )
        pins = _as_list(data.get("pins"))
        stops = [p for p in pins if p.get("type") == "STOP"]
        return [
            {
                "id": stop["id"],
                "name": _fix_mojibake(stop.get("desc")),
                "modes": _stop_modes(_stop_attr(stop, "STOP_MOT_LIST")),
            }
            for stop in stops
        ]

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


def _delay_minutes(planned: str | None, real: str | None) -> int:
    if not planned or not real or planned == real:
        return 0
    try:
        return round((datetime.fromisoformat(real) - datetime.fromisoformat(planned)).total_seconds() / 60)
    except ValueError:
        return 0


def _is_walking_leg(mode: dict[str, Any]) -> bool:
    # Fußweg-Etappen (z.B. Umstieg zwischen zwei Bahnsteigen) haben zwar ein
    # "mode"-Objekt, aber weder Liniennamen noch -nummer.
    return mode.get("product") == "Fussweg" or not (mode.get("name") or mode.get("number"))


def _platform(point: dict[str, Any]) -> str | None:
    # EFA nennt das Echtzeit-Gleis "platformName" (nicht "platform") -
    # fällt auf das geplante Gleis zurück, falls (noch) keine Echtzeitdaten
    # für diesen Punkt vorliegen.
    return point.get("platformName") or point.get("plannedPlatformName")


def _leg_summary(leg: dict[str, Any]) -> dict[str, Any]:
    """Fasst eine einzelne Etappe (Leg) für die Detail-Ansicht der Route zusammen."""
    mode = leg.get("mode") or {}
    points = _as_list(leg.get("points"))
    departure_point = next((p for p in points if p.get("usage") == "departure"), {})
    arrival_point = next((p for p in points if p.get("usage") == "arrival"), {})

    if _is_walking_leg(mode):
        try:
            duration_minutes = int(leg["timeMinute"]) if leg.get("timeMinute") else None
        except (TypeError, ValueError):
            duration_minutes = None
        return {
            "walking": True,
            "duration_minutes": duration_minutes,
            "departure_stop": _fix_mojibake(departure_point.get("name")),
            "arrival_stop": _fix_mojibake(arrival_point.get("name")),
        }

    planned_departure = _point_datetime(departure_point, realtime=False)
    real_departure = _point_datetime(departure_point, realtime=True) or planned_departure
    planned_arrival = _point_datetime(arrival_point, realtime=False)
    real_arrival = _point_datetime(arrival_point, realtime=True) or planned_arrival

    return {
        "walking": False,
        "line": mode.get("name") or mode.get("number"),
        "product": mode.get("product"),
        "direction": _fix_mojibake(mode.get("destination")),
        "departure_stop": _fix_mojibake(departure_point.get("name")),
        "departure": real_departure,
        "planned_departure": planned_departure,
        "departure_platform": _platform(departure_point),
        "planned_departure_platform": departure_point.get("plannedPlatformName"),
        "delay_minutes": _delay_minutes(planned_departure, real_departure),
        "arrival_stop": _fix_mojibake(arrival_point.get("name")),
        "arrival": real_arrival,
        "planned_arrival": planned_arrival,
        "arrival_platform": _platform(arrival_point),
        "planned_arrival_platform": arrival_point.get("plannedPlatformName"),
        "arrival_delay_minutes": _delay_minutes(planned_arrival, real_arrival),
    }


def summarize_journey(trip: dict[str, Any]) -> dict[str, Any]:
    """Fasst ein EFA-Trip-Objekt zu einer Timetable-Zeile samt Etappen-Details zusammen."""
    legs = [_leg_summary(leg) for leg in _as_list(trip.get("legs"))]
    transit_legs = [leg for leg in legs if not leg["walking"]]
    first_leg = transit_legs[0] if transit_legs else (legs[0] if legs else {})
    last_leg = transit_legs[-1] if transit_legs else (legs[-1] if legs else {})

    duration_minutes = None
    duration = trip.get("duration")
    if duration and ":" in duration:
        hours, minutes = duration.split(":")[:2]
        duration_minutes = int(hours) * 60 + int(minutes)

    return {
        "line": first_leg.get("line"),
        "product": first_leg.get("product"),
        "direction": first_leg.get("direction"),
        "departure": first_leg.get("departure"),
        "planned_departure": first_leg.get("planned_departure"),
        "delay_minutes": first_leg.get("delay_minutes", 0),
        "platform": first_leg.get("departure_platform"),
        "planned_platform": first_leg.get("planned_departure_platform"),
        "arrival": last_leg.get("arrival"),
        "planned_arrival": last_leg.get("planned_arrival"),
        "arrival_delay_minutes": last_leg.get("arrival_delay_minutes", 0),
        "duration_minutes": duration_minutes,
        "transfers": int(trip.get("interchange", 0) or 0),
        "lines": [leg["line"] for leg in transit_legs if leg.get("line")],
        "legs": legs,
    }
