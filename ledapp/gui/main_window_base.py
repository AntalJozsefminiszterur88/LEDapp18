# LEDapp/gui/main_window_base.py (Kiegészítve)

import sys
import os
import asyncio
import threading # Szükséges a threading.Event-hez
import time
from datetime import datetime, timedelta
import json
from concurrent.futures import Future
import traceback

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QListWidget, QProgressBar, QMessageBox, QFrame,
    QSpacerItem, QSizePolicy, QSystemTrayIcon # QSystemTrayIcon hozzáadva
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject, QThread, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QColor, QPalette, QFont

# Importáljuk a szükséges konfigurációs és backend elemeket
try:
    from ..config import COLORS, DAYS, CONFIG_FILE
    from ..services.ble_service import BLEService
    from ..core.reconnect_handler import log_event  # Logolás
    from ..util.async_helper import AsyncHelper
    from .gui_manager import GuiManager
    # GUI Widget importok itt is kellenek az isinstance miatt
    from .gui1_pyside import GUI1_Widget
    from .gui2_schedule_pyside import GUI2_Widget
    # Új import a config kezelőhöz
    from ..services import config_service
except ImportError as e:
    print(f"Hiba az importálás során main_window_base.py-ben: {e}")
    # Dummy log_event, ha a core import nem sikerül
    def log_event(msg): print(f"[LOG - Dummy BaseWindow]: {msg}")
    # Dummy config_service, ha a core import nem sikerül
    class DummyConfigService:
        @staticmethod
        def get_setting(key): return None
        @staticmethod
        def set_setting(key, value): pass
    config_service = DummyConfigService
    # Itt kiléphetnénk, vagy dummy osztályokat definiálhatnánk,
    # de a biztonság kedvéért most csak logolunk és megyünk tovább
    # sys.exit(1) # Kilépés hiba esetén

# Időzóna kezelés
import pytz
try:
    import tzlocal
    LOCAL_TZ = tzlocal.get_localzone()
    log_event(f"Helyi időzóna (tzlocal): {LOCAL_TZ.zone if LOCAL_TZ else 'Ismeretlen'}")
except Exception:
    log_event("tzlocal nem található vagy hiba történt, 'Europe/Budapest' használata.")
    try:
        LOCAL_TZ = pytz.timezone("Europe/Budapest")
        log_event(f"Helyi időzóna (fix): {LOCAL_TZ.zone}")
    except pytz.UnknownTimeZoneError:
        log_event("Figyelmeztetés: 'Europe/Budapest' időzóna sem található. UTC használata.")
        LOCAL_TZ = pytz.utc


class LEDApp_BaseWindow(QMainWindow):
    # --- Signals ---
    connection_status_signal = Signal(str)
    scan_results_signal = Signal(object)
    scan_error_signal = Signal(str)
    connect_results_signal = Signal(bool)
    connect_error_signal = Signal(str)
    command_error_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LED-Irányító 2000")

        # --- Központi Widget és Layout Létrehozása ---
        self.central_widget = QWidget()
        self.main_layout = QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        # *** ÚJ: Event a reconnect loop leállításához ***
        self._stop_reconnect_event = threading.Event()
        # ********************************************

        # --- Segédosztályok Inicializálása ---
        self.async_helper = AsyncHelper(self)
        # Fontos, hogy a GuiManager megkapja az app példányt, amiben az event van
        self.gui_manager = GuiManager(self)

        # --- Változók ---
        self.last_user_input = time.time()
        self.devices = [] # Kezdetben üres lista
        # Kezdeti érték betöltése a configból
        self.selected_device = (
            config_service.get_setting("last_device_name"),
            config_service.get_setting("last_device_address")
        ) if config_service.get_setting("last_device_address") else None
        self.connected = False # Induláskor sosem csatlakozunk még
        self.last_color_hex = COLORS[0][2] if COLORS else None
        self.is_led_on = True
        self.latitude = 47.4338
        self.longitude = 19.1931
        self.sunrise = None
        self.sunset = None
        self.connection_status = "disconnected"
        self._current_gui_widget = None # Ezt a GuiManager is látja/módosítja
        self.schedule = {
            day: {
                "color": "",
                "on_time": "",
                "off_time": "",
                "sunrise": False,
                "sunrise_offset": 0,
                "sunset": False,
                "sunset_offset": 0,
            }
            for day in DAYS
        }
        self.ble = BLEService()
        self._is_auto_starting = False # Új flag az automatikus indulás jelzésére
        self._initial_connection_attempted = False # Új flag

        # --- GUI Indítása ---
        self.gui_manager._apply_stylesheet()
        # A GUI betöltése most már a main.py-ben történik a logika alapján
        # self.gui_manager.load_gui1() # Ezt kikommenteljük innen
        # self.gui_manager.center_window() # Ezt is áthelyezzük

        # --- Signalok összekötése ---
        self.connection_status_signal.connect(self.update_connection_status_gui)
        self.scan_results_signal.connect(self._handle_scan_results)
        self.scan_error_signal.connect(self._handle_scan_error)
        self.connect_results_signal.connect(self._handle_connect_results)
        self.connect_error_signal.connect(self._handle_connect_error)
        self.command_error_signal.connect(self._handle_command_error)

    # *** ÚJ SLOT a disconnect utáni GUI1 töltéshez ***
    @Slot()
    def _load_gui1_slot(self):
        """Slot, amit a QMetaObject hívhat a GUI1 újratöltéséhez."""
        self.gui_manager.load_gui1()
    # ***********************************************

    @Slot()
    def disconnect_device(self):
        """Megszakítja a kapcsolatot, leállítja a reconnect loopot és visszatér a GUI1-re."""
        log_event("Kapcsolat bontása felhasználó által (disconnect_device)...")

        # 1. Állapotváltozók visszaállítása
        self.connected = False
        self.selected_device = None # Kiválasztott eszköz törlése
        self.devices = [] # Eszközlista törlése
        # Utolsó eszköz törlése a konfigurációból is
        config_service.set_setting("last_device_address", None)
        config_service.set_setting("last_device_name", None)

        self.update_connection_status_gui("disconnected") # GUI azonnali frissítése

        # 2. Reconnect Loop Leállítása (Signal az eventtel)
        log_event("Reconnect thread leállításának jelzése...")
        self._stop_reconnect_event.set() # Event beállítása

        async def do_disconnect():
            try:
                if self.ble and self.ble.client:
                    addr = self.ble.client.address # Mentsük el a címet logoláshoz
                    log_event(f"BLE disconnect kérése: {addr}")
                    await self.ble.disconnect() # Ez bontja a kapcsolatot
                    log_event("BLE disconnect kérés sikeresen elküldve/befejezve.")
                else:
                    log_event("BLE disconnect nem szükséges (nincs kliens vagy már bontva).")
            except Exception as e:
                log_event(f"Hiba a kapcsolat bontásakor (async): {e}")
                traceback.print_exc()
            finally:
                # 3. GUI1 újratöltése a FŐ SZÁLON, miután a disconnect lefutott
                log_event("GUI1 újratöltésének kérése a disconnect után...")
                # Most már a dedikált slotot hívjuk meg a főablakon (self)
                QMetaObject.invokeMethod(self, "_load_gui1_slot", Qt.ConnectionType.QueuedConnection)

        # Aszinkron disconnect indítása az AsyncHelperrel
        self.async_helper.run_async_task(do_disconnect(), None, self.command_error_signal)

        # Azonnal frissítjük a GUI1 gombjait és listáját (ha éppen az látható)
        self.update_button_states_if_gui1()


    def update_button_states_if_gui1(self):
        """Segédfüggvény, ami frissíti a GUI1 állapotát, ha az az aktív widget."""
        if isinstance(self._current_gui_widget, GUI1_Widget):
             self._current_gui_widget.update_button_states()
             self._current_gui_widget.update_device_list() # Az üres self.devices listát mutatja


    # --- Signal Handler Slotok ---
    @Slot(str)
    def update_connection_status_gui(self, status):
        self.connection_status = status
        current_widget = self._current_gui_widget

        # Ha a tálca ikon létezik, frissítsük a tooltipjét
        if hasattr(self, 'tray_icon') and self.tray_icon:
             device_name_str = f": {self.selected_device[0]}" if self.selected_device and self.selected_device[0] else ""
             if status == "connected": tooltip = f"LED-Irányító 2000 (Csatlakozva{device_name_str})"
             elif status == "connecting": tooltip = f"LED-Irányító 2000 (Csatlakozás...{device_name_str})"
             else: tooltip = "LED-Irányító 2000 (Nincs kapcsolat)"
             self.tray_icon.setToolTip(tooltip)

        if isinstance(current_widget, GUI2_Widget):
            label = getattr(current_widget, 'status_indicator_label', None)
            if label and label.isVisible():
                if status == "connected": text, color = "Állapot: Csatlakoztatva", "lime"
                elif status == "connecting": text, color = "Állapot: Csatlakozás...", "#FFA500"
                else: text, color = "Állapot: Nincs kapcsolat", "#FF6B6B"
                label.setText(text)
                label.setStyleSheet(f"QLabel {{ color: {color}; font-weight: bold; background-color: transparent; }}")
        elif isinstance(current_widget, GUI1_Widget):
            progress_label = getattr(current_widget, 'progress_label', None)
            if progress_label and progress_label.isVisible():
                 if status == "connecting": progress_label.setText("Csatlakozás...")
                 elif status == "disconnected": progress_label.setText("Kapcsolat bontva.")
                 elif status == "connected": progress_label.setText("Csatlakozva") # GUI1-en is jelezzük

    @Slot(object)
    def _handle_scan_results(self, devices):
        log_event(f"_handle_scan_results SLOT triggered in GUI thread. Received data type: {type(devices)}, Value: {devices}")
        current_widget = self._current_gui_widget
        if isinstance(current_widget, GUI1_Widget):
            if isinstance(devices, list):
                 current_widget.on_scan_finished(devices)
            else:
                 log_event(f"Hiba: Váratlan típus érkezett a scan eredményeként: {type(devices)}")
                 current_widget.on_scan_error("Belső hiba: érvénytelen keresési eredmény.")
            current_widget.on_scan_finally()
        else:
            log_event("Figyelmeztetés: Scan eredmény érkezett, de nem a GUI1 aktív.")

    @Slot(str)
    def _handle_scan_error(self, error_message):
        log_event(f"_handle_scan_error SLOT triggered in GUI thread. Error: {error_message}")
        current_widget = self._current_gui_widget
        if isinstance(current_widget, GUI1_Widget):
            current_widget.on_scan_error(error_message)
            current_widget.on_scan_finally()
        else:
            log_event(f"Figyelmeztetés: Scan hiba ({error_message}), de nem a GUI1 aktív.")


    @Slot(bool)
    def _handle_connect_results(self, success):
        log_event(f"_handle_connect_results SLOT triggered in GUI thread. Success: {success}")
        current_widget = self._current_gui_widget
        self._initial_connection_attempted = True # Jelöljük, hogy a kezdeti próbálkozás megtörtént

        if success:
            self.connected = True
            # *** Sikeres csatlakozáskor mentsük az eszközt ***
            if self.selected_device:
                config_service.set_setting("last_device_address", self.selected_device[1])
                config_service.set_setting("last_device_name", self.selected_device[0])
                log_event(f"Utolsó eszköz elmentve: {self.selected_device[0]} ({self.selected_device[1]})")
            else:
                 log_event("Figyelmeztetés: Sikeres csatlakozás, de self.selected_device üres.")

            # Ha a GUI1 aktív, akkor váltsunk GUI2-re
            if isinstance(current_widget, GUI1_Widget):
                if not self.gui_manager.load_gui2():
                    self.connected = False # Hiba esetén visszaállítjuk
                    current_widget.on_connect_finally()
            else:
                # Ha nem GUI1 volt aktív (pl. auto-connect), csak frissítsük az állapotot
                self.update_connection_status_gui("connected")
                # Itt lehetne jelezni a tálcán, ha auto-connect volt sikeres
                if self._is_auto_starting:
                    if hasattr(self, 'tray_icon') and self.tray_icon:
                         self.tray_icon.showMessage(
                            "LEDApp Csatlakozva",
                            f"Sikeresen csatlakozva: {self.selected_device[0] if self.selected_device else 'Ismeretlen eszköz'}",
                            QSystemTrayIcon.MessageIcon.Information,
                            3000
                         )
                    # Ha az automatikus indítás után sikeres a kapcsolat ÉS a GUI még nem töltődött be,
                    # akkor most kellene betölteni a GUI2-t (ha láthatóvá tesszük az ablakot)
                    # De ezt majd a show_window_from_tray kezeli.

        else: # Ha a csatlakozás sikertelen
            self.connected = False
            # Hiba esetén a _handle_connect_error fog lefutni
            if isinstance(current_widget, GUI1_Widget):
                 current_widget.on_connect_finally() # GUI1 gombjainak visszaállítása
            else:
                 # Ha nem GUI1 aktív (pl. auto-connect hiba), frissítsük az állapotot
                 self.update_connection_status_gui("disconnected")
                 # Itt is jelezhetünk a tálcán
                 if self._is_auto_starting:
                    if hasattr(self, 'tray_icon') and self.tray_icon:
                        self.tray_icon.showMessage(
                            "LEDApp Hiba",
                            "Automatikus csatlakozás sikertelen.",
                            QSystemTrayIcon.MessageIcon.Warning,
                            3000
                        )
                    # Ha az automatikus indítás után sikertelen a kapcsolat ÉS a GUI még nem töltődött be,
                    # akkor most kellene betölteni a GUI1-et (ha láthatóvá tesszük az ablakot)
                    # Ezt is a show_window_from_tray kezeli.


    @Slot(str)
    def _handle_connect_error(self, error_message):
        log_event(f"_handle_connect_error SLOT triggered in GUI thread. Error: {error_message}")
        current_widget = self._current_gui_widget
        self.connected = False # Biztosan nem vagyunk csatlakozva
        self._initial_connection_attempted = True # Jelöljük, hogy a kezdeti próbálkozás megtörtént (de sikertelen volt)

        if isinstance(current_widget, GUI1_Widget):
            current_widget.on_connect_error(error_message) # Hibaüzenet megjelenítése
            current_widget.on_connect_finally() # Gombok visszaállítása
        else:
            log_event(f"Figyelmeztetés: Connect hiba ({error_message}), de nem a GUI1 aktív.")
            self.update_connection_status_gui("disconnected")
            if hasattr(self, 'statusBar') and callable(self.statusBar):
                 self.statusBar().showMessage(f"Kapcsolódási hiba: {error_message}", 5000)
            # Tálca üzenet auto-start esetén
            if self._is_auto_starting:
                 if hasattr(self, 'tray_icon') and self.tray_icon:
                      self.tray_icon.showMessage(
                          "LEDApp Hiba",
                          f"Automatikus csatlakozás sikertelen: {error_message.split(':')[0]}", # Rövidebb üzenet
                          QSystemTrayIcon.MessageIcon.Warning,
                          5000
                      )

    @Slot(str)
    def _handle_command_error(self, error_message):
        log_event(f"_handle_command_error SLOT triggered in GUI thread. Error: {error_message}")
        if hasattr(self, 'statusBar') and callable(self.statusBar):
            self.statusBar().showMessage(f"Parancsküldési hiba: {error_message}", 5000)
        if "Not connected" in error_message or "disconnected" in error_message.lower():
             self.connected = False
             self.update_connection_status_gui("disconnected")
             # Ha parancsküldéskor derül ki, hogy nincs kapcsolat, és GUI2 van nyitva,
             # akkor visszadobhatnánk GUI1-re, de ezt a reconnect handlernek kellene kezelnie.
             # Lehet, hogy itt is jelezni kellene a felhasználónak egyértelműbben.
             if isinstance(self._current_gui_widget, GUI2_Widget):
                  # Opcionális: Hibaüzenet a GUI2-n
                  # QMessageBox.warning(self, "Kapcsolati Hiba", "Megszakadt a kapcsolat az eszközzel.")
                  # Vagy hagyatkozunk a státuszjelzőre és a reconnect loopra.
                  pass


    def base_cleanup(self):
         """ Alapvető cleanup műveletek kilépéskor. """
         log_event("Base cleanup műveletek indítása (kilépés)...")
         # Jelezzük a reconnect loopnak (ha még futna), hogy álljon le
         self._stop_reconnect_event.set()
         # Async hurok leállítását kérjük
         self.async_helper.stop_loop()
         log_event("Base cleanup (stop kérések) befejezve.")
         # A szálak leállása és a loop bezárása a háttérben történik meg (daemon=True, stop())
