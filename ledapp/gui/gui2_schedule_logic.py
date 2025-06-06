# LEDapp/gui/gui2_schedule_logic.py

import json
import os
from datetime import datetime, timedelta, time as dt_time
import traceback
import pytz

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

# Importáljuk a szükséges konfigurációs és backend/core elemeket
from ..config import COLORS, DAYS, CONFIG_FILE
from ..core.sun_logic import get_local_sun_info, get_hungarian_day_name, DAYS_HU
from ..core.location_utils import get_sun_times  # Bár itt nincs közvetlen hívás, a main_app tartalmazza
from ..services import schedule_service

# --- Időzóna Definíció ---
# Biztosítjuk, hogy a LOCAL_TZ létezzen
try:
    # Próbáljuk meg a rendszer alapértelmezett időzónáját használni, ha lehetséges
    try:
        import tzlocal
        LOCAL_TZ = tzlocal.get_localzone()
        print(f"Helyi időzóna (tzlocal - logic): {LOCAL_TZ.zone}")
    except ImportError:
        # Ha a tzlocal nincs telepítve, maradunk a fixnél
        LOCAL_TZ = pytz.timezone("Europe/Budapest")
        print(f"Helyi időzóna (fix - logic): {LOCAL_TZ.zone}")
except pytz.UnknownTimeZoneError:
    print("Figyelmeztetés: Helyi időzóna nem található. UTC használata (logic).")
    LOCAL_TZ = pytz.utc
except Exception as e:
    print(f"Váratlan hiba az időzóna beolvasásakor (logic): {e}. UTC használata.")
    LOCAL_TZ = pytz.utc

# --- Logika Függvények ---

def load_schedule_from_file(main_app):
    """
    Betölti az ütemezést a JSON fájlból a main_app.schedule-be.
    Args:
        main_app: A fő alkalmazás példánya (LEDApp_PySide).
    """
    main_app.schedule = schedule_service.load_schedule(CONFIG_FILE)


def save_schedule(gui_widget):
    """
    Elmenti az aktuális ütemezési beállításokat JSON fájlba a GUI widgetek alapján.
    Args:
        gui_widget: A GUI2_Widget példánya.
    """
    schedule_to_save = {}
    valid = True
    for day, widgets in gui_widget.schedule_widgets.items():
        temp_data = {}
        try:
            temp_data["color"] = widgets["color"].currentText()
            if not temp_data["color"] and COLORS:
                temp_data["color"] = COLORS[0][0]

            temp_data["sunrise"] = widgets["sunrise"].isChecked()
            temp_data["sunset"] = widgets["sunset"].isChecked()

            offset_sr_str = widgets["sunrise_offset"].text()
            offset_ss_str = widgets["sunset_offset"].text()
            # Ellenőrizzük, hogy az offset szám-e
            temp_data["sunrise_offset"] = int(offset_sr_str) if offset_sr_str else 0
            temp_data["sunset_offset"] = int(offset_ss_str) if offset_ss_str else 0

            on_time_val = widgets["on_time"].currentText()
            off_time_val = widgets["off_time"].currentText()
            temp_data["on_time"] = ""
            temp_data["off_time"] = ""

            # Validáljuk a HH:MM formátumot, ha nincs napkelte/napnyugta bejelölve
            if not temp_data["sunrise"] and on_time_val:
                try:
                    dt_time.fromisoformat(on_time_val)
                    temp_data["on_time"] = on_time_val
                except ValueError:
                     raise ValueError(f"Érvénytelen bekapcsolási idő formátum: '{on_time_val}'. HH:MM formátum szükséges.")

            if not temp_data["sunset"] and off_time_val:
                 try:
                     dt_time.fromisoformat(off_time_val)
                     temp_data["off_time"] = off_time_val
                 except ValueError:
                     raise ValueError(f"Érvénytelen kikapcsolási idő formátum: '{off_time_val}'. HH:MM formátum szükséges.")

            schedule_to_save[day] = temp_data

        except ValueError as ve:
            QMessageBox.critical(gui_widget, "Hiba", f"Érvénytelen érték a '{day}' napnál: {ve}. Kérlek javítsd (idő HH:MM, offset egész szám).")
            valid = False
            break
        except Exception as e:
            QMessageBox.critical(gui_widget, "Hiba", f"Váratlan hiba a '{day}' nap feldolgozásakor: {e}")
            valid = False
            break

    if not valid:
        return

    try:
        schedule_service.save_schedule(schedule_to_save, CONFIG_FILE)
        QMessageBox.information(gui_widget, "Mentés sikeres", "Az ütemezés sikeresen elmentve.")
        gui_widget.main_app.schedule = schedule_to_save
        check_schedule(gui_widget)
    except Exception as e:
        QMessageBox.critical(gui_widget, "Mentési hiba", f"Hiba történt a fájl írása során: {e}")



def check_schedule(gui_widget):
    """Ellenőrzi az ütemezést és ha szükséges, parancsot küld a LED-nek."""
    now_local = datetime.now(schedule_service.LOCAL_TZ)
    app = gui_widget.main_app
    try:
        target_hex = schedule_service.get_active_color(
            app.schedule,
            now_local,
            sunrise=app.sunrise,
            sunset=app.sunset,
        )
        if target_hex:
            if not app.is_led_on or app.last_color_hex != target_hex:
                if gui_widget.controls_widget:
                    gui_widget.controls_widget.send_color_command(target_hex)
        elif app.is_led_on:
            if gui_widget.controls_widget:
                gui_widget.controls_widget.turn_off_led()
    except Exception as e:
        print(f"V\u00e1ratlan hiba a schedule ellen\u0151rz\u00e9sekor: {e}")
        traceback.print_exc()
