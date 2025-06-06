# LEDapp/gui/gui2_schedule_pyside.py (ComboBox szélesség növelve)

import time
from datetime import datetime, timedelta, time as dt_time
import json
import os
import traceback
import pytz
import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout,
    QComboBox, QLineEdit, QCheckBox, QFrame, QSpacerItem, QSizePolicy,
    QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QTimer, Slot, QTime
from PySide6.QtGui import QFont, QColor

# --- Logolás ---
try:
    from ..core.reconnect_handler import log_event
except ImportError:
    def log_event(msg): print(f"[LOG - Dummy GUI2Schedule]: {msg}")
    log_event("Figyelmeztetés: core.reconnect_handler.log_event import sikertelen.")

# --- Modul Importok ---
try:
    from ..config import COLORS, DAYS, CONFIG_FILE
    from ..core import config_manager
    from ..core import registry_utils
    from ..core.sun_logic import get_local_sun_info, get_hungarian_day_name, DAYS_HU
    from ..core.location_utils import get_sun_times, LOCAL_TZ
    from . import gui2_schedule_logic as logic
    from .gui2_controls_pyside import GUI2_ControlsWidget
    logic.LOCAL_TZ = LOCAL_TZ
    log_event("GUI2Schedule: Szükséges modulok sikeresen importálva.")

except ImportError as e:
    log_event(f"KRITIKUS HIBA: Nem sikerült importálni a szükséges modulokat gui2_schedule_pyside.py-ban: {e}")
    traceback.print_exc()
    class DummyManager:
        DEFAULT_SETTINGS = {
            "start_with_windows": False, "last_device_address": None,
            "last_device_name": None, "auto_connect_on_startup": True,
        }
        @staticmethod
        def get_setting(key): return DummyManager.DEFAULT_SETTINGS.get(key)
        @staticmethod
        def set_setting(key, value): pass
        @staticmethod
        def is_in_startup(): return False
        @staticmethod
        def add_to_startup(): pass
        @staticmethod
        def remove_from_startup(): pass
    if 'config_manager' not in globals(): config_manager = DummyManager
    if 'registry_utils' not in globals(): registry_utils = DummyManager
    if 'logic' not in globals():
        class DummyLogic:
            LOCAL_TZ = pytz.utc
            @staticmethod
            def load_schedule_from_file(app): pass
            @staticmethod
            def save_schedule(widget): pass
            @staticmethod
            def check_schedule(widget): pass
            @staticmethod
            def get_local_sun_info(): return {"latitude": 0, "longitude": 0, "sunrise": None, "sunset": None, "located": False}
        logic = DummyLogic()
    if 'GUI2_ControlsWidget' not in globals():
        from PySide6.QtWidgets import QLabel
        GUI2_ControlsWidget = lambda app: QLabel("Vezérlő betöltési hiba")
    if 'DAYS_HU' not in globals(): DAYS_HU = {}
    if 'COLORS' not in globals(): COLORS = []
    if 'DAYS' not in globals(): DAYS = []
    if 'LOCAL_TZ' not in globals(): LOCAL_TZ = pytz.utc


# --- Osztály Definíció ---
class GUI2_Widget(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.setObjectName("GUI2_Widget_Instance")
        self.main_app = main_app

        # --- Fő vertikális layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(5)

        # --- Felső Sáv ---
        top_bar_layout = QHBoxLayout()
        # Bal: Eszköznév és Állapot
        top_left_widget = QWidget(); top_left_layout = QVBoxLayout(top_left_widget)
        top_left_layout.setContentsMargins(0,0,0,0); top_left_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        device_name = self.main_app.selected_device[0] if self.main_app.selected_device else "Ismeretlen"
        device_label = QLabel(f"Csatlakoztatott eszköz: {device_name}"); device_label.setFont(QFont("Arial", 12))
        top_left_layout.addWidget(device_label); self.status_indicator_label = QLabel("Állapot: Lekérdezés...")
        font_status = QFont("Arial", 11, QFont.Weight.Bold); self.status_indicator_label.setFont(font_status)
        top_left_layout.addWidget(self.status_indicator_label); top_bar_layout.addWidget(top_left_widget, 1)

        # Középső: Idő és Nap adatok
        info_widget = QWidget(); info_layout = QVBoxLayout(info_widget); info_layout.setContentsMargins(0,0,0,0); info_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label = QLabel("...")
        self.time_label.setFont(QFont("Arial", 13, QFont.Weight.Bold)); self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_layout.addWidget(self.time_label)
        try:
            sun_info = logic.get_local_sun_info(); self.main_app.latitude = sun_info["latitude"]; self.main_app.longitude = sun_info["longitude"]
            self.main_app.sunrise = sun_info["sunrise"]; self.main_app.sunset = sun_info["sunset"]; located = sun_info["located"]
        except Exception as e: log_event(f"Hiba a get_local_sun_info hívásakor GUI2 initben: {e}"); located = False; self.main_app.latitude = 47.4338; self.main_app.longitude = 19.1931; self.main_app.sunrise = None; self.main_app.sunset = None
        sunrise_str = self.main_app.sunrise.strftime('%H:%M') if self.main_app.sunrise else "N/A"; sunset_str = self.main_app.sunset.strftime('%H:%M') if self.main_app.sunset else "N/A"
        self.sun_label = QLabel(f"Napkelte: {sunrise_str} | Naplemente: {sunset_str}"); self.sun_label.setFont(QFont("Arial", 11, QFont.Weight.Bold)); self.sun_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.sun_label); lat = self.main_app.latitude; lon = self.main_app.longitude
        tz_name = logic.LOCAL_TZ.zone if hasattr(logic, 'LOCAL_TZ') and hasattr(logic.LOCAL_TZ, 'zone') else str(getattr(logic, 'LOCAL_TZ', 'Ismeretlen'))
        self.coord_label = QLabel(f"Koordináták: {lat:.4f}°É, {lon:.4f}°K | Időzóna: {tz_name}"); self.coord_label.setFont(QFont("Arial", 10, QFont.Weight.Bold)); self.coord_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.coord_label); top_bar_layout.addWidget(info_widget, 2)

        # Jobb: Pozíció státusz
        top_right_widget = QWidget(); top_right_layout = QVBoxLayout(top_right_widget); top_right_layout.setContentsMargins(0,0,0,0); top_right_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        status_text = "Pozíció: Meghatározva" if located else "Pozíció: Alapértelmezett"; status_color = "lime" if located else "#FFA500"
        self.position_status_label = QLabel(status_text); font_pos_status = QFont("Arial", 10, QFont.Weight.Bold); self.position_status_label.setFont(font_pos_status); self.position_status_label.setStyleSheet(f"color: {status_color}; background-color: transparent;")
        top_right_layout.addWidget(self.position_status_label); coord_only_label = QLabel(f"({lat:.2f}, {lon:.2f})"); coord_only_label.setFont(QFont("Arial", 8)); coord_only_label.setStyleSheet("color: gray; background-color: transparent;")
        top_right_layout.addWidget(coord_only_label, 0, Qt.AlignmentFlag.AlignRight); top_bar_layout.addWidget(top_right_widget, 1)
        # --- Felső sáv vége ---
        main_layout.addLayout(top_bar_layout)
        main_layout.addStretch(1) # Rugalmas térköz visszaállítása

        # --- Vezérlő Widget ---
        self.controls_widget = GUI2_ControlsWidget(self.main_app)
        main_layout.addWidget(self.controls_widget, 0, Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch(1) # Rugalmas térköz visszaállítása

        # --- Ütemező Táblázat (GroupBox nélkül) ---
        table_container = QWidget()
        table_layout = QGridLayout(table_container)
        table_layout.setSpacing(5)
        table_layout.setHorizontalSpacing(15)
        table_layout.setVerticalSpacing(8)
        table_layout.setColumnStretch(1, 1); table_layout.setColumnStretch(2, 0); table_layout.setColumnStretch(3, 0); table_layout.setColumnStretch(5, 0); table_layout.setColumnStretch(7, 0)
        headers = ["Nap", "Szín", "Fel", "Le", "Napkelte", "+/-", "Napnyugta", "+/-"]
        for i, header in enumerate(headers): label = QLabel(header); label.setFont(QFont("Arial", 10, QFont.Weight.Bold)); align = Qt.AlignmentFlag.AlignLeft if i == 0 else Qt.AlignmentFlag.AlignCenter; table_layout.addWidget(label, 0, i, align)
        self.schedule_widgets = {}; self.time_comboboxes = []; logic.load_schedule_from_file(self.main_app); color_display_names = ["Nincs kiválasztva"] + [c[0] for c in COLORS]; valid_color_names = [c[0] for c in COLORS]
        for i, day_hu in enumerate(DAYS):
            row = i + 1; day_widgets = {}; schedule_data = self.main_app.schedule.get(day_hu, {})
            day_label = QLabel(day_hu, font=QFont("Arial", 10)); table_layout.addWidget(day_label, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            color_cb = QComboBox(); color_cb.addItems(color_display_names); saved_color = schedule_data.get("color", ""); color_cb.setCurrentIndex(color_display_names.index(saved_color) if saved_color in valid_color_names else 0)
            table_layout.addWidget(color_cb, row, 1); day_widgets["color"] = color_cb
            time_values = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, 5)]
            # <<<--- ITT VAN A VÁLTOZTATÁS --->>>
            on_time_cb = QComboBox(); on_time_cb.addItems(time_values); on_time_cb.setCurrentText(schedule_data.get("on_time", "")); on_time_cb.setEditable(True); on_time_cb.setFixedWidth(85) # Szélesség növelve
            table_layout.addWidget(on_time_cb, row, 2, Qt.AlignmentFlag.AlignCenter); day_widgets["on_time"] = on_time_cb; self.time_comboboxes.append(on_time_cb)
            off_time_cb = QComboBox(); off_time_cb.addItems(time_values); off_time_cb.setCurrentText(schedule_data.get("off_time", "")); off_time_cb.setEditable(True); off_time_cb.setFixedWidth(85) # Szélesség növelve
            table_layout.addWidget(off_time_cb, row, 3, Qt.AlignmentFlag.AlignCenter); day_widgets["off_time"] = off_time_cb; self.time_comboboxes.append(off_time_cb)
            # <<<--- VÁLTOZTATÁS VÉGE --->>>
            sunrise_cb = QCheckBox(); sunrise_cb.setChecked(schedule_data.get("sunrise", False)); table_layout.addWidget(sunrise_cb, row, 4, Qt.AlignmentFlag.AlignCenter)
            day_widgets["sunrise"] = sunrise_cb; sunrise_cb.stateChanged.connect(lambda state, d=day_hu: self.toggle_sun_time(state, d, "sunrise"))
            sunrise_offset_entry = QLineEdit(str(schedule_data.get("sunrise_offset", 0))); sunrise_offset_entry.setFixedWidth(40); sunrise_offset_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
            table_layout.addWidget(sunrise_offset_entry, row, 5, Qt.AlignmentFlag.AlignCenter); day_widgets["sunrise_offset"] = sunrise_offset_entry
            sunset_cb = QCheckBox(); sunset_cb.setChecked(schedule_data.get("sunset", False)); table_layout.addWidget(sunset_cb, row, 6, Qt.AlignmentFlag.AlignCenter)
            day_widgets["sunset"] = sunset_cb; sunset_cb.stateChanged.connect(lambda state, d=day_hu: self.toggle_sun_time(state, d, "sunset"))
            sunset_offset_entry = QLineEdit(str(schedule_data.get("sunset_offset", 0))); sunset_offset_entry.setFixedWidth(40); sunset_offset_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
            table_layout.addWidget(sunset_offset_entry, row, 7, Qt.AlignmentFlag.AlignCenter); day_widgets["sunset_offset"] = sunset_offset_entry
            self.schedule_widgets[day_hu] = day_widgets
            self.toggle_sun_time(sunrise_cb.checkState(), day_hu, "sunrise")
            self.toggle_sun_time(sunset_cb.checkState(), day_hu, "sunset")
        # --- Ütemező Táblázat Vége ---
        main_layout.addWidget(table_container, 0, Qt.AlignmentFlag.AlignCenter)
        main_layout.addSpacing(10)

        # --- Ütemező és Indítási Gombok / Checkbox egy sorban ---
        schedule_action_layout = QHBoxLayout()
        schedule_action_layout.setContentsMargins(10,0,10,0)
        self.startup_checkbox = QCheckBox("Indítás a Windows-zal")
        if not isinstance(config_manager, type) or config_manager.__name__ != 'DummyManager':
            try:
                self.startup_checkbox.setChecked(config_manager.get_setting("start_with_windows"))
                self.startup_checkbox.stateChanged.connect(self.toggle_startup)
            except Exception as e_cfg:
                 log_event(f"Hiba a startup checkbox beállításakor: {e_cfg}")
                 self.startup_checkbox.setEnabled(False)
        else:
            log_event("ConfigManager dummy, startup checkbox letiltva.")
            self.startup_checkbox.setEnabled(False)
        schedule_action_layout.addWidget(self.startup_checkbox)
        schedule_action_layout.addStretch(1)
        reset_button = QPushButton("Alaphelyzet"); reset_button.clicked.connect(self.reset_schedule_gui)
        schedule_action_layout.addWidget(reset_button)
        save_button = QPushButton("Mentés"); save_button.clicked.connect(lambda: logic.save_schedule(self))
        schedule_action_layout.addWidget(save_button)
        main_layout.addLayout(schedule_action_layout)
        # --- Ütemező és Indítási Gombok Vége ---

        main_layout.addStretch(1) # Rugalmas térköz alul

        # --- Alsó Gombok (Vissza) ---
        bottom_button_layout = QHBoxLayout();
        bottom_button_layout.addStretch(1)
        back_button = QPushButton("Vissza");
        try: back_button.clicked.connect(self.main_app.gui_manager.load_gui1)
        except AttributeError as e: log_event(f"HIBA a Vissza gomb connect során: {e}."); back_button.setEnabled(False)
        bottom_button_layout.addWidget(back_button)
        main_layout.addLayout(bottom_button_layout)
        # --- Alsó Gombok Vége ---

        # --- Időzítők ---
        self.update_time_timer = QTimer(self) # Csak az óra időzítője
        self.update_time_timer.timeout.connect(self.update_time)
        self.update_time_timer.start(1000)
        self.update_time()

    # --- Slot Metódusok ---
    def stop_timers(self):
        log_event("GUI2 Timers stopping (only clock timer)...")
        if hasattr(self, 'update_time_timer'): self.update_time_timer.stop()
        log_event("GUI2 Timers stopped.")

    @Slot()
    def reset_schedule_gui(self):
        reply = QMessageBox.question(self, 'Alaphelyzet',
                                     "Biztosan visszaállítod az összes ütemezési beállítást az alapértelmezettre?\n(Ez a művelet nem menti a változásokat.)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            log_event("Ütemező GUI visszaállítása alaphelyzetbe...")
            for day, widgets in self.schedule_widgets.items():
                widgets["color"].setCurrentIndex(0)
                widgets["on_time"].setCurrentText("")
                widgets["off_time"].setCurrentText("")
                widgets["sunrise"].setChecked(False)
                widgets["sunrise_offset"].setText("0")
                widgets["sunset"].setChecked(False)
                widgets["sunset_offset"].setText("0")
                self.toggle_sun_time(Qt.CheckState.Unchecked.value, day, "sunrise")
                self.toggle_sun_time(Qt.CheckState.Unchecked.value, day, "sunset")


    @Slot(int)
    def toggle_startup(self, state):
        is_checked = bool(state == Qt.CheckState.Checked.value)
        log_event(f"'Indítás a Windows-zal' checkbox {'bekapcsolva' if is_checked else 'kikapcsolva'}.")
        is_dummy_cfg = isinstance(config_manager, type) and config_manager.__name__ == 'DummyManager'
        is_dummy_reg = isinstance(registry_utils, type) and registry_utils.__name__ == 'DummyManager'
        if is_dummy_cfg or is_dummy_reg:
             log_event("HIBA: Nem lehet módosítani az indítási beállításokat, mert a config/registry manager nem töltődött be helyesen.")
             QMessageBox.critical(self, "Import Hiba", "Nem sikerült betölteni a beállításkezelő modulokat. Az indítási beállítás nem módosítható.")
             self.startup_checkbox.blockSignals(True)
             self.startup_checkbox.setChecked(not is_checked)
             self.startup_checkbox.blockSignals(False)
             return
        config_manager.set_setting("start_with_windows", is_checked)
        success = False
        if is_checked:
            success = registry_utils.add_to_startup()
            if not success:
                QMessageBox.warning(self, "Hiba", "Nem sikerült hozzáadni az alkalmazást az indítópulthoz.\nLehet, hogy nincs megfelelő jogosultság.")
        else:
            success = registry_utils.remove_from_startup()
            if not success:
                 QMessageBox.warning(self, "Hiba", "Nem sikerült eltávolítani az alkalmazást az indítópultból.\nLehet, hogy nincs megfelelő jogosultság.")
        if not success:
             log_event("Registry művelet sikertelen, checkbox és beállítás visszaállítása.")
             self.startup_checkbox.blockSignals(True)
             self.startup_checkbox.setChecked(not is_checked)
             self.startup_checkbox.blockSignals(False)
             config_manager.set_setting("start_with_windows", not is_checked)


    # <<<--- ITT VAN A MÓDOSÍTOTT LOGIKA --->>>
    @Slot(int, str, str)
    def toggle_sun_time(self, state, day, sun_event_type):
        """
        Engedélyezi/letiltja a megfelelő idő és offset mezőket a Napkelte/Napnyugta
        checkbox állapota alapján. Letiltáskor kiüríti az idő mezőt.
        """
        is_checked = bool(state == Qt.CheckState.Checked.value)

        if day not in self.schedule_widgets:
            log_event(f"HIBA: Ismeretlen nap a toggle_sun_time-ban: {day}")
            return

        day_widgets = self.schedule_widgets[day]

        offset_entry_key = f"{sun_event_type}_offset"
        time_combo_key = "on_time" if sun_event_type == "sunrise" else "off_time"

        if offset_entry_key not in day_widgets or time_combo_key not in day_widgets:
            log_event(f"HIBA: Hiányzó widget kulcsok a toggle_sun_time-ban: {offset_entry_key} vagy {time_combo_key}")
            return

        offset_entry = day_widgets[offset_entry_key]
        time_combo = day_widgets[time_combo_key]

        if is_checked:
            # Ha a Napkelte/Napnyugta be van jelölve:
            time_combo.setEnabled(False)    # <<< Idő mező letiltása >>>
            time_combo.setCurrentText("")   # <<< Idő mező kiürítése >>>
            offset_entry.setEnabled(True)   # Offset mező engedélyezése
        else:
            # Ha a Napkelte/Napnyugta nincs bejelölve:
            time_combo.setEnabled(True)     # <<< Idő mező engedélyezése >>>
            offset_entry.setEnabled(False)  # Offset mező letiltása
            # offset_entry.setText("0") # Opcionális: offset nullázása
    # <<<--- MÓDOSÍTOTT LOGIKA VÉGE --->>>


    @Slot()
    def update_time(self):
        try:
            now = datetime.now(logic.LOCAL_TZ)
            magyar_nap = DAYS_HU.get(now.strftime('%A'), now.strftime('%A'))
            self.time_label.setText(f"{now.strftime('%Y.%m.%d')} | {magyar_nap} | {now.strftime('%H:%M:%S')}")
        except Exception as e:
            log_event(f"Hiba az idő frissítésekor: {e}")
            self.time_label.setText("Idő hiba")
