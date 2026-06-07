"""Boutons Cookeo : Stop, OK, Demander l'état."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BUTTONS = [
    ("stop", "Arrêter la recette", "mdi:stop", "stop_recipe"),
    ("ok", "Valider (OK)", "mdi:check", "send_ok"),
    ("state", "Demander l'état", "mdi:refresh", "ask_state"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(CookeoButton(entry, client, *b) for b in BUTTONS)


class CookeoButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, client, key, name, icon, method) -> None:
        self._client = client
        self._method = method
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_press(self) -> None:
        try:
            await getattr(self._client, self._method)()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Cookeo action %s échouée: %s", self._method, err)
