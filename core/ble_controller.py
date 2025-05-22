# core/ble_controller.py (Logolással + eredeti szűréssel)

import asyncio
import logging # Import the logging module
from bleak import BleakClient, BleakScanner, BleakError
from config import CHARACTERISTIC_UUID
# import traceback # No longer needed for logging exceptions

# Logolás importálása - Removed, using standard logging

class BLEController:
    def __init__(self):
        self.client = None
        self._connection_lock = asyncio.Lock()

    async def scan(self):
        """Eszközök keresése (bővített logolással)."""
        logging.info("BLEController: Starting BleakScanner.discover...")
        devices_list = []
        try:
            # Növelt timeout
            discovered = await BleakScanner.discover(timeout=12.0)
            logging.info(f"BLEController: Discover finished. Found {len(discovered)} raw devices.")
            if discovered:
                logging.info("BLEController: Processing discovered devices...")
                for d in discovered:
                    name = d.name if d.name else "Unnamed Device"
                    address = d.address
                    logging.debug(f"  - Processing: {name} ({address})") # Changed to debug
                    # Eredeti szűrés visszaállítása: Csak névvel rendelkező eszközök
                    if d.name:
                        devices_list.append((name, address))
                    else:
                        logging.debug(f"  - Skipping unnamed device: {address}") # Changed to debug
            else:
                 logging.info("BLEController: No devices discovered by BleakScanner.")

        except Exception as e:
             logging.exception("BLEController: Error during scan execution") # Automatically includes traceback
             devices_list = [] # Hiba esetén üres lista

        logging.info(f"BLEController: Returning {len(devices_list)} named devices to AsyncHelper.")
        return devices_list # Csak a névvel rendelkezőket adjuk vissza

    async def connect(self, address):
        """Csatlakozás az eszközhöz címmel (egyszeri próbálkozás)."""
        async with self._connection_lock:
            if self.client and self.client.is_connected:
                if self.client.address.upper() == address.upper():
                    logging.info(f"BLEController: Már csatlakozva: {address}")
                    return True
                else:
                    await self.disconnect()

            logging.info(f"BLEController: Csatlakozás kísérlet: {address}")
            # The 'if self.client: pass' block was here and has been removed as redundant.
            # The self.client is either None or a disconnected client due to the logic above.

            self.client = BleakClient(address)
            try:
                await self.client.connect(timeout=15.0)
                logging.info(f"BLEController: Sikeres csatlakozás: {address}")
                return True
            except Exception as e:
                logging.error(f"BLEController: Csatlakozási hiba a connect() során ({type(e).__name__}): {e}")
                self.client = None
                raise e

    async def disconnect(self):
        """Kapcsolat bontása."""
        async with self._connection_lock:
            client_to_disconnect = self.client
            self.client = None
            if client_to_disconnect and client_to_disconnect.is_connected:
                logging.info(f"BLEController: disconnect() hívása: {client_to_disconnect.address}")
                try:
                    await client_to_disconnect.disconnect()
                    logging.info(f"BLEController: disconnect() sikeres.")
                except BleakError as e:
                     logging.error(f"BLEController: Hiba a kapcsolat bontása közben: {e}")

    async def send_command(self, hex_command):
        """Parancs küldése a csatlakoztatott eszköznek."""
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(CHARACTERISTIC_UUID, bytes.fromhex(hex_command), response=False)
            except BleakError as e:
                 logging.error(f"BLEController: Hiba parancs küldésekor ({hex_command}): {e}")
                 raise e
            except Exception as e:
                 logging.exception(f"BLEController: Váratlan hiba parancs küldésekor ({hex_command})") # Use logging.exception
                 raise e
        else:
             # Ezt a hibát a hívónak (async_helper) kell elkapnia és a command_error_signal-ra küldenie
             raise BleakError("Cannot send command: Not connected to device.")
