"""Konstanten für die HA DynConnections Integration."""

DOMAIN = "ha_dynconnections"

CONF_DEVICE_TRACKER = "device_tracker"
CONF_DESTINATION_ID = "destination_id"
CONF_DESTINATION_NAME = "destination_name"
CONF_NEARBY_RESULTS = "nearby_results"
CONF_NEARBY_DISTANCE = "nearby_distance"

DEFAULT_NEARBY_RESULTS = 5
DEFAULT_NEARBY_DISTANCE = 1000  # Meter

JOURNEY_RESULTS = 5

TRANSPORT_REST_BASE_URL = "https://v6.db.transport.rest"

PLATFORMS = ["sensor", "select", "datetime", "button"]

CARD_FILENAME = "ha-dynconnections-card.js"
STATIC_BASE_PATH = f"/{DOMAIN}"

# Wird bei jeder inhaltlichen Änderung der Karte hochgezählt, siehe frontend.py.
CARD_VERSION = "1"
