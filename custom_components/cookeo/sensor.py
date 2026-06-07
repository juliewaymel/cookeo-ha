"""Capteur d'état Cookeo — décode les trames de notification."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .cookeo_client import decode_frame

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CookeoStateSensor(entry, client)])


class CookeoStateSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "État"
    _attr_icon = "mdi:pot-steam"

    def __init__(self, entry: ConfigEntry, client) -> None:
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_state"
        self._attr_native_value = "inconnu"
        self._attr_extra_state_attributes = {}
        client._notify_cb = self._on_frame

    def _on_frame(self, data: bytes) -> None:
        info = decode_frame(data)
        self._attr_native_value = info.get("etat") or info.get("categorie") or info.get("type", "?")
        self._attr_extra_state_attributes = info
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        try:
            await self._client.connect()
            await self._client.ask_state()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Connexion Cookeo échouée: %s", err)
