"""Config flow for Cyclades PM integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    CONF_SERIAL_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from .coordinator import CycladesPMCoordinator

_LOGGER = logging.getLogger(__name__)


def get_serial_ports() -> list[str]:
    """Return a list of available serial ports."""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    coordinator = CycladesPMCoordinator(hass, data)
    
    try:
        # Test connection with a timeout
        await asyncio.wait_for(coordinator.test_connection(), timeout=45.0)
        
    except asyncio.TimeoutError:
        raise ConnectionError("Timeout connecting to device")
    except ConnectionError as err:
        # Re-raise connection errors (including auth failures) as-is
        raise err
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise ConnectionError(f"Cannot connect: {err}")
    finally:
        # CRITICAL: Always clean up the test connection
        await coordinator.async_shutdown()

    return {
        "title": data.get(CONF_NAME, DEFAULT_NAME),
        "outlets_detected": coordinator.outlets_detected,
        "firmware_version": coordinator.firmware_version,
        "has_temp_sensor": bool(coordinator.has_temp_sensor),
    }


class CycladesPMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cyclades PM."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}
        self._outlets_detected = 0
        self._firmware_version = ""
        self._has_temp_sensor = True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                self._data = user_input
                self._outlets_detected = info["outlets_detected"]
                self._firmware_version = info["firmware_version"]
                self._has_temp_sensor = info["has_temp_sensor"]
                
                # Show confirmation step with detected outlets
                return await self.async_step_confirm()
                
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Get available serial ports
        serial_ports = await self.hass.async_add_executor_job(get_serial_ports)
        
        if not serial_ports:
            return self.async_abort(reason="no_serial_ports")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_SERIAL_PORT): vol.In(serial_ports),
                vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show confirmation with detected outlets."""
        if user_input is not None:
            # Create unique ID based on serial port
            await self.async_set_unique_id(self._data[CONF_SERIAL_PORT])
            self._abort_if_unique_id_configured()
            
            # Store outlet count and firmware info in config data
            config_data = self._data.copy()
            config_data["outlets_detected"] = self._outlets_detected
            config_data["firmware_version"] = self._firmware_version
            config_data["has_temp_sensor"] = self._has_temp_sensor
            
            return self.async_create_entry(
                title=self._data.get(CONF_NAME, DEFAULT_NAME), 
                data=config_data
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._data.get(CONF_NAME, DEFAULT_NAME),
                "serial_port": self._data[CONF_SERIAL_PORT],
                "outlets_detected": str(self._outlets_detected),
                "firmware_version": self._firmware_version,
            },
        )