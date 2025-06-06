import asyncio
import logging
from bleak import BleakClient, BleakScanner, BleakError

from ..config import CHARACTERISTIC_UUID


class BLEService:
    """Bluetooth Low Energy communication service."""

    def __init__(self):
        self.client = None
        self._connection_lock = asyncio.Lock()

    async def scan(self):
        """Search for BLE devices."""
        logging.info("BLEService: Starting device scan...")
        devices_list = []
        try:
            discovered = await BleakScanner.discover(timeout=12.0)
            logging.info(
                "BLEService: Discover finished. Found %d raw devices.",
                len(discovered),
            )
            for d in discovered:
                if d.name:
                    devices_list.append((d.name, d.address))
                else:
                    logging.debug("BLEService: skipping unnamed device %s", d.address)
        except Exception:
            logging.exception("BLEService: error during scan")
            devices_list = []

        logging.info("BLEService: returning %d named devices", len(devices_list))
        return devices_list

    async def connect(self, address):
        """Connect to a BLE device by address."""
        async with self._connection_lock:
            if self.client and self.client.is_connected:
                if self.client.address.upper() == address.upper():
                    logging.info("BLEService: already connected to %s", address)
                    return True
                await self.disconnect()

            logging.info("BLEService: connecting to %s", address)
            self.client = BleakClient(address)
            try:
                await self.client.connect(timeout=15.0)
                logging.info("BLEService: connected to %s", address)
                return True
            except Exception as e:
                logging.error("BLEService: connection error: %s", e)
                self.client = None
                raise e

    async def disconnect(self):
        """Disconnect from the current device."""
        async with self._connection_lock:
            client_to_disconnect = self.client
            self.client = None
            if client_to_disconnect and client_to_disconnect.is_connected:
                logging.info(
                    "BLEService: disconnecting from %s", client_to_disconnect.address
                )
                try:
                    await client_to_disconnect.disconnect()
                    logging.info("BLEService: disconnect successful")
                except BleakError as e:
                    logging.error(
                        "BLEService: error while disconnecting: %s", e
                    )

    async def send_command(self, hex_command):
        """Send a command to the connected device."""
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(
                    CHARACTERISTIC_UUID,
                    bytes.fromhex(hex_command),
                    response=False,
                )
            except BleakError as e:
                logging.error(
                    "BLEService: error sending command %s: %s", hex_command, e
                )
                raise e
            except Exception:
                logging.exception(
                    "BLEService: unexpected error sending command %s", hex_command
                )
                raise
        else:
            raise BleakError("Cannot send command: Not connected to device.")

