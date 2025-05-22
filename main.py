# LEDapp/main.py (Javítva a Future await hiba és opcionális késleltetés)

import sys
import os
import argparse
import asyncio # Importálva
import logging # Import the logging module

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, 
    format='[%(levelname)s - %(module)s @ %(asctime)s]: %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)

from PySide6.QtWidgets import QApplication
# from PySide6.QtGui import QIcon # QIcon will be imported via app_utils
from PySide6.QtCore import QTimer, QMetaObject, Qt, Q_ARG
from app_utils import load_app_icon # Import the new function

# Importáljuk a szükséges modulokat
from gui.main_window_pyside import LEDApp_PySide
from core import config_manager
# (Old try-except for log_event and critical error handling removed as logging is now standard)


async def attempt_auto_connect(app_instance):
    """ Megkísérli az automatikus csatlakozást a háttérben. """
    if not app_instance: return False
    # Unused variable 'connected_successfully' removed.

    try:
        # *** Opcionális extra késleltetés az újraindítás után ***
        logging.info("Rövid várakozás az auto-connect előtt (Bluetooth inicializálás)...")
        await asyncio.sleep(2.0) # Adjunk 2 másodpercet (ez állítható)
        # ****************************************************

        last_addr = config_manager.get_setting("last_device_address")
        last_name = config_manager.get_setting("last_device_name")

        if not last_addr or not last_name:
            logging.info("Automatikus csatlakozás kihagyva: Nincs mentett utolsó eszköz.")
            return False # Már itt visszatérünk

        logging.info(f"Automatikus csatlakozás megkísérlése: {last_name} ({last_addr})")
        app_instance.selected_device = (last_name, last_addr)
        QMetaObject.invokeMethod(app_instance, "update_connection_status_gui", Qt.ConnectionType.QueuedConnection, Q_ARG(str, "connecting"))

        # Csatlakozási kísérlet indítása az AsyncHelper segítségével
        # Az eredményt a done_callback fogja kezelni és a signalokat kibocsátani
        future = app_instance.async_helper.run_async_task(
            app_instance.ble.connect(last_addr),
            app_instance.connect_results_signal,
            app_instance.connect_error_signal
        )

        # !!! A HIBÁS RÉSZ ELTÁVOLÍTVA !!!
        # Nincs szükség az await asyncio.wait_for(future, ...)-ra itt,
        # mert az AsyncHelper done_callback-je kezeli az eredményt/hibát.
        # A future objektummal itt nem csinálunk semmit.

        if not future:
             logging.error("Hiba: Nem sikerült elindítani az automatikus csatlakozási taskot.")
             # Unused variable 'connected_successfully' removed.
        # A connected_successfully értékét a signal handler (_handle_connect_results) fogja beállítani.
        # Itt nem tudjuk megvárni szinkron módon. A függvény visszatérhet,
        # mielőtt a kapcsolat ténylegesen létrejönne vagy meghiúsulna.
        # A _initial_connection_attempted flag beállítása a finally blokkban történik.

    except Exception as e:
         # Ez a blokk valószínűleg nem fog lefutni a wait_for eltávolítása miatt,
         # de biztonság kedvéért itt hagyjuk.
         logging.error(f"Váratlan hiba az attempt_auto_connect indításakor: {e}", exc_info=True)
         # Unused variable 'connected_successfully' removed.
         # Hibajelzés küldése a fő szálra
         if hasattr(app_instance, '_handle_connect_error'):
             error_msg = f"Indítási hiba: {e}"
             QMetaObject.invokeMethod(app_instance, "_handle_connect_error", Qt.ConnectionType.QueuedConnection, Q_ARG(str, error_msg))

    finally:
         app_instance._initial_connection_attempted = True
         # Unused variable 'connected_successfully' removed.
         logging.info(f"_initial_connection_attempted flag beállítva: True (Csatlakozás a háttérben fut/futott).")
         # Az ablak betöltését a show_window_from_tray vagy a _handle_connect_results intézi.

    # A függvény visszatérési értéke itt már nem tükrözi a kapcsolat sikerességét,
    # mivel az aszinkron módon dől el.
    return None # Vagy True, ha a task indítása sikeres volt, de ez félrevezető lehet.


if __name__ == "__main__":
    # --- Parancssori argumentumok feldolgozása ---
    parser = argparse.ArgumentParser()
    parser.add_argument('--tray', action='store_true', help='Indítás rejtve a tálcára.')
    args = parser.parse_args()

    # --- Qt Alkalmazás Inicializálása ---
    qt_app = QApplication(sys.argv)

    # --- Ikon Beállítása ---
    app_icon = load_app_icon() # Use the utility function

    if not app_icon.isNull():
        qt_app.setWindowIcon(app_icon)
    else:
        logging.warning("main.py - Failed to load application icon using load_app_icon(), using default Qt icon.")


    # --- Ablak bezárásának kezelése ---
    qt_app.setQuitOnLastWindowClosed(False)

    # --- Főablak létrehozása ---
    start_hidden_arg = args.tray
    main_window = LEDApp_PySide(start_hidden=start_hidden_arg)
    main_window._is_auto_starting = start_hidden_arg

    if not app_icon.isNull(): # Ensure app_icon was successfully loaded
         main_window.setWindowIcon(app_icon)

    # --- Automatikus csatlakozás és indítási logika ---
    if start_hidden_arg:
        logging.info("Indítás --tray argumentummal.")

        if config_manager.get_setting("auto_connect_on_startup"):
            async def delayed_autoconnect():
                 await asyncio.sleep(0.5) # Rövid várakozás az eseményhurok stabilizálódására
                 await attempt_auto_connect(main_window) # Elindítja a csatlakozást

            # Az asyncio task futtatása az AsyncHelperen keresztül
            main_window.async_helper.run_async_task(delayed_autoconnect())
        else:
            logging.info("Automatikus csatlakozás kihagyva (beállítás szerint le van tiltva).")
            main_window._initial_connection_attempted = True # Jelöljük, hogy nem kell várni

    else:
        logging.info("Normál indítás.")
        main_window._initial_connection_attempted = True # Normál indításnál nincs auto-connect kísérlet
        main_window.show()


    # --- Qt Eseményhurok Indítása ---
    sys.exit(qt_app.exec())
