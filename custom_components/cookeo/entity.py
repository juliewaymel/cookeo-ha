"""Entité de base Cookeo (regroupement device + disponibilité)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CookeoCoordinator


class CookeoEntity(CoordinatorEntity[CookeoCoordinator]):
    """Base : rattache l'entité au device Cookeo."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator: CookeoCoordinator) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            connections={("bluetooth", entry.data["address"])} if entry.data.get("address") else set(),
            name=coordinator.device_name,
            manufacturer="Moulinex / Groupe SEB",
            model="Cookeo Connect",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available
