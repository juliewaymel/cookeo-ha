"""Config flow Cookeo BLE (découverte Bluetooth ou MAC manuelle)."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN


class CookeoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._addr: str | None = None
        self._name: str = "Cookeo"

    async def async_step_bluetooth(self, info: BluetoothServiceInfoBleak):
        await self.async_set_unique_id(info.address)
        self._abort_if_unique_id_configured()
        self._addr = info.address
        self._name = info.name or "Cookeo"
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=self._name, data={CONF_ADDRESS: self._addr})
        return self.async_show_form(step_id="confirm", description_placeholders={"name": self._name})

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ADDRESS])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Cookeo", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
        )
