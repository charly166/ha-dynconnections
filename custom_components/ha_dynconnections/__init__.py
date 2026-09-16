"""HA DynConnections – dynamische ÖPNV-Verbindungsauskunft (VVS-EFA-Backend)."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VvsEfaClient
from .const import CARD_FILENAME, CARD_VERSION, DOMAIN, STATIC_BASE_PATH
from .frontend import LovelaceResourceRegistration
from .websocket_api import async_register_commands

_LOGGER = logging.getLogger(__name__)

WWW_DIR = Path(__file__).parent / "www"
CARD_URL_PATH = f"{STATIC_BASE_PATH}/{CARD_FILENAME}?v={CARD_VERSION}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = VvsEfaClient(session)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["client"] = client

    async_register_commands(hass)
    await _async_register_static_files(hass)
    # Erst NACH dem Setup versuchen (siehe ausführliche Begründung im
    # Schwesterprojekt HA MoviesDB, __init__.py) - bewusst nicht
    # awaited/blockierend.
    hass.async_create_task(LovelaceResourceRegistration(hass).async_register())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.pop(DOMAIN, None)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Entfernt beim Löschen der Config Entry auch die Lovelace-Ressource wieder."""
    await LovelaceResourceRegistration(hass).async_unregister()


async def _async_register_static_files(hass: HomeAssistant) -> None:
    """Stellt den www/-Ordner (Karte) statisch bereit."""
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_BASE_PATH, str(WWW_DIR), cache_headers=True)]
    )
    _LOGGER.debug("HA DynConnections: Karte wird ausgeliefert unter %s", CARD_URL_PATH)
