# LEDapp/core/reconnect_handler.py (Éjfél átnyúlás javítással)
import asyncio
import time
from datetime import datetime, timedelta, time as dt_time
import traceback
import threading
import pytz

from bleak import BleakClient, BleakScanner, BleakError, BLEDevice

# Szükséges importok
try:
    from ..config import COLORS, DAYS, CHARACTERISTIC_UUID
    try:
        from ..gui.gui2_schedule_logic import LOCAL_TZ
    except ImportError:
        try:
            from ..gui.gui2_schedule_logic import LOCAL_TZ
        except ImportError:
            print("Figyelmeztetés: LOCAL_TZ import sikertelen, UTC használata a handlerben.")
            LOCAL_TZ = pytz.utc
    from .sun_logic import DAYS_HU
except ImportError as e:
    print(f"HIBA: Nem sikerült importálni a szükséges config/logic elemeket a reconnect_handler.py-ban: {e}")
    COLORS, DAYS, DAYS_HU = [], [], {}
    CHARACTERISTIC_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
    LOCAL_TZ = pytz.utc

# Konstansok
KEEP_ALIVE_COMMAND = "7e00000000000000ef"
CONNECT_TIMEOUT = 15.0
PING_INTERVAL = 20.0
INACTIVITY_PING_THRESHOLD = 5.0
RECONNECT_DELAY = 1.0
MAX_CONNECT_ATTEMPTS = 3
RESCAN_DELAY = 5.0
LOOP_SLEEP = 0.5
SCHEDULE_CHECK_INTERVAL = 5.0

def log_event(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)

async def rescan_and_find_device(target_name):
    # ... (változatlan) ...
    log_event(f"Új keresés indítása a(z) '{target_name}' nevű eszközhöz...")
    try:
        devices = await BleakScanner.discover(timeout=15.0)
        for device in devices:
            if device.name == target_name:
                log_event(f"Eszköz újra megtalálva: {device.name} ({device.address})")
                return device.address
        log_event(f"'{target_name}' nevű eszköz nem található a keresés során.")
        return None
    except asyncio.CancelledError:
        log_event("Figyelmeztetés: Az eszközkeresés megszakadt (CancelledError).")
        return None
    except Exception as e:
        log_event(f"Hiba az újrakeresés során: {e}")
        return None


def _get_schedule_times(schedule_data, date_for_calc, app_sunrise, app_sunset):
    """
    Segédfüggvény egy adott nap schedule adataiból a be/ki időpontok kiszámításához.
    Visszaadja (on_time_dt, off_time_dt, color_name) tuple-t.
    A dt objektumok már időzóna-aware objektumok lesznek.
    """
    on_time_dt = None
    off_time_dt = None
    color_name = schedule_data.get("color")

    # --- Bekapcsolási idő ---
    if schedule_data.get("sunrise", False):
        offset = schedule_data.get("sunrise_offset", 0)
        if app_sunrise:
            try:
                # app_sunrise már TZ-aware
                on_time_dt = app_sunrise.replace(year=date_for_calc.year, month=date_for_calc.month, day=date_for_calc.day) + timedelta(minutes=offset)
            except Exception: pass # Hiba esetén None marad
    else:
        on_time_str = schedule_data.get("on_time")
        if on_time_str:
            try:
                time_obj = dt_time.fromisoformat(on_time_str)
                naive_dt = datetime.combine(date_for_calc, time_obj)
                on_time_dt = LOCAL_TZ.localize(naive_dt)
            except ValueError: pass

    # --- Kikapcsolási idő ---
    if schedule_data.get("sunset", False):
        offset = schedule_data.get("sunset_offset", 0)
        if app_sunset:
            try:
                # app_sunset már TZ-aware
                off_time_dt = app_sunset.replace(year=date_for_calc.year, month=date_for_calc.month, day=date_for_calc.day) + timedelta(minutes=offset)
            except Exception: pass
    else:
        off_time_str = schedule_data.get("off_time")
        if off_time_str:
            try:
                time_obj = dt_time.fromisoformat(off_time_str)
                naive_dt = datetime.combine(date_for_calc, time_obj)
                off_time_dt = LOCAL_TZ.localize(naive_dt)
            except ValueError: pass

    # Éjfél átnyúlás kezelése a kikapcsolási időnél
    if on_time_dt and off_time_dt and off_time_dt <= on_time_dt:
        off_time_dt += timedelta(days=1)

    return on_time_dt, off_time_dt, color_name


async def check_and_apply_schedule(app, client):
     """Ellenőrzi az ütemezést (aktuális ÉS előző napi átnyúlást) és korrigál."""
     if not app or not hasattr(app, 'schedule') or not app.schedule or not client or not client.is_connected:
         return

     now_local = datetime.now(LOCAL_TZ)
     today_date = now_local.date()
     yesterday_date = today_date - timedelta(days=1)

     today_name_py = now_local.strftime('%A')
     today_name_hu = DAYS_HU.get(today_name_py, today_name_py)

     yesterday_name_py = (now_local - timedelta(days=1)).strftime('%A')
     yesterday_name_hu = DAYS_HU.get(yesterday_name_py, yesterday_name_py)

     # Adatok lekérése a mai és tegnapi napra
     today_schedule_data = app.schedule.get(today_name_hu, {})
     yesterday_schedule_data = app.schedule.get(yesterday_name_hu, {})

     # Napkelte/napnyugta adatok lekérése (már TZ-aware objektumoknak kell lenniük)
     app_sunrise_today = app.sunrise if hasattr(app, 'sunrise') and app.sunrise else None
     app_sunset_today = app.sunset if hasattr(app, 'sunset') and app.sunset else None
     # A tegnapi napkelte/napnyugta nem releváns az átnyúlás szempontjából,
     # a tegnapi napra vonatkozó számítást a tegnapi dátummal végezzük.

     should_be_on = False
     final_target_color_name = None
     final_target_hex_code = None
     final_target_hex_value = None

     try:
         # --- Előző napról átnyúló intervallum ellenőrzése ---
         if yesterday_schedule_data:
             on_dt_y, off_dt_y, color_y = _get_schedule_times(
                 yesterday_schedule_data, yesterday_date, None, None # Tegnapi napkelte/nyugta nem kell itt
             )
             # Csak akkor releváns, ha a kikapcsolás átnyúlik a mai napra ÉS az aktuális idő még előtte van
             if off_dt_y and off_dt_y.date() == today_date and now_local < off_dt_y:
                 # És persze a bekapcsolásnak is léteznie kellett tegnap
                 if on_dt_y and now_local >= on_dt_y: # Technikaiag az on_dt_y tegnapra vonatkozik
                      should_be_on = True
                      final_target_color_name = color_y
                      log_event(f"SCHEDULE CHECK: Aktív intervallum tegnapról ({yesterday_name_hu}): {on_dt_y.strftime('%H:%M')} - {off_dt_y.strftime('%H:%M')}, Szín: {color_y}")


         # --- Aktuális napi intervallum ellenőrzése ---
         # Csak akkor nézzük, ha még nem találtunk aktív intervallumot tegnapról
         if not should_be_on and today_schedule_data:
             on_dt_t, off_dt_t, color_t = _get_schedule_times(
                 today_schedule_data, today_date, app_sunrise_today, app_sunset_today
             )
             # Ellenőrizzük, hogy az aktuális idő a mai intervallumban van-e
             if on_dt_t and off_dt_t and on_dt_t <= now_local < off_dt_t:
                 should_be_on = True
                 final_target_color_name = color_t
                 log_event(f"SCHEDULE CHECK: Aktív intervallum ma ({today_name_hu}): {on_dt_t.strftime('%H:%M')} - {off_dt_t.strftime('%H:%M')}, Szín: {color_t}")

         # --- Színkód kikeresése, ha bekapcsolva kell lennie ---
         if should_be_on and final_target_color_name:
             target_color_info = next((c for c in COLORS if c[0] == final_target_color_name), None)
             if target_color_info:
                 final_target_hex_code = target_color_info[2] # Parancs
                 final_target_hex_value = target_color_info[1] # Érték (#rrggbb)
             else:
                 # Ha a névhez nincs szín (pl. "Nincs kiválasztva"), akkor mégsem kell bekapcsolva lennie
                 should_be_on = False
                 log_event(f"SCHEDULE CHECK: Aktív intervallumhoz ('{final_target_color_name}') nincs érvényes szín rendelve.")


         # --- Korrekció végrehajtása ---
         correction_needed = False
         command_to_send = None
         new_app_state_on = app.is_led_on
         new_app_state_color = app.last_color_hex

         if should_be_on:
             # Ha be kellene kapcsolva lennie, de nincs, VAGY be van, de nem jó színnel
             if not app.is_led_on or app.last_color_hex != final_target_hex_value:
                 log_event(f"SCHEDULE CORRECTION: Bekapcsolás/színváltás -> {final_target_color_name} ({now_local.strftime('%H:%M:%S')})")
                 command_to_send = final_target_hex_code
                 new_app_state_on = True
                 new_app_state_color = final_target_hex_value
                 correction_needed = True
         else: # should_be_off
             # Ha ki kellene kapcsolva lennie, de be van kapcsolva
             if app.is_led_on:
                 log_event(f"SCHEDULE CORRECTION: Kikapcsolás ({now_local.strftime('%H:%M:%S')})")
                 command_to_send = "7e00050300000000ef" # Kikapcsoló parancs
                 new_app_state_on = False
                 # new_app_state_color marad az utolsó szín
                 correction_needed = True

         if correction_needed and command_to_send:
             try:
                 await client.write_gatt_char(CHARACTERISTIC_UUID, bytes.fromhex(command_to_send), response=False)
                 app.is_led_on = new_app_state_on
                 app.last_color_hex = new_app_state_color
                 app.last_user_input = time.time()
             except Exception as e:
                 log_event(f"HIBA az ütemezés korrekciós parancsának küldésekor: {e}")

     except Exception as e:
          log_event(f"Váratlan hiba a schedule ellenőrzésekor: {e}")
          traceback.print_exc()


async def start_ble_connection_loop(app, stop_event: threading.Event):
    """Folyamatosan figyeli a kapcsolatot, újracsatlakozik, ébren tartja és ellenőrzi az ütemezést."""
    # ... (Függvény eleje, változók inicializálása változatlan) ...
    if not app.selected_device or not app.selected_device[0]:
        log_event("Hiba: Nincs kiválasztott eszköznév a kapcsolattartáshoz. Loop leáll.")
        return

    original_device_name = app.selected_device[0]
    current_address = app.selected_device[1]
    log_event(f"Kapcsolat figyelő indítása: '{original_device_name}' ({current_address})")
    last_ping_time = time.time()
    last_schedule_check_time = 0
    connection_attempts = 0

    while True:
        if stop_event.is_set():
            log_event("Stop event észlelve, reconnect loop leállítása...")
            break

        try:
            current_client = app.ble.client if hasattr(app, 'ble') and app.ble else None

            # --- Kapcsolat Ellenőrzése és Újracsatlakozás ---
            if not current_client or not current_client.is_connected:
                # ... (Újracsatlakozási logika változatlan, lásd előző válaszban) ...
                if app.connection_status != "disconnected":
                     if hasattr(app, 'connection_status_signal'):
                         app.connection_status_signal.emit("disconnected")
                     app.connection_status = "disconnected"

                log_event(f"Kapcsolat ellenőrzés: Nincs kapcsolat '{original_device_name}' ({current_address}). Próba #{connection_attempts + 1}...")

                if connection_attempts >= MAX_CONNECT_ATTEMPTS:
                    log_event("Maximum csatlakozási kísérlet elérve, újrakeresés...")
                    new_address = await rescan_and_find_device(original_device_name)
                    connection_attempts = 0
                    if new_address:
                        if new_address != current_address:
                             log_event(f"Eszköz új címen található: {new_address}")
                             current_address = new_address
                             app.selected_device = (original_device_name, current_address)
                        else:
                             log_event("Eszköz ugyanazon a címen található.")
                    else:
                        log_event(f"Eszköz nem található keresés után sem. Várakozás ({RESCAN_DELAY}s)...")
                        if stop_event.is_set(): break
                        await asyncio.sleep(RESCAN_DELAY)
                        continue

                try:
                    if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("connecting")
                    app.connection_status = "connecting"
                    if app.ble and app.ble.client:
                        log_event("Régi app.ble.client referencia létezik, bontás kísérlete...")
                        old_client_ref = app.ble.client
                        app.ble.client = None
                        try:
                            if old_client_ref and old_client_ref.is_connected:
                                 await old_client_ref.disconnect()
                                 log_event("Régi kliens bontva.")
                        except Exception as disconn_err: log_event(f"Figyelmeztetés: Hiba a régi kliens bontásakor: {disconn_err}")

                    log_event(f"Új BleakClient létrehozása és hozzárendelése: {current_address}...")
                    client = BleakClient(current_address)
                    app.ble.client = client

                    log_event(f"Csatlakozás megkezdése: {current_address} (timeout={CONNECT_TIMEOUT}s)...")
                    await client.connect(timeout=CONNECT_TIMEOUT)

                    if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("connected")
                    app.connection_status = "connected"
                    log_event(f"Sikeresen csatlakozva: '{original_device_name}' ({current_address})")
                    last_ping_time = time.time()
                    last_schedule_check_time = 0 # Azonnali ellenőrzés kérése
                    connection_attempts = 0

                except (BleakError, asyncio.TimeoutError, asyncio.CancelledError) as e:
                    log_event(f"Kapcsolódási hiba #{connection_attempts + 1} ({type(e).__name__}): {e}")
                    if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("disconnected")
                    app.connection_status = "disconnected"
                    if app.ble: app.ble.client = None
                    connection_attempts += 1
                    if stop_event.is_set(): break
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue
                except Exception as e:
                    log_event(f"Általános hiba a kapcsolat létrehozásakor #{connection_attempts + 1}: {e}")
                    log_event(f"Traceback:\n{traceback.format_exc()}")
                    if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("disconnected")
                    app.connection_status = "disconnected"
                    if app.ble: app.ble.client = None
                    connection_attempts += 1
                    if stop_event.is_set(): break
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue

            # --- Ha Csatlakozva van: Ping és Ütemezés ---
            else: # current_client and current_client.is_connected
                 if app.connection_status != "connected":
                     log_event("Kliens csatlakozva, de app státusz nem 'connected'. Státusz frissítése.")
                     if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("connected")
                     app.connection_status = "connected"
                     last_schedule_check_time = 0 # Azonnali ellenőrzés

                 now = time.time()

                 # *** Ütemezés Ellenőrzés ***
                 if now - last_schedule_check_time >= SCHEDULE_CHECK_INTERVAL:
                     # Itt már a javított logikát hívjuk
                     await check_and_apply_schedule(app, current_client)
                     last_schedule_check_time = now

                 # *** Keep-Alive Ping ***
                 # ... (ping logika változatlan) ...
                 last_input_time = app.last_user_input if hasattr(app, 'last_user_input') else now
                 elapsed_since_last_ping = now - last_ping_time
                 elapsed_since_input = now - last_input_time
                 should_ping = elapsed_since_last_ping >= PING_INTERVAL or \
                               (elapsed_since_input >= INACTIVITY_PING_THRESHOLD and elapsed_since_last_ping >= INACTIVITY_PING_THRESHOLD)
                 if should_ping:
                     try:
                         if current_client and current_client.is_connected:
                             await current_client.write_gatt_char(CHARACTERISTIC_UUID, bytes.fromhex(KEEP_ALIVE_COMMAND), response=False)
                             last_ping_time = time.time()
                         else:
                             log_event("Ping kihagyva, a kliens már nem csatlakozik (pingelés előtt ellenőrizve).")
                     except (BleakError, asyncio.CancelledError) as e:
                         log_event(f"Hiba ping küldésekor ({type(e).__name__}): {e}")
                         if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("disconnected")
                         app.connection_status = "disconnected"
                         if app.ble: app.ble.client = None
                         if stop_event.is_set(): break
                         continue
                     except Exception as e:
                         log_event(f"Általános hiba ping küldésekor: {e}")
                         log_event(f"Traceback:\n{traceback.format_exc()}")
                         if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("disconnected")
                         app.connection_status = "disconnected"
                         if app.ble: app.ble.client = None
                         if stop_event.is_set(): break
                         await asyncio.sleep(0.5)
                         continue

            # --- Ciklus végi várakozás ---
            if stop_event.is_set():
                log_event("Stop event észlelve (ciklus végén), reconnect loop leállítása...")
                break
            await asyncio.sleep(LOOP_SLEEP)

        # --- Globális Hiba és Kilépés Kezelés ---
        except asyncio.CancelledError:
            log_event("A start_ble_connection_loop fő ciklusa megszakadt (CancelledError). Loop leáll.")
            break
        except Exception as e:
            log_event(f"Váratlan hiba a start_ble_connection_loop fő ciklusában: {e}")
            log_event(f"Traceback:\n{traceback.format_exc()}")
            if app.ble: app.ble.client = None
            app.connection_status = "disconnected"
            if hasattr(app, 'connection_status_signal'): app.connection_status_signal.emit("disconnected")
            if stop_event.is_set(): break
            await asyncio.sleep(LOOP_SLEEP * 4)

    # --- Loop Végi Cleanup ---
    # ... (cleanup logika változatlan) ...
    log_event("start_ble_connection_loop vége (while ciklusból kilépve), utolsó cleanup...")
    final_client = app.ble.client if hasattr(app, 'ble') and app.ble else None
    if final_client and final_client.is_connected:
        try:
            log_event("Loop végén kliens bontása...")
            loop = asyncio.get_running_loop()
            if loop.is_running():
                await final_client.disconnect()
                log_event("Kliens bontva a loop végén (futó loopban).")
            else:
                 log_event("Figyelmeztetés: Loop nem fut a loop végi disconnecthez.")
        except RuntimeError as e:
             log_event(f"RuntimeError a loop végi disconnect során: {e}")
        except Exception as final_disconn_err:
             log_event(f"Hiba a kliens bontásakor a loop végén: {final_disconn_err}")
    if hasattr(app, 'ble') and app.ble:
        app.ble.client = None
    log_event("Reconnect handler cleanup befejezve.")
