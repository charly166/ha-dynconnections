"""Konstanten für die HA DynConnections Integration."""

DOMAIN = "ha_dynconnections"

DEFAULT_NEARBY_RESULTS = 5
DEFAULT_NEARBY_DISTANCE = 1000  # Meter

JOURNEY_RESULTS = 5

# VVS' eigener EFA-Server (dieselbe Schnittstelle, die auch efa.vvs.de/vvs
# als öffentliche Fahrplanauskunft-Website selbst nutzt). Bewusst statt
# v6.db.transport.rest gewählt, nachdem die zugrunde liegende DB-HAFAS-API
# dort abgeschaltet wurde (siehe README, Abschnitt "Datenquelle").
EFA_BASE_URL = "https://efa.vvs.de/vvs"

# Keine Entity-Plattformen: alle Bedienung läuft über die Karte, die per
# WebSocket-Befehle (websocket_api.py) mit der Integration spricht.
PLATFORMS: list[str] = []

CARD_FILENAME = "ha-dynconnections-card.js"
STATIC_BASE_PATH = f"/{DOMAIN}"

# Wird bei jeder inhaltlichen Änderung der Karte hochgezählt, siehe frontend.py.
CARD_VERSION = "5"
