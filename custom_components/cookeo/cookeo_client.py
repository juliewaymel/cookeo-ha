"""Client BLE Cookeo — handshake, commandes (CRC16), suivi de cuisson, transfert recette.

Séquence prouvée (07/06/2026) :
  1) connexion (le Pi/adaptateur doit être appairé/bondé au Cookeo au préalable)
  2) écrire ACCESS_CODE sur ACCESS_UUID                (déverrouillage)
  3) activer les notifications sur NOTIFY_UUID         (ORDRE crucial : access AVANT notify)
  4) écrire les commandes CRC-framées sur WRITE_UUID   -> réponses sur NOTIFY_UUID

Toutes les trames montantes/descendantes = hex + CRC16-CCITT (poly 0x1021, init 0).
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice

from .const import (
    ACCESS_CODE,
    ACCESS_UUID,
    CATEGORY,
    CAT_RECIPE,
    CAT_STATE,
    CAT_SPE,
    CMD_ACK,
    CMD_ASK_STATE,
    CMD_BEGIN_START_RECIPE,
    CMD_SEND_OK,
    CMD_STOP_RECIPE,
    COOKING_STATES,
    COURSE_TYPE,
    DEFAULT_COURSE,
    DEFAULT_LANG,
    DEFAULT_NAME,
    DEFAULT_REGION,
    ERROR_STATES,
    KEEP_WARM_STATES,
    MENU_MAP,
    MODE_MAP,
    NOTIFY_UUID,
    PROGRESS_MODES,
    STATE_MAP,
    TYPE_ACK,
    TYPE_DATA,
    TYPE_NAK,
    WRITE_UUID,
)

_LOGGER = logging.getLogger(__name__)

CHUNK_BYTES = 17  # octets de données utiles par trame de transfert (MTU 23 -> 20B)


# --------------------------------------------------------------------------- #
#  CRC16 + helpers de trame                                                    #
# --------------------------------------------------------------------------- #
def crc16_ccitt(data: bytes) -> int:
    """CRC16-CCITT (poly 0x1021, init 0x0000) — identique à CRC16Utils de l'app."""
    crc = 0
    for b in data:
        for i in range(8):
            bit = (b >> (7 - i)) & 1
            c15 = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if bit ^ c15:
                crc ^= 0x1021
    return crc & 0xFFFF


def crc16_hex(hex_str: str) -> str:
    """CRC16 d'une chaîne hex -> 4 caractères hex (comme createHexCRC16)."""
    return "%04X" % crc16_ccitt(bytes.fromhex(hex_str))


def frame(hex_cmd: str) -> bytes:
    """Trame complète prête à écrire = payload + CRC16 (big-endian)."""
    hex_cmd = hex_cmd.replace(" ", "")
    return bytes.fromhex(hex_cmd) + crc16_ccitt(bytes.fromhex(hex_cmd)).to_bytes(2, "big")


def _u24(b: bytes, start: int) -> int | None:
    """Entier big-endian sur 3 octets, ou None si hors trame."""
    if len(b) < start + 3:
        return None
    return (b[start] << 16) | (b[start + 1] << 8) | b[start + 2]


def _u32(b: bytes, start: int) -> int | None:
    if len(b) < start + 4:
        return None
    return int.from_bytes(b[start : start + 4], "big")


def decode_frame(data: bytes) -> dict[str, Any]:
    """Décode une trame de notification en dictionnaire lisible (suivi de cuisson).

    Voir l'en-tête de const.py pour la cartographie des octets.
    """
    out: dict[str, Any] = {"raw": data.hex()}
    if not data:
        return out

    t = data[0]
    out["type"] = {TYPE_DATA: "données", TYPE_ACK: "ACK", TYPE_NAK: "NAK"}.get(
        t, f"0x{t:02x}"
    )
    if t != TYPE_DATA or len(data) < 4:
        return out

    cat = data[2]
    state = data[3]
    out["categorie_code"] = cat
    out["categorie"] = CATEGORY.get(cat, str(cat))
    out["etat_code"] = state
    out["etat"] = STATE_MAP.get(state, f"code {state}")

    if len(data) >= 5:
        menu = data[4]
        out["menu_code"] = menu
        out["menu"] = MENU_MAP.get(menu, str(menu))

    # Octet 5 = mode de cuisson (DATA_4) — ou code erreur sur les états 19/20.
    if len(data) >= 6:
        if state in ERROR_STATES:
            out["erreur_code"] = data[5]
        else:
            mode = data[5]
            out["mode_code"] = mode
            out["mode"] = MODE_MAP.get(mode, str(mode))
            # Progression (%) portée par l'octet 6 sur les modes pression/four/réchauffage.
            if mode in PROGRESS_MODES and len(data) >= 7:
                out["progression"] = data[6]

    # Timer de cuisson (états cuisson / maintien / mijotage) : total & écoulé.
    if state in COOKING_STATES or state in KEEP_WARM_STATES:
        total = _u24(data, 6)
        elapsed = _u24(data, 9)
        if total is not None and total != 0xFFFFFF:
            out["temps_total_s"] = total
            if elapsed is not None and elapsed != 0xFFFFFF:
                out["temps_ecoule_s"] = elapsed
                out["temps_restant_s"] = max(0, total - elapsed)
                if total > 0:
                    out["progression"] = min(100, round(elapsed * 100 / total))

    # Identité de la recette en cours (si la trame est assez longue).
    rid = _u32(data, 12)
    if rid is not None and rid not in (0, 0xFFFFFFFF):
        out["recette_id"] = rid
    if len(data) >= 17:
        out["etape"] = data[16]
    if len(data) >= 18:
        out["convives"] = data[17]

    out["en_cuisson"] = state in COOKING_STATES
    out["maintien_chaud"] = state in KEEP_WARM_STATES
    out["recette_active"] = state in COOKING_STATES or state in KEEP_WARM_STATES or bool(
        out.get("recette_id")
    )
    return out


# --------------------------------------------------------------------------- #
#  Client                                                                      #
# --------------------------------------------------------------------------- #
class CookeoClient:
    """Pilote un Cookeo Connect en BLE."""

    def __init__(
        self,
        address: str,
        get_device: Callable[[], BLEDevice | None] | None = None,
        notify_cb: Callable[[bytes], None] | None = None,
        name: str = DEFAULT_NAME,
    ) -> None:
        self._address = address
        self._get_device = get_device
        self._notify_cb = notify_cb
        self._name = name
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._frame_event = asyncio.Event()
        self.last_frame: bytes | None = None

    # -- propriétés -------------------------------------------------------- #
    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def notify_cb(self) -> Callable[[bytes], None] | None:
        return self._notify_cb

    @notify_cb.setter
    def notify_cb(self, cb: Callable[[bytes], None] | None) -> None:
        self._notify_cb = cb

    # -- connexion --------------------------------------------------------- #
    def _resolve_target(self) -> BLEDevice | str:
        if self._get_device is not None:
            device = self._get_device()
            if device is not None:
                return device
        return self._address

    async def connect(self) -> None:
        """Connecte, déverrouille (code d'accès) puis active les notifications."""
        async with self._lock:
            if self.is_connected:
                return
            target = self._resolve_target()
            try:
                # bleak-retry-connector gère reconnexion + cache de services.
                from bleak_retry_connector import (  # noqa: PLC0415
                    BleakClientWithServiceCache,
                    establish_connection,
                )

                if isinstance(target, BLEDevice):
                    self._client = await establish_connection(
                        BleakClientWithServiceCache, target, self._name
                    )
                else:
                    self._client = BleakClient(target)
                    await self._client.connect()
            except ImportError:
                self._client = BleakClient(target)
                await self._client.connect()

            # 1) code d'accès AVANT notify (sinon le Cookeo reste muet)
            await self._client.write_gatt_char(ACCESS_UUID, ACCESS_CODE, response=True)
            # 2) notifications
            await self._client.start_notify(NOTIFY_UUID, self._on_notify)
            await asyncio.sleep(0.4)
            _LOGGER.debug("Cookeo connecté + déverrouillé (%s)", self._address)

    async def disconnect(self) -> None:
        async with self._lock:
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    self._client = None

    # -- notifications ----------------------------------------------------- #
    def _on_notify(self, _char: Any, data: bytearray) -> None:
        self.last_frame = bytes(data)
        self._frame_event.set()
        _LOGGER.debug("Cookeo notify: %s", self.last_frame.hex())
        if self._notify_cb:
            self._notify_cb(bytes(data))

    async def _wait_for_frame(self, timeout: float = 5.0) -> bytes | None:
        """Attend la prochaine notification (modèle requête/réponse)."""
        self._frame_event.clear()
        try:
            await asyncio.wait_for(self._frame_event.wait(), timeout)
        except asyncio.TimeoutError:
            return None
        return self.last_frame

    # -- écriture ---------------------------------------------------------- #
    async def _write(self, payload: bytes, response: bool = True) -> None:
        if not self.is_connected:
            await self.connect()
        await self._client.write_gatt_char(WRITE_UUID, payload, response=response)

    async def send_command(self, hex_cmd: str) -> None:
        """Envoie une commande hex brute (le CRC16 est ajouté automatiquement)."""
        await self._write(frame(hex_cmd))

    async def send_raw_access(self) -> None:
        """(Re)écrit le code d'accès — utile après reconnexion."""
        if not self.is_connected:
            await self.connect()
        await self._client.write_gatt_char(ACCESS_UUID, ACCESS_CODE, response=True)

    # -- commandes de haut niveau ----------------------------------------- #
    async def ask_state(self) -> bytes | None:
        await self.send_command(CMD_ASK_STATE)
        return await self._wait_for_frame()

    async def stop_recipe(self) -> None:
        await self.send_command(CMD_STOP_RECIPE)

    async def send_ok(self) -> None:
        await self.send_command(CMD_SEND_OK)

    async def send_ack(self) -> None:
        await self.send_command(CMD_ACK)

    async def start_recipe(
        self, recipe_id: int, course: str = "main", quantity: int = 2
    ) -> None:
        """Lance une recette résidente/transférée par son id.

        Trame : 000D0302 01 <course> <id 4o> 00000000 <quantité>  (+ CRC16).
        """
        course_hex = COURSE_TYPE.get(str(course).lower(), DEFAULT_COURSE)
        payload = (
            CMD_BEGIN_START_RECIPE
            + "01"
            + course_hex
            + f"{int(recipe_id) & 0xFFFFFFFF:08X}"
            + "00000000"
            + f"{int(quantity) & 0xFF:02X}"
        )
        _LOGGER.debug("start_recipe frame=%s", payload)
        await self.send_command(payload)

    # -- transfert d'une recette binaire .cok ----------------------------- #
    def build_transfer_header(
        self,
        data: bytes,
        recipe_id: int,
        version: str,
        category: int,
        lang: str = DEFAULT_LANG,
        region: str = DEFAULT_REGION,
    ) -> str:
        """Construit l'en-tête 000F… d'un transfert de recette (askTransferBinary)."""
        major, _, minor = version.partition(".")
        minor = minor or "0"
        n_chunks = math.ceil(len(data) / CHUNK_BYTES)
        lang_hex = lang.lower().encode().hex().upper()
        region_hex = region.upper().encode().hex().upper()
        header = (
            "000F0200"
            + f"{int(recipe_id) & 0xFFFFFFFF:08X}"
            + f"{int(major) & 0xFF:02X}"
            + f"{int(minor) & 0xFF:02X}"
            + lang_hex.rjust(4, "0")
            + region_hex.rjust(4, "0")
            + f"{n_chunks & 0xFFFF:04X}"
            + f"{int(category) & 0xFF:02X}"
        )
        return header

    def build_transfer_chunks(self, data: bytes, is_recipe: bool = True) -> list[bytes]:
        """Découpe le binaire en trames 03 + 17 octets + CRC16 (transferBinary)."""
        prefix = "03" if is_recipe else "02"
        hexdata = data.hex()
        n_chunks = math.ceil(len(data) / CHUNK_BYTES)
        chunks: list[bytes] = []
        for i in range(n_chunks):
            seg = hexdata[i * 34 : i * 34 + 34].ljust(34, "0")
            body = prefix + seg
            chunks.append(bytes.fromhex(body + crc16_hex(body)))
        return chunks

    async def send_recipe_binary(
        self,
        data: bytes,
        recipe_id: int,
        version: str = "1.0",
        category: int = 2,
        lang: str = DEFAULT_LANG,
        region: str = DEFAULT_REGION,
        start: bool = False,
        course: str = "main",
        quantity: int = 2,
    ) -> dict[str, Any]:
        """Transfère une recette .cok : en-tête -> chunks -> (option) démarrage.

        Expérimental : nécessite un Cookeo appairé. Le `recipe_id`/`version`/`category`
        proviennent des métadonnées du catalogue SEB.
        """
        if not self.is_connected:
            await self.connect()

        header = self.build_transfer_header(
            data, recipe_id, version, category, lang, region
        )
        chunks = self.build_transfer_chunks(data, is_recipe=True)
        _LOGGER.info(
            "Transfert recette id=%s v=%s : header=%s, %d chunks",
            recipe_id,
            version,
            header,
            len(chunks),
        )

        # 1) en-tête d'autorisation
        await self.send_command(header)
        authorize = await self._wait_for_frame(timeout=6.0)
        _LOGGER.debug("Réponse autorisation transfert : %s", authorize.hex() if authorize else "—")

        # 2) chunks (write-with-response = contrôle de flux)
        for idx, chunk in enumerate(chunks):
            await self._write(chunk)
            if idx % 8 == 0:
                await asyncio.sleep(0.02)

        result: dict[str, Any] = {
            "recipe_id": recipe_id,
            "chunks": len(chunks),
            "authorized": authorize.hex() if authorize else None,
        }

        # 3) démarrage optionnel
        if start:
            await asyncio.sleep(0.3)
            await self.start_recipe(recipe_id, course=course, quantity=quantity)
            result["started"] = True
        return result

    # -- appairage & test (config flow) ----------------------------------- #
    async def pair(self) -> bool:
        """Tente d'appairer/bonder l'adaptateur au Cookeo (mettre le Cookeo en appairage).

        Sur BlueZ (HAOS), mappe sur Device1.Pair. Selon le backend, l'appairage manuel
        `bluetoothctl` (connect puis pair) peut rester nécessaire.
        """
        target = self._resolve_target()
        if not self.is_connected:
            self._client = BleakClient(target)
            await self._client.connect()
        try:
            ok = await self._client.pair()  # type: ignore[func-returns-value]
            return bool(ok) if ok is not None else True
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Appairage Cookeo échoué : %s", err)
            return False

    async def test_connection(self) -> dict[str, Any]:
        """Connexion de bout en bout : déverrouillage + ask_state + décodage."""
        result: dict[str, Any] = {"connected": False, "answered": False}
        try:
            await self.connect()
            result["connected"] = self.is_connected
            data = await self.ask_state()
            if data:
                result["answered"] = True
                result["frame"] = data.hex()
                result["decoded"] = decode_frame(data)
        except Exception as err:  # noqa: BLE001
            result["error"] = str(err)
        return result
