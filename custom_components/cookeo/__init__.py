"""Intégration Cookeo BLE pour Home Assistant."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_KEY, DOMAIN
from .cookeo_client import CookeoClient
from .coordinator import CookeoCoordinator
from . import recipe_api

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    name = entry.title or "Cookeo"

    def _get_device():
        return bluetooth.async_ble_device_from_address(hass, address, connectable=True)

    client = CookeoClient(address, get_device=_get_device, name=name)
    coordinator = CookeoCoordinator(hass, client, name, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # 1ère tentative non bloquante (le Cookeo peut être éteint / hors portée)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001
        _LOGGER.info("Cookeo non joignable au démarrage (%s) — réessai en tâche de fond", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    _register_services(hass)
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _first_coordinator(hass: HomeAssistant, entry_id: str | None = None) -> CookeoCoordinator | None:
    data: dict = hass.data.get(DOMAIN, {})
    if entry_id and entry_id in data:
        return data[entry_id]
    return next(iter(data.values()), None) if data else None


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "send_command"):
        return

    async def handle_send_command(call: ServiceCall) -> None:
        coord = _first_coordinator(hass, call.data.get("entry_id"))
        if coord:
            await coord.client.send_command(call.data["command"])
            await coord.async_request_refresh()

    async def handle_start_recipe(call: ServiceCall) -> None:
        coord = _first_coordinator(hass, call.data.get("entry_id"))
        if coord:
            await coord.client.start_recipe(
                int(call.data["recipe_id"]),
                course=call.data.get("course", "main"),
                quantity=int(call.data.get("quantity", 2)),
            )
            await coord.async_request_refresh()

    async def handle_send_recipe(call: ServiceCall) -> ServiceResponse:
        coord = _first_coordinator(hass, call.data.get("entry_id"))
        if not coord:
            return {"error": "Aucun Cookeo configuré"}
        session = async_get_clientsession(hass)
        target = call.data.get("url") or call.data.get("uuid")
        data = await recipe_api.download_cok(session, target)
        result = await coord.client.send_recipe_binary(
            data,
            recipe_id=int(call.data["recipe_id"]),
            version=call.data.get("version", "1.0"),
            category=int(call.data.get("category", 2)),
            start=call.data.get("start", False),
            course=call.data.get("course", "main"),
            quantity=int(call.data.get("quantity", 2)),
        )
        result["bytes"] = len(data)
        await coord.async_request_refresh()
        return result

    async def handle_search_recipe(call: ServiceCall) -> ServiceResponse:
        session = async_get_clientsession(hass)
        coord = _first_coordinator(hass)
        api_key = None
        if coord and coord.config_entry:
            api_key = coord.config_entry.options.get(CONF_API_KEY)
        try:
            results = await recipe_api.search_recipes(
                session, call.data["query"], api_key=api_key
            )
            return {"results": results}
        except PermissionError as err:
            return {"error": str(err), "results": []}

    hass.services.async_register(
        DOMAIN, "send_command", handle_send_command,
        schema=vol.Schema(
            {vol.Required("command"): cv.string, vol.Optional("entry_id"): cv.string}
        ),
    )
    hass.services.async_register(
        DOMAIN, "start_recipe", handle_start_recipe,
        schema=vol.Schema(
            {
                vol.Required("recipe_id"): vol.Coerce(int),
                vol.Optional("course", default="main"): cv.string,
                vol.Optional("quantity", default=2): vol.Coerce(int),
                vol.Optional("entry_id"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN, "send_recipe", handle_send_recipe,
        schema=vol.Schema(
            {
                vol.Exclusive("url", "src"): cv.string,
                vol.Exclusive("uuid", "src"): cv.string,
                vol.Required("recipe_id"): vol.Coerce(int),
                vol.Optional("version", default="1.0"): cv.string,
                vol.Optional("category", default=2): vol.Coerce(int),
                vol.Optional("start", default=False): cv.boolean,
                vol.Optional("course", default="main"): cv.string,
                vol.Optional("quantity", default=2): vol.Coerce(int),
                vol.Optional("entry_id"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, "search_recipe", handle_search_recipe,
        schema=vol.Schema({vol.Required("query"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if coordinator:
        await coordinator.client.disconnect()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not hass.data.get(DOMAIN):
        for svc in ("send_command", "start_recipe", "send_recipe", "search_recipe"):
            hass.services.async_remove(DOMAIN, svc)
    return unloaded
