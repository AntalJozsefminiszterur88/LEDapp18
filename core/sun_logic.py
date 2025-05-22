from datetime import datetime, timedelta
from core.location_utils import get_coordinates, get_sun_times

# Hungarian day names list (Monday=0, Sunday=6)
DAYS_HU_LIST = [
    'Hétfő',     # Monday
    'Kedd',      # Tuesday
    'Szerda',    # Wednesday
    'Csütörtök', # Thursday
    'Péntek',    # Friday
    'Szombat',   # Saturday
    'Vasárnap'   # Sunday
]

def get_local_sun_info():
    lat, lon, located = get_coordinates()
    sunrise, sunset = get_sun_times(lat, lon)
    return {
        "latitude": lat,
        "longitude": lon,
        "sunrise": sunrise,
        "sunset": sunset,
        "located": located
    }

def get_hungarian_day_name():
    """Returns the current day's name in Hungarian."""
    day_index = datetime.now().weekday() # Monday is 0 and Sunday is 6
    # Basic safety check, though weekday() should always return 0-6
    if 0 <= day_index < len(DAYS_HU_LIST):
        return DAYS_HU_LIST[day_index]
    return "Ismeretlen nap" # Fallback for unexpected index
