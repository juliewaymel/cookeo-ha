"""Capteurs Cookeo — suivi de cuisson décodé."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import CookeoEntity


@dataclass(frozen=True, kw_only=True)
class CookeoSensorDescription(SensorEntityDescription):
    """Décrit un capteur dérivé de l'état décodé."""

    value: Callable[[dict[str, Any]], Any] = lambda d: None


def _minutes(seconds: Any) -> Any:
    return round(seconds / 60) if isinstance(seconds, (int, float)) else None


SENSORS: tuple[CookeoSensorDescription, ...] = (
    CookeoSensorDescription(
        key="etat",
        name="État",
        icon="mdi:pot-steam",
        value=lambda d: d.get("etat"),
    ),
    CookeoSensorDescription(
        key="mode",
        name="Mode",
        icon="mdi:chef-hat",
        value=lambda d: d.get("mode"),
    ),
    CookeoSensorDescription(
        key="progression",
        name="Progression",
        icon="mdi:progress-clock",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("progression"),
    ),
    CookeoSensorDescription(
        key="temps_restant",
        name="Temps restant",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        value=lambda d: _minutes(d.get("temps_restant_s")),
    ),
    CookeoSensorDescription(
        key="temps_ecoule",
        name="Temps écoulé",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        value=lambda d: _minutes(d.get("temps_ecoule_s")),
    ),
    CookeoSensorDescription(
        key="temps_total",
        name="Temps total",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        value=lambda d: _minutes(d.get("temps_total_s")),
    ),
    CookeoSensorDescription(
        key="convives",
        name="Convives",
        icon="mdi:account-group",
        value=lambda d: d.get("convives"),
    ),
    CookeoSensorDescription(
        key="etape",
        name="Étape",
        icon="mdi:format-list-numbered",
        entity_registry_enabled_default=False,
        value=lambda d: d.get("etape"),
    ),
    CookeoSensorDescription(
        key="recette_id",
        name="Recette (id)",
        icon="mdi:identifier",
        entity_registry_enabled_default=False,
        value=lambda d: d.get("recette_id"),
    ),
    CookeoSensorDescription(
        key="trame",
        name="Dernière trame",
        icon="mdi:code-braces",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: d.get("raw"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(CookeoSensor(entry, coordinator, d) for d in SENSORS)


class CookeoSensor(CookeoEntity, SensorEntity):
    entity_description: CookeoSensorDescription

    def __init__(self, entry, coordinator, description: CookeoSensorDescription) -> None:
        super().__init__(entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "etat":
            data = self.coordinator.data or {}
            return {
                k: data[k]
                for k in ("categorie", "menu", "etat_code", "erreur_code")
                if k in data
            }
        return None
