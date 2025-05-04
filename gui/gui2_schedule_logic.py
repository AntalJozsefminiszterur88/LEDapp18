# LEDapp/gui/gui2_schedule_logic.py

import json
import os
from datetime import datetime, timedelta, time as dt_time
import traceback
import pytz

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

# Importáljuk a szükséges konfigurációs és backend/core elemeket
from config import COLORS, DAYS, CONFIG_FILE
from core.sun_logic import get_local_sun_info, get_hungarian_day_name, DAYS_HU
from core.location_utils import get_sun_times # Bár itt nincs közvetlen hívás, a main_app tartalmazza

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
    default_schedule = {day: {"color": COLORS[0][0] if COLORS else "", "on_time": "", "off_time": "", "sunrise": False, "sunrise_offset": 0, "sunset": False, "sunset_offset": 0} for day in DAYS}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            merged_schedule = {}
            for day in DAYS:
                 day_data = default_schedule[day].copy()
                 if day in loaded_data and isinstance(loaded_data[day], dict):
                      for key in day_data:
                           if key in loaded_data[day]:
                                expected_type = type(day_data[key])
                                loaded_val = loaded_data[day][key]
                                # Speciális kezelés offset-re (mindig int legyen)
                                if key.endswith("_offset"):
                                     try:
                                         day_data[key] = int(loaded_val)
                                     except (ValueError, TypeError):
                                         print(f"Figyelmeztetés: Érvénytelen offset érték ('{loaded_val}') a '{day}' nap '{key}' kulcsánál. 0 lesz használva.")
                                         day_data[key] = 0 # Alapértelmezett offset hiba esetén
                                elif isinstance(loaded_val, expected_type):
                                     day_data[key] = loaded_val
                                else:
                                    print(f"Figyelmeztetés: Típuseltérés a '{day}' nap '{key}' kulcsánál. Mentett: {type(loaded_val)}, Várt: {expected_type}. Alapértelmezett használata.")
                 merged_schedule[day] = day_data
            main_app.schedule = merged_schedule

        except json.JSONDecodeError:
            print(f"Hiba: A {CONFIG_FILE} fájl hibás JSON formátumú. Alapértelmezett ütemezés használata.")
            main_app.schedule = default_schedule.copy()
        except Exception as e:
            print(f"Hiba a schedule betöltésekor: {e}. Alapértelmezett ütemezés használata.")
            main_app.schedule = default_schedule.copy()
    else:
         print(f"Nincs mentett schedule ({CONFIG_FILE}), alapértelmezett ütemezés használata.")
         main_app.schedule = default_schedule.copy()


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
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(schedule_to_save, f, ensure_ascii=False, indent=4)
        QMessageBox.information(gui_widget, "Mentés sikeres", "Az ütemezés sikeresen elmentve.")
        # Frissítjük az app belső állapotát is a mentett adatokkal
        gui_widget.main_app.schedule = schedule_to_save
        # Újra ellenőrizzük az ütemezést a friss adatokkal
        check_schedule(gui_widget)
    except Exception as e:
        QMessageBox.critical(gui_widget, "Mentési hiba", f"Hiba történt a fájl írása során: {e}")


def check_schedule(gui_widget):
    """
    Ellenőrzi az ütemezést és szükség esetén parancsot küld a LED-nek.
    Args:
        gui_widget: A GUI2_Widget példánya.
    """
    now_local = datetime.now(LOCAL_TZ)
    today_name_hu = DAYS_HU.get(now_local.strftime('%A'), now_local.strftime('%A'))

    if today_name_hu not in gui_widget.schedule_widgets:
        return

    day_data_widgets = gui_widget.schedule_widgets[today_name_hu]
    main_app = gui_widget.main_app # Rövidítés

    try:
        on_time_dt = None
        off_time_dt = None

        # --- Bekapcsolási idő meghatározása ---
        if day_data_widgets["sunrise"].isChecked():
            offset_str = day_data_widgets["sunrise_offset"].text()
            try:
                offset = int(offset_str if offset_str else 0)
                if main_app.sunrise: # Ellenőrizzük, hogy van-e érvényes napkelte adat
                    # Fontos: A main_app.sunrise már a helyi időzónában van
                    on_time_dt = main_app.sunrise + timedelta(minutes=offset)
            except (ValueError, TypeError) as e:
                print(f"Hiba a napkelte offset feldolgozásakor ({today_name_hu}): {e}")
                pass # Hiba esetén None marad

        else: # Fix időpont használata
            on_time_str = day_data_widgets["on_time"].currentText()
            if on_time_str:
                try:
                    time_obj = dt_time.fromisoformat(on_time_str)
                    naive_dt = datetime.combine(now_local.date(), time_obj)
                    on_time_dt = LOCAL_TZ.localize(naive_dt)
                except ValueError as e:
                    print(f"Hiba a bekapcsolási idő ('{on_time_str}') feldolgozásakor ({today_name_hu}): {e}")
                    pass # Hiba esetén None marad

        # --- Kikapcsolási idő meghatározása ---
        if day_data_widgets["sunset"].isChecked():
             offset_str = day_data_widgets["sunset_offset"].text()
             try:
                 offset = int(offset_str if offset_str else 0)
                 if main_app.sunset: # Ellenőrizzük, hogy van-e érvényes napnyugta adat
                     # Fontos: A main_app.sunset már a helyi időzónában van
                     off_time_dt = main_app.sunset + timedelta(minutes=offset)
             except (ValueError, TypeError) as e:
                 print(f"Hiba a napnyugta offset feldolgozásakor ({today_name_hu}): {e}")
                 pass
        else: # Fix időpont használata
             off_time_str = day_data_widgets["off_time"].currentText()
             if off_time_str:
                 try:
                     time_obj = dt_time.fromisoformat(off_time_str)
                     naive_dt = datetime.combine(now_local.date(), time_obj)
                     off_time_dt = LOCAL_TZ.localize(naive_dt)
                     # Éjfél átnyúlás kezelése: ha a kikapcsolás korábbi, mint a bekapcsolás,
                     # akkor a kikapcsolás másnapra vonatkozik
                     if on_time_dt and off_time_dt <= on_time_dt:
                         print(f"SCHEDULE: Éjfél átnyúlás észlelve ({today_name_hu}), kikapcsolás másnapra tolva.")
                         off_time_dt += timedelta(days=1)
                 except ValueError as e:
                     print(f"Hiba a kikapcsolási idő ('{off_time_str}') feldolgozásakor ({today_name_hu}): {e}")
                     pass

        # --- Művelet végrehajtása ---
        if on_time_dt and off_time_dt:
            target_color_name = day_data_widgets["color"].currentText()
            target_color_hex = next((c[2] for c in COLORS if c[0] == target_color_name), None)

            if not target_color_hex:
                print(f"SCHEDULE: Nincs érvényes HEX kód a '{target_color_name}' színhez ({today_name_hu}).")
                return # Ha nincs szín, ne csináljunk semmit

            # Ellenőrzés, hogy az aktuális idő a be/ki intervallumban van-e
            # Megengedőbb ellenőrzés: now >= on és now < off
            should_be_on = on_time_dt <= now_local < off_time_dt

            # Debug log
            # print(f"DEBUG ({today_name_hu}): Now={now_local.strftime('%H:%M:%S')}, On={on_time_dt.strftime('%H:%M:%S')}, Off={off_time_dt.strftime('%H:%M:%S')}, ShouldBeOn={should_be_on}, IsLEDOn={main_app.is_led_on}, LastColor={main_app.last_color_hex}, TargetColor={target_color_hex}")

            # Csak akkor küld parancsot, ha az állapot változna
            if should_be_on and (not main_app.is_led_on or main_app.last_color_hex != target_color_hex):
                print(f"SCHEDULE: Bekapcsolás/színváltás ({target_color_name}) - Idő: {now_local.strftime('%H:%M')}")
                # Közvetlenül hívjuk a controls widget metódusát
                if gui_widget.controls_widget:
                    gui_widget.controls_widget.send_color_command(target_color_hex)
            elif not should_be_on and main_app.is_led_on:
                print(f"SCHEDULE: Kikapcsolás - Idő: {now_local.strftime('%H:%M')}")
                # Közvetlenül hívjuk a controls widget metódusát
                if gui_widget.controls_widget:
                    gui_widget.controls_widget.turn_off_led()

        # else: # Debug: Ha valamelyik időpont hiányzik
        #     print(f"DEBUG ({today_name_hu}): Hiányzó időpont(ok): On={on_time_dt}, Off={off_time_dt}")


    except Exception as e:
         print(f"Váratlan hiba a schedule ellenőrzésekor ({today_name_hu}): {e}")
         traceback.print_exc()
