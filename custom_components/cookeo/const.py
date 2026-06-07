"""Constantes Cookeo BLE.

Reverse-engineered depuis l'app « Mon Cookeo » (com.groupeseb.moncookeo).
Protocole BLE en clair, trames hex + CRC16-CCITT. Pilotage prouvé 07/06/2026.
"""

DOMAIN = "cookeo"

# --- GATT (service propriétaire Cookeo) ---
SERVICE_UUID = "3c63cc60-364a-11e3-808b-0002a5d5c51b"
WRITE_UUID = "471846e0-364a-11e3-a7ad-0002a5d5c51b"   # commandes (write)
NOTIFY_UUID = "4fcc0f60-364a-11e3-98e0-0002a5d5c51b"  # état/réponses (read + notify)
ACCESS_UUID = "672b49c0-d053-11e3-ad6e-0002a5d5c51b"  # déverrouillage (write)

# Code d'accès à écrire sur ACCESS_UUID pour déverrouiller la communication
# (16 octets 00 01 02 ... 0F), AVANT d'activer les notifications.
ACCESS_CODE = bytes(range(16))

# --- Commandes (payload hex, AVANT ajout auto du CRC16) ---
# Format trame : [LEN sur 2 octets][payload]  puis  + CRC16-CCITT(2 octets)
CMD_ASK_STATE = "00020065"
CMD_ASK_CONFIG = "00020301"
CMD_ASK_RECIPE_VERSION = "0002030B"
CMD_STOP_RECIPE = "0002030A"
CMD_SEND_OK = "00020303"
CMD_CANCEL_TRANSFER = "00020202"

# Programmes de cuisson (technicalId Cookeo) — cf CookeoConstants.Program
PROGRAMS = {
    "browning_low": "PROGRAM_200143",
    "browning_medium": "PROGRAM_200144",
    "browning_high": "PROGRAM_200063",
    "keep_warm": "PROGRAM_200065",
    "pressure_ultra_high": "PROGRAM_200068",
    "pressure_high": "PROGRAM_200067",
    "pressure_low": "PROGRAM_200066",
}

# API SEB (catalogue + binaires recette .cok, /statics public sans auth)
SEB_API = "https://sebplatform.api.groupe-seb.com"
RECIPE_ENDPOINT = SEB_API + "/common-api/v3/recipes/PRO/{variant_id}/"
BINARY_URL = SEB_API + "/statics/original/{uuid}.cok"
