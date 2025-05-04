# core/location_utils.py (Részletesebb hibalogolással)

import requests
from datetime import datetime
from suntime import Sun
from pytz import timezone as pytz_timezone
import traceback # Importáljuk a tracebacket

# Logolás importálása (ha a reconnect_handler definiálja)
try:
    from .reconnect_handler import log_event
except ImportError:
     # Dummy log_event ha a reconnect_handler nem elérhető innen
    def log_event(msg): print(f"[LOG - Dummy LocUtils]: {msg}")


BUDAPEST_COORDS = (47.4338, 19.1931)
LOCAL_TZ = pytz_timezone("Europe/Budapest") # Feltételezzük, hogy ez létezik
UTC_TZ = pytz_timezone("UTC")

def get_coordinates():
    """Megpróbálja lekérni a koordinátákat IP alapján."""
    try:
        log_event("Koordináták lekérése (ip-api.com)...")
        # Növelt timeout és User-Agent beállítása
        headers = {'User-Agent': 'LEDApp/1.0'}
        response = requests.get("http://ip-api.com/json/", timeout=10, headers=headers)
        response.raise_for_status() # Hibát dob HTTP hibakód esetén
        data = response.json()
        if data.get("status") == "success":
            lat = data["lat"]
            lon = data["lon"]
            log_event(f"Koordináták sikeresen lekérve: Lat={lat}, Lon={lon}")
            return lat, lon, True
        else:
            log_event(f"Figyelmeztetés: ip-api.com nem 'success' státuszt adott vissza: {data.get('message', 'N/A')}")
            return BUDAPEST_COORDS[0], BUDAPEST_COORDS[1], False
    except requests.exceptions.Timeout:
        log_event("Hiba: Timeout a koordináták lekérése közben.")
        # traceback.print_exc() # Opcionális: Teljes traceback
        return BUDAPEST_COORDS[0], BUDAPEST_COORDS[1], False
    except requests.exceptions.RequestException as e:
        log_event(f"Hiba a koordináták lekérése közben (RequestException): {e}")
        # traceback.print_exc() # Opcionális: Teljes traceback
        return BUDAPEST_COORDS[0], BUDAPEST_COORDS[1], False
    except Exception as e:
        log_event(f"Váratlan hiba a koordináták lekérése közben: {e}")
        log_event(f"Traceback:\n{traceback.format_exc()}") # Itt írjuk ki a teljes tracebacket
        return BUDAPEST_COORDS[0], BUDAPEST_COORDS[1], False

def get_sun_times(lat, lon, now=None):
    """Kiszámolja a napkelte/napnyugta időpontokat a megadott koordinátákra."""
    try:
        # Dátum objektum a now alapján, vagy a mai nap, ha nincs megadva
        target_date = now.date() if now else datetime.now(LOCAL_TZ).date()

        sun = Sun(lat, lon)
        # Használjuk a dátum objektumot a számításhoz
        sunrise_utc_dt = sun.get_sunrise_time(target_date, UTC_TZ)
        sunset_utc_dt = sun.get_sunset_time(target_date, UTC_TZ)

        # Átváltás helyi időzónára
        sunrise_local = sunrise_utc_dt.astimezone(LOCAL_TZ)
        sunset_local = sunset_utc_dt.astimezone(LOCAL_TZ)
        log_event(f"Napkelte/Napnyugta számítva ({lat:.2f},{lon:.2f}): Kelte={sunrise_local.strftime('%H:%M')}, Nyugta={sunset_local.strftime('%H:%M')}")
        return sunrise_local, sunset_local
    except Exception as e:
        log_event(f"Hiba a napkelte/napnyugta számítása közben: {e}")
        # traceback.print_exc() # Opcionális
        return None, None # Hiba esetén None-t adunk vissza
