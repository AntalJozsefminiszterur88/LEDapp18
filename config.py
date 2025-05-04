# config.py (Frissített színekkel)

LATITUDE = 47.4338
LONGITUDE = 19.1931
TIMEZONE = "UTC+2" # Ezt a kódrészlet már nem használja aktívan, a tzlocal/pytz kezeli
CONFIG_FILE = "led_schedule.json" # Ütemezési beállítások fájlja
SETTINGS_FILE = "led_settings.json" # Általános beállítások fájlja (config_manager használja)
CHARACTERISTIC_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

DAYS = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"]

# Frissített színpaletta a jobb elkülönülés érdekében
COLORS = [
    # Név a GUI-n, HEX kód (CSS/Qt-hez), BLE parancs (HEX string)
    ("Piros",       "#FF0000", "7e000503ff000000ef"),
    ("Zöld",        "#008000", "7e00050300800000ef"), # Sötétebb zöld
    ("Kék",         "#0000FF", "7e0005030000ff00ef"),
    ("Arany",       "#FFD700", "7e000503ffd70000ef"), # Sárga helyett arany
    ("Türkiz",      "#008080", "7e00050300808000ef"), # Cián helyett türkiz (teal)
    ("Magenta",     "#FF00FF", "7e000503ff00ff00ef"), # Lila helyett magenta
    ("Narancs",     "#FF8C00", "7e000503ff8c0000ef"), # Sötétebb narancs
    ("Fehér",       "#FFFFFF", "7e000503ffffff00ef")
]
