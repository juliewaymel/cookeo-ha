"""Coordinator Cookeo : interroge l'état et diffuse le suivi de cuisson aux entités."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .cookeo_client import CookeoClient, decode_frame

_LOGGER = logging.getLogger(__name__)


class CookeoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Maintient l'état décodé du Cookeo (push via notify + poll ask_state)."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: CookeoClient,
        name: str,
        entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self.device_name = name
        self.available = False
        client.notify_cb = self._on_frame

    @callback
    def _on_frame(self, data: bytes) -> None:
        """Notification BLE -> mise à jour immédiate des entités."""
        decoded = decode_frame(data)
        if decoded.get("type") in ("ACK", "NAK"):
            return
        self.available = True
        self.async_set_updated_data(decoded)

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll périodique : demande l'état courant."""
        try:
            data = await self.client.ask_state()
        except Exception as err:  # noqa: BLE001
            self.available = False
            raise UpdateFailed(f"Cookeo injoignable : {err}") from err
        if data is None:
            # pas de réponse mais connexion vivante : on garde l'ancien état
            return self.data or {}
        self.available = True
        return decode_frame(data)
