"""Constantes Cookeo BLE.

Reverse-engineered depuis l'app « Mon Cookeo » (com.groupeseb.moncookeo).
Protocole BLE en clair, trames hex + CRC16-CCITT. Pilotage prouvé 07/06/2026.

Structure d'une trame (octets, 0-based) :
    [0] TYPE       0 = données, 6 = ACK, 21 = NAK
    [1] LEN        nombre d'octets de payload (hors TYPE/LEN/CRC)
    [2] DATA_1     catégorie (0 état, 1 biblio, 2 recette, 3 spécifique, 4 SAV)
    [3] DATA_2     état / écran courant (voir STATE_MAP)
    [4] DATA_3     menu (voir MENU_MAP)
    [5] DATA_4     mode de cuisson (voir MODE_MAP) — ou code erreur si état 19/20
    [6..8]  temps total de cuisson (secondes, big-endian) — états cuisson/maintien
    [9..11] temps écoulé (secondes, big-endian)
    [12..15] id recette en cours (big-endian)
    [16] index d'étape de la recette
    [17] nombre de convives / portions
    [-2:] CRC16-CCITT (poly 0x1021, init 0x0000)
"""

DOMAIN = "cookeo"

# --- GATT (service propriétaire Cookeo) ---
SERVICE_UUID = "3c63cc60-364a-11e3-808b-0002a5d5c51b"
WRITE_UUID = "471846e0-364a-11e3-a7ad-0002a5d5c51b"   # commandes (write)
NOTIFY_UUID = "4fcc0f60-364a-11e3-98e0-0002a5d5c51b"  # état/réponses (read + notify)
ACCESS_UUID = "672b49c0-d053-11e3-ad6e-0002a5d5c51b"  # déverrouillage (write)

# Code d'accès à écrire sur ACCESS_UUID (16 octets 00..0F), AVANT les notifications.
ACCESS_CODE = bytes(range(16))

DEFAULT_NAME = "Cookeo"
LOCAL_NAME = "BLuE Cookeo"

# Clé d'option : clé API catalogue SEB (recherche). L'envoi par UUID/URL reste public.
CONF_API_KEY = "api_key"

# --- Types de trame (octet 0) ---
TYPE_DATA = 0
TYPE_ACK = 6
TYPE_NAK = 21

# --- Catégorie DATA_1 (octet 2) ---
CAT_STATE = 0
CAT_BIBLIO = 1
CAT_RECIPE = 2
CAT_SPE = 3
CAT_SAV = 4
CATEGORY = {
    CAT_STATE: "état",
    CAT_BIBLIO: "bibliothèque",
    CAT_RECIPE: "recette",
    CAT_SPE: "spécifique",
    CAT_SAV: "SAV",
}

# --- Commandes (payload hex complet TYPE+LEN+DATA, AVANT ajout auto du CRC16) ---
CMD_ASK_STATE = "00020065"
CMD_ASK_CONFIG = "00020301"
CMD_ASK_RECIPE_VERSION = "0002030B"
CMD_STOP_RECIPE = "0002030A"
CMD_SEND_OK = "00020303"
CMD_CANCEL_TRANSFER = "00020202"
CMD_ACK = "06"
# Préfixe d'une commande START_RECIPE (000D = type 0 + len 13)
CMD_BEGIN_START_RECIPE = "000D0302"

# --- DATA_2 : état / écran courant (octet 3). Source : CookeoConstants.DATA_2_STATE_* ---
STATE_MAP = {
    0: "inactif",
    1: "insérer la cuve",
    2: "couvercle ouvert",
    3: "couvercle fermé",
    4: "en attente",
    5: "préchauffage",
    6: "décompression",
    7: "cuisson",
    8: "cuisson (couvercle ouvert)",
    9: "arrêt du dorage",
    10: "maintien au chaud",
    11: "maintien au chaud",
    12: "dorage de la viande",
    13: "cuisson d'un aliment",
    14: "ajouter un ingrédient",
    15: "rissolage",
    16: "démarrage de la cuisson",
    17: "info immersion",
    18: "info vapeur",
    19: "erreur",
    20: "erreur (acquittée)",
    21: "choix du départ",
    22: "réglage du temps de cuisson",
    23: "ajouter de l'eau",
    24: "mijotage (couvercle fermé)",
    25: "temps de mijotage",
    26: "choix du mijotage",
    27: "fin du mijotage",
    30: "choix de la catégorie",
    31: "choix de la recette",
    32: "choix du nombre de convives",
    33: "récapitulatif",
    34: "liste des ingrédients",
    35: "démarrage de la recette",
    36: "fin de cuisson",
    37: "prolonger la cuisson",
    40: "réglages",
    41: "langues",
    42: "pays",
    43: "unités",
    44: "écran",
    45: "son",
    46: "luminosité (démo)",
    47: "luminosité",
    48: "démo",
    49: "code démo",
    50: "bluetooth",
    51: "suppression",
    52: "liste des bibliothèques",
    53: "liste des recettes",
    60: "mode manuel",
    61: "temps de cuisson",
    62: "heure",
    63: "heure de fin",
    64: "vider le réservoir",
    65: "confirmer le vidage",
    66: "niveau de dorage",
    67: "fin du dorage",
    70: "type d'ingrédient",
    71: "choix de l'ingrédient",
    72: "choix du morceau",
    73: "choix du poids",
    74: "choix de la quantité",
    75: "départ différé",
    80: "choix d'extinction",
    81: "animation de démarrage",
    82: "animation d'extinction",
    83: "menu principal",
    84: "veille",
    85: "reprise",
    86: "reprise du dorage",
    87: "annuler la reprise",
    90: "menu des recettes",
    91: "choix catégorie bibliothèque",
}

# États pendant lesquels le Cookeo chauffe activement.
COOKING_STATES = {5, 6, 7, 8, 12, 13, 15, 16, 24, 25}
# États « maintien au chaud » (recette terminée mais réchaud actif).
KEEP_WARM_STATES = {10, 11}
# États « recette/cuisson démarrée » (panneau actif, suivi pertinent).
ERROR_STATES = {19, 20}

# --- DATA_3 : menu (octet 4). Source : CookeoConstants.DATA_3_MENU_* ---
MENU_MAP = {
    0: "ingrédients",
    1: "recettes",
    2: "bibliothèques",
    3: "réglages",
    4: "extinction",
    5: "manuel",
    6: "autre",
}

# --- DATA_4 : mode de cuisson (octet 5). Source : CookeoConstants.DATA_4_MODE_* ---
MODE_MAP = {
    0: "cuisson sous pression",
    1: "cuisson douce",
    2: "mijotage",
    3: "cuisson au four",
    4: "maintien au chaud",
    5: "réchauffage",
    6: "autre",
}
# Modes pour lesquels l'octet 6 porte un pourcentage de progression.
PROGRESS_MODES = {0, 3, 5}

# --- Type de plat (course) pour START_RECIPE. Source : RecipeCookeoBleRequest.startRecipe ---
COURSE_TYPE = {
    "starter": "01",    # entrée
    "entree": "01",
    "main": "02",       # plat
    "main_course": "02",
    "plat": "02",
    "dessert": "00",
    "express": "03",
    "secondi": "04",
}
DEFAULT_COURSE = "02"  # plat

# --- Programmes de cuisson manuelle (technicalId). Source : CookeoConstants.Program ---
PROGRAMS = {
    "browning_low": "200143",
    "browning_medium": "200144",
    "browning_high": "200063",
    "keep_warm_iot": "200065",
    "cooking_ultra_high_pressure": "200068",
    "cooking_high_pressure_iot": "200067",
    "cooking_low_pressure_iot": "200066",
    "steam_low": "200145",
    "very_high_steam": "200146",
    "simmering_low": "200064",
    "simmering_medium": "200062",
    "simmering_high": "200142",
    "browning": "200159",
    "cooking_high_pressure": "200156",
    "cooking_low_pressure": "200157",
    "slow_cooking": "200158",
    "simmering": "200160",
    "keep_warm": "200161",
    "reheat": "REHEAT",
}

# Locale par défaut envoyée dans l'en-tête de transfert recette.
DEFAULT_LANG = "fr"
DEFAULT_REGION = "FR"

# --- API SEB (catalogue + binaires recette .cok, /statics public sans auth) ---
SEB_API = "https://sebplatform.api.groupe-seb.com"
RECIPE_ENDPOINT = SEB_API + "/common-api/v3/recipes/PRO/{variant_id}/"
BINARY_URL = SEB_API + "/statics/original/{uuid}.cok"

# Délai de rafraîchissement par défaut du coordinator (secondes).
DEFAULT_SCAN_INTERVAL = 20
