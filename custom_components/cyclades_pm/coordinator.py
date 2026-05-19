"""DataUpdateCoordinator for Cyclades PM."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from typing import Any

import aioserial
from asyncio import Queue

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)


class CycladesPMCoordinator(DataUpdateCoordinator):
    """Cyclades PM coordinator."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        
        self.config = config
        self.serial_port = config[CONF_SERIAL_PORT]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        
        self.serial: aioserial.AioSerial | None = None
        self.authenticated = False
        self.outlets_detected = 0
        self.outlets: dict[int, dict[str, Any]] = {}
        
        # Device data
        self.amps = 0.0
        self.peak_amps = 0.0
        self.temp_celsius = 0.0
        self.temp_fahrenheit = 0.0
        self.peak_temp_celsius = 0.0
        self.peak_temp_fahrenheit = 0.0
        self.max_amps = 0
        self.firmware_version = ""
        self.firmware_date = ""
        
        # Authentication state
        self.auth_failed = False
        
        # Async queues
        self.rxQueue: Queue | None = None
        self.txQueue: Queue | None = None
        
        # Tasks
        self._tasks: list[asyncio.Task] = []
        
        # Regex patterns
        self.regex_functions = {
            re.compile(r'Username:'): self._send_username,
            re.compile(r'Password:'): self._send_password,
            re.compile(r'IPDU #(\d+): Temperature: (\d+\.\d+)C \((\d+\.\d+)F\). Maximum: (\d+\.\d+)C \((\d+\.\d+)F\)'): self._handle_temperature,
            re.compile(r'IPDU #(\d+): True RMS current: (\d+\.\d+)A. Maximum current: (\d+\.\d+)A'): self._handle_current,
            re.compile(r'IPDU #(\d+): Hw with (\d+) outlets (\d+) AMPs max Sw V (\d+\.\d+\.\d+) (.*)$'): self._handle_ver,
            re.compile(r'(\d+): Outlet turned (on|off).'): self._handle_port_state,
            re.compile(r'OUT: (\d+)'): self._init_outlets,
            re.compile(r'pm>'): self._handle_authenticated,
            re.compile(r'Authentication failed.'): self._handle_auth_failure,
            re.compile(r'(\d+).*locked (ON|OFF)'): self._handle_port_state_locked,
            re.compile(r'No temperature sensor detected.'): self._handle_no_temperature,
        }
    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        if not self.authenticated:
            return self._get_current_data()
            
        # Request current status
        if self.txQueue:
            await self.txQueue.put("current\r")
            await asyncio.sleep(1)
            await self.txQueue.put("temperature\r")
            await asyncio.sleep(1)
            await self.txQueue.put("status all\r")
            
        return self._get_current_data()

    def _get_current_data(self) -> dict[str, Any]:
        """Get current device data."""
        return {
            "outlets": self.outlets,
            "amps": self.amps,
            "peak_amps": self.peak_amps,
            "temp_celsius": self.temp_celsius,
            "temp_fahrenheit": self.temp_fahrenheit,
            "peak_temp_celsius": self.peak_temp_celsius,
            "peak_temp_fahrenheit": self.peak_temp_fahrenheit,
            "max_amps": self.max_amps,
            "firmware_version": self.firmware_version,
            "firmware_date": self.firmware_date,
            "authenticated": self.authenticated,
            "outlets_detected": self.outlets_detected,
        }

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            # Small delay to ensure port is fully released from config flow
            await asyncio.sleep(0.5)
            
            self.serial = aioserial.AioSerial(
                port=self.serial_port, 
                baudrate=9600, 
                timeout=1
            )
            
            self.rxQueue = Queue()
            self.txQueue = Queue()
            
            # Start background tasks
            self._tasks = [
                asyncio.create_task(self._read_serial()),
                asyncio.create_task(self._process_lines()),
                asyncio.create_task(self._write_serial()),
            ]
            
            _LOGGER.info("Cyclades PM coordinator setup complete")
            
        except Exception as err:
            _LOGGER.error("Failed to setup coordinator: %s", err)
            raise

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        # Close serial connection
        if self.serial:
            self.serial.close()
            
        _LOGGER.info("Cyclades PM coordinator shutdown complete")

    async def test_connection(self) -> bool:
        """Test connection to device."""
        await self.async_setup()
        
        # Wait for authentication or failure
        for _ in range(30):  # 30 second timeout
            if self.auth_failed:
                raise ConnectionError("Authentication failed - check username and password")
            if self.authenticated:
                break
            await asyncio.sleep(1)
        else:
            raise ConnectionError("Timeout during authentication")
            
        # Send ver command to get outlet count
        if self.txQueue:
            await self.txQueue.put("ver\r")
            
        # Wait for outlet detection via ver command
        for _ in range(15):  # 15 second timeout for ver response
            if self.outlets_detected > 0:
                return True
            await asyncio.sleep(1)
            
        raise ConnectionError("Failed to detect outlets from device")

    async def _read_serial(self) -> None:
        """Read from serial port."""
        try:
            while True:
                if not self.serial:
                    break
                    
                line = await self.serial.readline_async()
                if line and self.rxQueue:
                    decoded_line = line.decode(errors="ignore").strip()
                    _LOGGER.debug("Received: %s", decoded_line)
                    await self.rxQueue.put(decoded_line)
                    
        except asyncio.CancelledError:
            _LOGGER.debug("Serial reading cancelled")
        except Exception as err:
            _LOGGER.error("Error reading serial: %s", err)

    async def _process_lines(self) -> None:
        """Process received lines."""
        try:
            while True:
                if not self.rxQueue:
                    break
                    
                line = await self.rxQueue.get()
                await self._process_line(line)
                self.rxQueue.task_done()
                
        except asyncio.CancelledError:
            _LOGGER.debug("Line processing cancelled")

    async def _process_line(self, line: str) -> None:
        """Process a single line."""
        for regex, func in self.regex_functions.items():
            match = regex.search(line)
            if match:
                _LOGGER.debug("Match found: %s", match.group(0))
                await func(*match.groups())
                break
        else:
            _LOGGER.debug("No match: %s", line)

    async def _write_serial(self) -> None:
        """Write to serial port."""
        try:
            while True:
                if not self.txQueue or not self.serial:
                    break
                    
                message = await self.txQueue.get()
                await self.serial.write_async(message.encode())
                _LOGGER.debug("Sent: %s", message.strip())
                self.txQueue.task_done()
                
        except asyncio.CancelledError:
            _LOGGER.debug("Serial writing cancelled")
        except Exception as err:
            _LOGGER.error("Error writing serial: %s", err)

    # Handler methods
    async def _send_username(self) -> None:
        """Send username."""
        if self.txQueue:
            await self.txQueue.put(f"{self.username}\r")

    async def _send_password(self) -> None:
        """Send password."""
        if self.txQueue:
            await self.txQueue.put(f"{self.password}\r")

    async def _handle_temperature(self, ipdu: str, current_c: str, current_f: str, 
                                 peak_c: str, peak_f: str) -> None:
        """Handle temperature data."""
        self.temp_celsius = float(current_c)
        self.temp_fahrenheit = float(current_f)
        self.peak_temp_celsius = float(peak_c)
        self.peak_temp_fahrenheit = float(peak_f)
        self.async_set_updated_data(self._get_current_data())
                                     
    async def _handle_no_temperature(self) -> None:
        """Handle unit without temperature sensor."""
        # FIXME - Need to disable the temperature sensor, probably in the config flow process.
        #self.temp_celsius = float(current_c)
        #self.temp_fahrenheit = float(current_f)
        #self.peak_temp_celsius = float(peak_c)
        #self.peak_temp_fahrenheit = float(peak_f)
        #self.async_set_updated_data(self._get_current_data())

    async def _handle_current(self, ipdu: str, amps: str, peak_amps: str) -> None:
        """Handle current data."""
        self.amps = float(amps)
        self.peak_amps = float(peak_amps)
        self.async_set_updated_data(self._get_current_data())

    async def _handle_port_state(self, outlet_number: str, state: str) -> None:
        """Handle outlet state change."""
        outlet_num = int(outlet_number)
        if outlet_num in self.outlets:
            self.outlets[outlet_num]['state'] = state.lower()
            self.async_set_updated_data(self._get_current_data())

    async def _handle_port_state_locked(self, outlet_number: str, state: str) -> None:
        """Handle locked outlet state."""
        outlet_num = int(outlet_number)
        if outlet_num in self.outlets:
            self.outlets[outlet_num]['state'] = state.lower()
            self.async_set_updated_data(self._get_current_data())

    async def _init_outlets(self, total_outlets: str) -> None:
        """Initialize outlets."""
        total = int(total_outlets)
        if not self.outlets or self.outlets_detected != total:
            self.outlets = {
                i: {'name': f'Outlet {i}', 'state': 'off'} 
                for i in range(1, total + 1)
            }
            self.outlets_detected = total
            self.async_set_updated_data(self._get_current_data())

    async def _handle_authenticated(self) -> None:
        """Handle successful authentication."""
        if not self.authenticated:
            self.authenticated = True
            if self.txQueue:
                await self.txQueue.put("ver\r")  # Use ver command instead of status all
            _LOGGER.info("Authenticated successfully")

    async def _handle_ver(self, ipdu: str, outlets: str, max_amps: str, 
                         firmware_version: str, firmware_date: str) -> None:
        """Handle version command response with outlet count."""
        outlet_count = int(outlets)
        self.max_amps = int(max_amps)
        self.firmware_version = firmware_version
        self.firmware_date = firmware_date.strip()
        
        # Initialize outlets based on ver command response
        if not self.outlets or self.outlets_detected != outlet_count:
            self.outlets = {
                i: {'name': f'Outlet {i}', 'state': 'off'} 
                for i in range(1, outlet_count + 1)
            }
            self.outlets_detected = outlet_count
            _LOGGER.info("Detected %d outlets from ver command", outlet_count)
            self.async_set_updated_data(self._get_current_data())

    async def _handle_auth_failure(self) -> None:
        """Handle authentication failure."""
        self.auth_failed = True
        _LOGGER.error("Authentication failed")

    # Control methods
    async def async_set_outlet(self, outlet_number: int, state: str) -> None:
        """Set outlet state."""
        if self.txQueue:
            await self.txQueue.put(f"{state} {outlet_number}\r")

    async def async_cycle_outlet(self, outlet_number: int) -> None:
        """Cycle outlet."""
        if self.txQueue:
            await self.txQueue.put(f"cycle {outlet_number}\r")
