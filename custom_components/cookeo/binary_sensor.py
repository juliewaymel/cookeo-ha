"""Capteurs binaires Cookeo — cuisson en cours, maintien au chaud, erreur."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import CookeoEntity


@dataclass(frozen=True, kw_only=True)
class CookeoBinaryDescription(BinarySensorEntityDescription):
    value: Callable[[dict[str, Any]], bool] = lambda d: False


BINARY_SENSORS: tuple[CookeoBinaryDescription, ...] = (
    CookeoBinaryDescription(
        key="cuisson",
        name="Cuisson",
        icon="mdi:pot-steam",
        device_class=BinarySensorDeviceClass.RUNNING,
        value=lambda d: bool(d.get("en_cuisson")),
    ),
    CookeoBinaryDescription(
        key="maintien_chaud",
        name="Maintien au chaud",
        icon="mdi:water-boiler",
        value=lambda d: bool(d.get("maintien_chaud")),
    ),
    CookeoBinaryDescription(
        key="recette_active",
        name="Recette en cours",
        icon="mdi:silverware-fork-knife",
        value=lambda d: bool(d.get("recette_active")),
    ),
    CookeoBinaryDescription(
        key="erreur",
        name="Erreur",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda d: "erreur_code" in d,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(CookeoBinarySensor(entry, coordinator, d) for d in BINARY_SENSORS)


class CookeoBinarySensor(CookeoEntity, BinarySensorEntity):
    entity_description: CookeoBinaryDescription

    def __init__(self, entry, coordinator, description: CookeoBinaryDescription) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        return self.entity_description.value(self.coordinator.data or {})
