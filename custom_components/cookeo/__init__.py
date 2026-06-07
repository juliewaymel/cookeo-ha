"""Intégration Cookeo BLE pour Home Assistant."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .cookeo_client import CookeoClient

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    address = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    client = CookeoClient(ble_device or address)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


def _first_client(hass: HomeAssistant) -> CookeoClient | None:
    data = hass.data.get(DOMAIN, {})
    return next(iter(data.values()), None) if data else None


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "send_command"):
        return

    async def handle_send_command(call: ServiceCall) -> None:
        client = _first_client(hass)
        if client:
            await client.send_command(call.data["command"].replace(" ", ""))

    async def handle_send_recipe(call: ServiceCall) -> None:
        """Expérimental : télécharge un .cok et le transfère au Cookeo."""
        client = _first_client(hass)
        if not client:
            return
        session = async_get_clientsession(hass)
        async with session.get(call.data["url"]) as resp:
            data = await resp.read()
        _LOGGER.info("Recette .cok téléchargée (%d octets), transfert…", len(data))
        await client.transfer_binary(data, is_recipe=True)

    hass.services.async_register(
        DOMAIN, "send_command",
        handle_send_command,
        schema=vol.Schema({vol.Required("command"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN, "send_recipe",
        handle_send_recipe,
        schema=vol.Schema({vol.Required("url"): cv.url}),
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if client:
        await client.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
