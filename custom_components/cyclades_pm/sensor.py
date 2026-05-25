"""Sensor platform for Cyclades PM."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CycladesPMCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cyclades PM sensors."""
    coordinator: CycladesPMCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = [
        CycladesPMCurrentSensor(coordinator, config_entry, "current"),
        CycladesPMCurrentSensor(coordinator, config_entry, "peak_current"),
    ]

    # Skip temperature entity creation when the config entry recorded that no
    # sensor is present. Legacy entries created before this flag existed default
    # to True so they keep their entity; the runtime `available` check below
    # marks it unavailable if the device reports no sensor.
    if config_entry.data.get("has_temp_sensor", True):
        entities.append(CycladesPMTemperatureSensor(coordinator, config_entry))

    async_add_entities(entities)


class CycladesPMSensorBase(CoordinatorEntity[CycladesPMCoordinator], SensorEntity):
    """Base class for Cyclades PM sensors."""

    def __init__(self, coordinator: CycladesPMCoordinator, config_entry: ConfigEntry, sensor_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        
        # Create device name slug for entity IDs
        device_name = config_entry.data.get("name", "Cyclades PM")
        device_slug = device_name.lower().replace(" ", "_").replace("-", "_")
        
        self._attr_unique_id = f"{coordinator.serial_port}_{sensor_type}"
        self._attr_name = f"{device_name} {sensor_type.replace('_', ' ').title()}"
        self._device_name = device_name
        self._device_slug = device_slug

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.serial_port)},
            "name": self._device_name,
            "manufacturer": "Cyclades",
            "model": "PM Series",
        }


class CycladesPMTemperatureSensor(CycladesPMSensorBase):
    """Temperature sensor for Cyclades PM."""

    def __init__(self, coordinator: CycladesPMCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, config_entry, "temperature")
        
        self._attr_name = f"{self._device_name} Temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        """Mark unavailable when the device reports no temperature sensor."""
        return super().available and self.coordinator.has_temp_sensor is not False

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.temp_celsius


class CycladesPMCurrentSensor(CycladesPMSensorBase):
    """Current sensor for Cyclades PM."""

    def __init__(self, coordinator: CycladesPMCoordinator, config_entry: ConfigEntry, current_type: str) -> None:
        """Initialize the current sensor."""
        super().__init__(coordinator, config_entry, current_type)
        self._current_type = current_type
        
        if current_type == "current":
            self._attr_name = f"{self._device_name} Current"
        else:
            self._attr_name = f"{self._device_name} Peak Current"
            
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self._current_type == "current":
            return self.coordinator.amps
        return self.coordinator.peak_amps