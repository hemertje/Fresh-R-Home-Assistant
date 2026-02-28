"""Fresh-r sensor platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, SENSORS
from .coordinator import FreshRCoordinator

_LOGGER = logging.getLogger(__name__)

# Map string → HA constant
_DC = {
    "temperature":     SensorDeviceClass.TEMPERATURE,
    "carbon_dioxide":  SensorDeviceClass.CO2,
    "humidity":        SensorDeviceClass.HUMIDITY,
    "pm25":            SensorDeviceClass.PM25,
    "power":           SensorDeviceClass.POWER,
}
_SC = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total":       SensorStateClass.TOTAL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[FreshRCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities = [
        FreshRSensor(coord, key, defn)
        for coord in coordinators
        for key, defn in SENSORS.items()
    ]
    async_add_entities(entities)


class FreshRSensor(CoordinatorEntity, SensorEntity):
    """Represents a single Fresh-r sensor value."""

    def __init__(self, coordinator: FreshRCoordinator, key: str, defn: tuple) -> None:
        super().__init__(coordinator)
        api_field, friendly, unit, dc_str, sc_str, icon = defn
        self._key       = key
        self._api_field = api_field   # None for derived/calibrated sensors

        self._attr_name                       = f"Fresh-r {friendly}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class               = _DC.get(dc_str) if dc_str else None
        self._attr_state_class                = _SC.get(sc_str) if sc_str else None
        self._attr_icon                       = icon
        self._attr_unique_id                  = f"{DOMAIN}_{coordinator.serial}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        d = self.coordinator.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial)},
            name=f"Fresh-r {d.get('room') or d['id']}",
            manufacturer=MANUFACTURER,
            model=d.get("type", MODEL),
        )

    @property
    def native_value(self) -> float | None:
        data: dict[str, Any] = self.coordinator.data or {}
        # All keys (raw, calibrated, derived) live directly in the parsed data dict
        return data.get(self._key)
