# LEDapp/gui/gui_manager.py (Javított ComboBox stílussal)

import sys
import os
import threading
import asyncio
# import traceback # No longer needed for logging exceptions
import logging # Import the logging module
import time # Import time for sleep

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt, QMetaObject

# Core application imports
from .gui1_pyside import GUI1_Widget
from .gui2_schedule_pyside import GUI2_Widget
from core.reconnect_handler import start_ble_connection_loop
# (Old try-except ImportError for dummy fallbacks removed to ensure fail-fast on missing components)

class GuiManager:
    """Segédosztály a GUI megjelenítésének és váltásának kezelésére."""

    def __init__(self, app_instance: QMainWindow):
        self.app = app_instance
        self.reconnect_thread = None
        self.central_widget = self.app.centralWidget()
        self.main_layout = self.central_widget.layout()
        if not self.main_layout:
             self.main_layout = QVBoxLayout(self.central_widget)
             logging.warning("GuiManager init, layout létrehozva.")


    def _apply_stylesheet(self):
        """ Alkalmazza a központi stíluslapot a style.qss fájlból. """
        qss_file_path = os.path.join(os.path.dirname(__file__), "style.qss")
        try:
            with open(qss_file_path, "r", encoding="utf-8") as f:
                qss_content = f.read()
            self.app.setStyleSheet(qss_content)
            logging.info(f"Successfully loaded stylesheet from {qss_file_path}")
        except FileNotFoundError:
            logging.error(f"Stylesheet file not found at {qss_file_path}. No styles will be applied.")
            # Optionally, apply a minimal default style or leave as is
            # self.app.setStyleSheet("QMainWindow, QWidget { background-color: rgb(50, 51, 57); color: #E0E0E0; }") # Example minimal
        except Exception as e:
            logging.error(f"Error loading stylesheet from {qss_file_path}: {e}", exc_info=True)
            # Fallback or proceed without styles

    def center_window(self):
        """Ablakot képernyő közepére igazítja."""
        if QApplication.instance():
            try:
                screen = QApplication.primaryScreen()
                if screen:
                    screen_geometry = screen.availableGeometry()
                    window_geometry = self.app.frameGeometry()
                    x = (screen_geometry.width() - window_geometry.width()) // 2
                    y = (screen_geometry.height() - window_geometry.height()) // 2
                    x = max(0, x); y = max(0, y)
                    self.app.move(x, y)
                else: logging.error("Hiba: Nem található elsődleges képernyő.")
            except Exception as e: logging.error(f"Hiba az ablak középre igazítása közben: {e}")

    def _clear_layout(self, layout):
        """Rekurzív layout törlő (fallback)."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    if hasattr(widget, 'stop_timers') and callable(widget.stop_timers):
                        try: widget.stop_timers()
                        except Exception as e: logging.error(f"Hiba a widget stop_timers hívásakor (_clear_layout): {e}")
                    widget.deleteLater()
                else:
                    sub_layout = item.layout()
                    if sub_layout is not None:
                        self._clear_layout(sub_layout)

    def clear_window_content(self):
        """Törli az aktuálisan megjelenített GUI widgetet."""
        current_widget = self.app._current_gui_widget
        if isinstance(current_widget, GUI2_Widget):
             logging.info("clear_window_content: GUI2 volt aktív, reconnect loop stop jelzés...")
             if hasattr(self.app, '_stop_reconnect_event'):
                 self.app._stop_reconnect_event.set()
             self.reconnect_thread = None

        if current_widget:
            logging.info(f"clear_window_content: Aktuális widget törlése: {current_widget.objectName()}")
            if hasattr(current_widget, 'stop_timers') and callable(current_widget.stop_timers):
                try: current_widget.stop_timers()
                except Exception as e: logging.error(f"Hiba a {current_widget.objectName()} stop_timers hívásakor: {e}")

            current_widget.setParent(None)
            current_widget.deleteLater()
            self.app._current_gui_widget = None
        else:
            logging.warning("clear_window_content: Nem volt aktuális widget referencia, layout ürítése fallbackként.")
            self._clear_layout(self.main_layout) # Fallback

    def load_gui1(self):
        """Betölti az első képernyőt."""
        self.clear_window_content()
        self.app.setWindowTitle("LED-Irányító 2000 - Csatlakozás")
        self.app.resize(600, 450) # Eredeti méret visszaállítása

        widget = GUI1_Widget(self.app)
        self.main_layout.addWidget(widget)
        self.app._current_gui_widget = widget

        widget.update_button_states()
        widget.update_device_list()

        self.center_window()

    def load_gui2(self):
        """Betölti a második képernyőt és elindítja a reconnect loopot."""
        if not self.app.selected_device:
            logging.error("Hiba: Nincs kiválasztott eszköz a GUI2 betöltésekor.")
            # Előfordulhat auto-connect hiba után, ne jelenítsünk meg hibaüzenetet itt
            # QMessageBox.warning(self.app, "Hiba", "Nincs kiválasztott eszköz.")
            self.load_gui1() # Visszatérünk GUI1-re, ha nincs eszköz
            return False

        self.clear_window_content()
        self.app.setWindowTitle(f"LED-Irányító 2000 - {self.app.selected_device[0]}")
        # GUI2 méretének beállítása (ez felülírhatja a tartalom méretét)
        # Lehet, hogy jobb a tartalomra bízni vagy fix méretet használni
        self.app.resize(1080, 864) # Vagy egy kisebb/nagyobb fix méret

        widget = GUI2_Widget(self.app)
        self.main_layout.addWidget(widget)
        self.app._current_gui_widget = widget

        self.app.update_connection_status_gui(self.app.connection_status)
        self.center_window()

        # Reconnect thread indítása
        if self.reconnect_thread is None or not self.reconnect_thread.is_alive():
            logging.info("Reconnect thread indítása (GuiManager)...")
            if hasattr(self.app, '_stop_reconnect_event'):
                self.app._stop_reconnect_event.clear() # Stop jelzés törlése
            else:
                 logging.critical("HIBA: Nincs _stop_reconnect_event az app példányon GUI2 töltésekor!")
                 return False

            self.reconnect_thread = threading.Thread(
                target=self._run_reconnect_loop_target,
                args=(self.app, self.app._stop_reconnect_event),
                daemon=True
            )
            self.reconnect_thread.start()
        return True

    @staticmethod
    def _run_reconnect_loop_target(app_instance, stop_event):
         """Külön szálon futó asyncio hurok a kapcsolattartáshoz."""
         loop = asyncio.new_event_loop()
         asyncio.set_event_loop(loop)
         try:
              logging.info("Reconnect loop thread (új hurok) indítása...")
              # Biztosítjuk, hogy a core modul elérhető legyen
              from core.reconnect_handler import start_ble_connection_loop # Ensure this is the correct import path
              loop.run_until_complete(start_ble_connection_loop(app_instance, stop_event))
         except Exception as e:
              logging.exception(f"Hiba a reconnect loop futtatása közben: {e}") # Use logging.exception
         finally:
              logging.info("Reconnect loop thread befejeződött.")
              # Cleanup az asyncio hurokhoz
              if loop.is_running():
                    try:
                         if sys.version_info >= (3, 7):
                             loop.run_until_complete(loop.shutdown_asyncgens())
                         loop.call_soon_threadsafe(loop.stop)
                         # Adunk egy kis időt a leállásra, mielőtt bezárnánk
                         time.sleep(0.1)
                    except RuntimeError as e:
                         logging.error(f"RuntimeError during reconnect loop stop: {e}")
              if not loop.is_closed():
                  loop.close()
                  logging.info("Asyncio event loop closed in reconnect thread.")
