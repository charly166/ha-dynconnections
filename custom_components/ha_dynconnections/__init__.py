"""HA DynConnections – dynamische ÖPNV-Verbindungsauskunft (VVS-EFA-Backend)."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VvsEfaClient
from .const import (
    CARD_FILENAME,
    CARD_VERSION,
    CONF_DESTINATION_ID,
    CONF_DESTINATION_NAME,
    DOMAIN,
    PLATFORMS,
    STATIC_BASE_PATH,
)
from .coordinator import DynConnectionsCoordinator
from .frontend import LovelaceResourceRegistration

_LOGGER = logging.getLogger(__name__)

WWW_DIR = Path(__file__).parent / "www"
CARD_URL_PATH = f"{STATIC_BASE_PATH}/{CARD_FILENAME}?v={CARD_VERSION}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = VvsEfaClient(session)

    coordinator = DynConnectionsCoordinator(
        hass,
        client,
        entry.data[CONF_DESTINATION_ID],
        entry.data[CONF_DESTINATION_NAME],
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "entry": entry,
    }

    # Karten-Bereitstellung nur beim allerersten Setup registrieren.
    if len(hass.data[DOMAIN]) == 1:
        await _async_register_static_files(hass)
        # Erst NACH dem Setup versuchen (siehe ausführliche Begründung im
        # Schwesterprojekt HA MoviesDB, __init__.py) - bewusst nicht
        # awaited/blockierend.
        hass.async_create_task(LovelaceResourceRegistration(hass).async_register())

    # Ändert der Nutzer die Zielhaltestelle/Optionen, wird die Integration
    # einfach neu geladen - einfachster korrekter Weg, um Client/Coordinator
    # mit den neuen Optionen neu aufzusetzen.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Entfernt beim vollständigen Löschen der letzten Config Entry auch die
    Lovelace-Ressource wieder, damit nichts verwaist zurückbleibt."""
    if not hass.data.get(DOMAIN):
        await LovelaceResourceRegistration(hass).async_unregister()


async def _async_register_static_files(hass: HomeAssistant) -> None:
    """Stellt den www/-Ordner (Karte) statisch bereit."""
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_BASE_PATH, str(WWW_DIR), cache_headers=True)]
    )
    _LOGGER.debug("HA DynConnections: Karte wird ausgeliefert unter %s", CARD_URL_PATH)
