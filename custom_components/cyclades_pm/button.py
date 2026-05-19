"""Button platform for Cyclades PM outlets cycling."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
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
    """Set up Cyclades PM buttons."""
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
        _LOGGER.warning("No outlets detected for button entities")
        return

    entities = []
    for outlet_num in range(1, outlets_detected + 1):
        entities.append(CycladesPMOutletCycleButton(coordinator, config_entry, outlet_num))

    async_add_entities(entities)


class CycladesPMOutletCycleButton(CoordinatorEntity[CycladesPMCoordinator], ButtonEntity):
    """Representation of a Cyclades PM outlet cycle button."""

    def __init__(
        self, coordinator: CycladesPMCoordinator, config_entry: ConfigEntry, outlet_number: int
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._outlet_number = outlet_number
        
        # Create device name slug for entity IDs
        device_name = config_entry.data.get("name", "Cyclades PM")
        device_slug = device_name.lower().replace(" ", "_").replace("-", "_")
        
        self._attr_unique_id = f"{coordinator.serial_port}_cycle_{outlet_number}"
        self._attr_name = f"{device_name} Cycle Outlet {outlet_number}"
        self._attr_icon = "mdi:restart"
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

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_cycle_outlet(self._outlet_number)
        await self.coordinator.async_request_refresh()
