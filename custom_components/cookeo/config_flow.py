"""Config flow Cookeo BLE : découverte Bluetooth / MAC, appairage + test, options."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import CONF_API_KEY, DEFAULT_NAME, DOMAIN
from .cookeo_client import CookeoClient


class CookeoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._addr: str | None = None
        self._name: str = DEFAULT_NAME

    async def async_step_bluetooth(
        self, info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(info.address)
        self._abort_if_unique_id_configured()
        self._addr = info.address
        self._name = info.name or DEFAULT_NAME
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._name, data={CONF_ADDRESS: self._addr}
            )
        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": self._name}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._addr = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(self._addr)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=DEFAULT_NAME, data={CONF_ADDRESS: self._addr}
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return CookeoOptionsFlow(entry)


class CookeoOptionsFlow(OptionsFlow):
    """Options : appairer, tester la connexion, clé API catalogue."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._result: str | None = None

    def _client(self) -> CookeoClient:
        address = self._entry.data[CONF_ADDRESS]

        def _get_device():
            return bluetooth.async_ble_device_from_address(
                self.hass, address, connectable=True
            )

        return CookeoClient(address, get_device=_get_device, name=self._entry.title)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["pair", "test", "settings"],
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bouton « Appairer » : met le Cookeo en appairage puis bonde l'adaptateur."""
        client = self._client()
        ok = False
        error = None
        try:
            ok = await client.pair()
        except Exception as err:  # noqa: BLE001
            error = str(err)
        finally:
            await client.disconnect()
        msg = "✅ Appairage réussi." if ok else f"❌ Échec de l'appairage. {error or ''}"
        return self.async_show_menu(
            step_id="init",
            menu_options=["pair", "test", "settings"],
            description_placeholders={"result": msg},
        )

    async def async_step_test(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bouton « Tester » : connexion + déverrouillage + demande d'état."""
        client = self._client()
        res = await client.test_connection()
        await client.disconnect()
        if res.get("answered"):
            etat = (res.get("decoded") or {}).get("etat", "?")
            msg = f"✅ Cookeo connecté — état : {etat} (trame {res.get('frame')})"
        elif res.get("connected"):
            msg = "🟠 Connecté mais aucune réponse (vérifier l'appairage / le Cookeo allumé)."
        else:
            msg = f"❌ Connexion impossible. {res.get('error', '')}"
        return self.async_show_menu(
            step_id="init",
            menu_options=["pair", "test", "settings"],
            description_placeholders={"result": msg},
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_API_KEY,
                        default=self._entry.options.get(CONF_API_KEY, ""),
                    ): str,
                }
            ),
        )
