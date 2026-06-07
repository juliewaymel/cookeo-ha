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

# Code d'accès à écrire sur ACCESS_UUID (16 octets 00..0F), AVANT les notifications.
ACCESS_CODE = bytes(range(16))

# --- Commandes (payload hex, AVANT ajout auto du CRC16) ---
CMD_ASK_STATE = "00020065"
CMD_ASK_CONFIG = "00020301"
CMD_ASK_RECIPE_VERSION = "0002030B"
CMD_STOP_RECIPE = "0002030A"
CMD_SEND_OK = "00020303"
CMD_CANCEL_TRANSFER = "00020202"
CMD_ACK = "06"

# --- Décodage trames (index d'octet 1-based de l'app : byte0=type, byte2=DATA_1, byte3=DATA_2) ---
TYPE_DATA = 0
TYPE_ACK = 6
TYPE_NAK = 21

CATEGORY = {0: "état", 1: "bibliothèque", 2: "recette", 3: "spécifique", 4: "SAV"}

# DATA_2 quand catégorie = état (0). Source : CookeoConstants.DATA_2_STATE_*
STATE_MAP = {
    0: "autre", 1: "insérer la cuve", 2: "couvercle ouvert", 3: "couvercle fermé",
    4: "attente", 5: "préchauffage", 6: "décompression", 7: "cuisson",
    8: "cuisson (ouvert)", 9: "arrêt dorage", 10: "maintien au chaud", 11: "maintien au chaud",
    12: "dorage viande", 13: "cuisson aliment", 14: "ajouter un ingrédient", 15: "rissolage",
    16: "démarrage cuisson", 17: "info immersion", 18: "info vapeur", 19: "erreur",
    20: "erreur OK", 21: "choix départ", 22: "réglage temps de cuisson", 23: "ajouter de l'eau",
    24: "mijotage (fermé)", 25: "temps mijotage", 26: "choix mijotage", 27: "fin mijotage",
    33: "récapitulatif", 35: "démarrage recette", 36: "fin de cuisson", 37: "prolonger cuisson",
    60: "mode manuel", 61: "temps de cuisson", 62: "heure", 63: "heure de fin",
    64: "vider le réservoir", 75: "départ différé", 84: "veille", 85: "reprise",
}

# API SEB (catalogue + binaires recette .cok, /statics public sans auth)
SEB_API = "https://sebplatform.api.groupe-seb.com"
RECIPE_ENDPOINT = SEB_API + "/common-api/v3/recipes/PRO/{variant_id}/"
BINARY_URL = SEB_API + "/statics/original/{uuid}.cok"
