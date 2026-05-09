"""Switch platform for Cyclades PM outlets."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Cyclades PM switches."""
    coordinator: CycladesPMCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Get outlet count from config entry data (stored during setup)
    outlets_detected = config_entry.data.get("outlets_detected", 0)
    
    # If no outlets in config, wait for coordinator to detect them
    if outlets_detected == 0:
        await coordinator.async_request_refresh()
        # Give coordinator time to authenticate and get outlet count
        for _ in range(30):
            if coordinator.outlets_detected > 0:
                outlets_detected = coordinator.outlets_detected
                break
            await asyncio.sleep(1)

    if outlets_detected == 0:
        _LOGGER.warning("No outlets detected for switch entities")
        return

    entities = []
    for outlet_num in range(1, outlets_detected + 1):
        entities.append(CycladesPMOutletSwitch(coordinator, config_entry, outlet_num))

    async_add_entities(entities)


class CycladesPMOutletSwitch(CoordinatorEntity[CycladesPMCoordinator], SwitchEntity):
    """Representation of a Cyclades PM outlet switch."""

    def __init__(
        self, coordinator: CycladesPMCoordinator, config_entry: ConfigEntry, outlet_number: int
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._outlet_number = outlet_number
        
        # Create device name slug for entity IDs
        device_name = config_entry.data.get("name", "Cyclades PM")
        device_slug = device_name.lower().replace(" ", "_").replace("-", "_")
        
        self._attr_unique_id = f"{coordinator.serial_port}_outlet_{outlet_number}"
        self._attr_name = f"{device_name} Outlet {outlet_number}"
        self._device_name = device_name

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.serial_port)},
            "name": self._device_name,
            "manufacturer": "Cyclades",
            "model": "PM Series",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if outlet is on."""
        if self._outlet_number in self.coordinator.outlets:
            return self.coordinator.outlets[self._outlet_number]["state"] == "on"
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the outlet on."""
        await self.coordinator.async_set_outlet(self._outlet_number, "on")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the outlet off."""
        await self.coordinator.async_set_outlet(self._outlet_number, "off")
        await self.coordinator.async_request_refresh()