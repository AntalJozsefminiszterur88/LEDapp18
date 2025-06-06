"""Helpers for loading, saving and evaluating LED schedules."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, time as dt_time

import pytz

from ..config import COLORS, DAYS, CONFIG_FILE
from ..core.sun_logic import DAYS_HU

try:
    import tzlocal
    LOCAL_TZ = tzlocal.get_localzone()
except Exception:
    LOCAL_TZ = pytz.utc

try:
    from ..core.reconnect_handler import log_event
except Exception:  # pragma: no cover - fallback logger
    def log_event(msg: str) -> None:
        print(f"[schedule_service] {msg}")


DEFAULT_SCHEDULE = {
    day: {
        "color": COLORS[0][0] if COLORS else "",
        "on_time": "",
        "off_time": "",
        "sunrise": False,
        "sunrise_offset": 0,
        "sunset": False,
        "sunset_offset": 0,
    }
    for day in DAYS
}


def load_schedule(path: str = CONFIG_FILE) -> dict:
    """Load schedule data from ``path`` or return defaults."""
    schedule = DEFAULT_SCHEDULE.copy()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            for day in DAYS:
                day_data = schedule[day].copy()
                if day in loaded and isinstance(loaded[day], dict):
                    for key in day_data:
                        if key in loaded[day]:
                            expected_type = type(day_data[key])
                            value = loaded[day][key]
                            if key.endswith("_offset"):
                                try:
                                    day_data[key] = int(value)
                                except (ValueError, TypeError):
                                    log_event(
                                        f"Invalid offset '{value}' for {day} {key}; using 0"
                                    )
                                    day_data[key] = 0
                            elif isinstance(value, expected_type):
                                day_data[key] = value
                schedule[day] = day_data
            log_event(f"Schedule loaded from {path}")
        except Exception as e:  # pragma: no cover - log and fall back
            log_event(f"Error loading schedule from {path}: {e}")
    else:
        log_event(f"No schedule found at {path}; using defaults")
    return schedule


def save_schedule(schedule: dict, path: str = CONFIG_FILE) -> None:
    """Persist ``schedule`` to ``path``."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(schedule, fh, ensure_ascii=False, indent=4)
        log_event(f"Schedule saved to {path}")
    except Exception as e:  # pragma: no cover - log only
        log_event(f"Failed to save schedule to {path}: {e}")


def _get_times(data: dict, date_for_calc: datetime.date, sunrise, sunset):
    """Internal helper translating schedule entry to datetime values."""
    on_dt = None
    off_dt = None
    color = data.get("color")

    if data.get("sunrise"):
        offset = int(data.get("sunrise_offset", 0))
        if sunrise:
            try:
                on_dt = sunrise.replace(year=date_for_calc.year,
                                         month=date_for_calc.month,
                                         day=date_for_calc.day) + timedelta(minutes=offset)
            except Exception:
                pass
    else:
        on_str = data.get("on_time")
        if on_str:
            try:
                t = dt_time.fromisoformat(on_str)
                on_dt = LOCAL_TZ.localize(datetime.combine(date_for_calc, t))
            except ValueError:
                pass

    if data.get("sunset"):
        offset = int(data.get("sunset_offset", 0))
        if sunset:
            try:
                off_dt = sunset.replace(year=date_for_calc.year,
                                         month=date_for_calc.month,
                                         day=date_for_calc.day) + timedelta(minutes=offset)
            except Exception:
                pass
    else:
        off_str = data.get("off_time")
        if off_str:
            try:
                t = dt_time.fromisoformat(off_str)
                off_dt = LOCAL_TZ.localize(datetime.combine(date_for_calc, t))
            except ValueError:
                pass

    if on_dt and off_dt and off_dt <= on_dt:
        off_dt += timedelta(days=1)

    return on_dt, off_dt, color


def get_active_color(schedule: dict,
                     now: datetime | None = None,
                     sunrise=None,
                     sunset=None):
    """Return the active color hex value for ``now`` based on ``schedule``."""
    if not schedule:
        return None

    now_local = now or datetime.now(LOCAL_TZ)
    today = now_local.date()
    yesterday = today - timedelta(days=1)

    today_name = DAYS_HU.get(now_local.strftime("%A"), now_local.strftime("%A"))
    yesterday_name = DAYS_HU.get(
        (now_local - timedelta(days=1)).strftime("%A"),
        (now_local - timedelta(days=1)).strftime("%A"),
    )

    today_data = schedule.get(today_name, {})
    yesterday_data = schedule.get(yesterday_name, {})

    for data, date_for_calc, sr, ss in [
        (yesterday_data, yesterday, None, None),
        (today_data, today, sunrise, sunset),
    ]:
        if not data:
            continue
        on_dt, off_dt, color_name = _get_times(data, date_for_calc, sr, ss)
        if on_dt and off_dt and on_dt <= now_local < off_dt:
            color_info = next((c for c in COLORS if c[0] == color_name), None)
            if color_info:
                return color_info[1]
    return None
