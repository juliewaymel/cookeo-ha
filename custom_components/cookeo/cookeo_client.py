"""Client BLE Cookeo — handshake + commandes (CRC16-CCITT).

Séquence prouvée :
  1) connexion (appareil appairé/bondé au préalable)
  2) écrire ACCESS_CODE sur ACCESS_UUID   (déverrouillage)
  3) activer les notifications sur NOTIFY_UUID   (ORDRE crucial : access AVANT notify)
  4) écrire les commandes CRC-framées sur WRITE_UUID -> réponses sur NOTIFY_UUID
"""
from __future__ import annotations

import asyncio
import logging

from bleak import BleakClient

from .const import ACCESS_CODE, ACCESS_UUID, NOTIFY_UUID, WRITE_UUID

_LOGGER = logging.getLogger(__name__)


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


def frame(hex_cmd: str) -> bytes:
    """Construit la trame finale : payload + CRC16 (big-endian)."""
    data = bytes.fromhex(hex_cmd)
    return data + crc16_ccitt(data).to_bytes(2, "big")


class CookeoClient:
    """Pilote un Cookeo Connect en BLE."""

    def __init__(self, address_or_device, notify_cb=None) -> None:
        self._target = address_or_device
        self._notify_cb = notify_cb
        self._client: BleakClient | None = None
        self.last_frame: bytes | None = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect(self) -> None:
        self._client = BleakClient(self._target)
        await self._client.connect()
        # 1) déverrouillage : code d'accès sur la char ACCESS
        await self._client.write_gatt_char(ACCESS_UUID, ACCESS_CODE, response=True)
        # 2) notifications APRÈS le code d'accès
        await self._client.start_notify(NOTIFY_UUID, self._on_notify)
        await asyncio.sleep(0.4)
        _LOGGER.debug("Cookeo connecté + déverrouillé")

    def _on_notify(self, _char, data: bytearray) -> None:
        self.last_frame = bytes(data)
        _LOGGER.debug("Cookeo notify: %s", self.last_frame.hex())
        if self._notify_cb:
            self._notify_cb(bytes(data))

    async def send_command(self, hex_cmd: str) -> None:
        if not self.is_connected:
            raise RuntimeError("Cookeo non connecté")
        await self._client.write_gatt_char(WRITE_UUID, frame(hex_cmd), response=True)

    # raccourcis
    async def ask_state(self) -> None:
        await self.send_command("00020065")

    async def stop_recipe(self) -> None:
        await self.send_command("0002030A")

    async def send_ok(self) -> None:
        await self.send_command("00020303")

    async def transfer_binary(self, data: bytes, is_recipe: bool = True) -> None:
        """Transfère un binaire .cok (chunks de 17 octets, type + CRC16 par chunk)."""
        prefix = "03" if is_recipe else "02"
        hexdata = data.hex()
        chunks = -(-len(data) // 17)  # ceil
        for i in range(chunks):
            seg = hexdata[i * 34 : i * 34 + 34].ljust(34, "0")
            payload = prefix + seg
            full = payload + "%04X" % crc16_ccitt(bytes.fromhex(payload))
            await self._client.write_gatt_char(WRITE_UUID, bytes.fromhex(full), response=True)

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
