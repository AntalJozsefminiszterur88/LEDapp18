# LEDapp/gui/gui2_controls_pyside.py (Javított Signal hívásokkal)

import time
import asyncio
from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QGridLayout, QSizePolicy
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QPalette, QColor

from config import COLORS # Importáljuk a színeket

# Logolás importálása, ha kell
try:
    from core.reconnect_handler import log_event
except ImportError:
    # Dummy logger
    def log_event(msg): print(f"[LOG - Dummy GUI2Controls]: {msg}")

class GUI2_ControlsWidget(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app

        # Fő horizontális elrendezés
        main_layout = QHBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(20)

        # --- Színes Gombok Rácsa ---
        color_grid_widget = QWidget()
        color_grid_layout = QGridLayout(color_grid_widget)
        color_grid_layout.setSpacing(5)

        colors_per_row = 4
        for i, (name, tk_color, hex_code) in enumerate(COLORS):
            row = i // colors_per_row
            col = i % colors_per_row
            btn = QPushButton(name)
            font = QFont("Arial", 12)
            btn.setFont(font)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.setMinimumSize(100, 40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {tk_color};
                    color: {self.get_contrasting_text_color(tk_color)};
                    border: 1px solid #555;
                    border-radius: 3px;
                }}
                QPushButton:pressed {{
                    background-color: {self.adjust_color(tk_color, -30)};
                }}
            """)
            btn.clicked.connect(lambda checked=False, h=hex_code: self.send_color_command(h))
            color_grid_layout.addWidget(btn, row, col)
        main_layout.addWidget(color_grid_widget)

        # --- Ki/Bekapcsoló Gombok ---
        power_frame_widget = QWidget()
        power_layout = QVBoxLayout(power_frame_widget)
        power_layout.setSpacing(5)

        self.power_off_btn = QPushButton("Kikapcsol")
        font_power = QFont("Arial", 12)
        self.power_off_btn.setFont(font_power)
        self.power_off_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.power_off_btn.setMinimumSize(100, 40)
        self.power_off_btn.clicked.connect(self.turn_off_led)
        power_layout.addWidget(self.power_off_btn)

        self.power_on_btn = QPushButton("Bekapcsol")
        self.power_on_btn.setFont(font_power)
        self.power_on_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.power_on_btn.setMinimumSize(100, 40)
        self.power_on_btn.clicked.connect(self.turn_on_led)
        power_layout.addWidget(self.power_on_btn)
        main_layout.addWidget(power_frame_widget)

        self.update_power_buttons()

    def get_contrasting_text_color(self, bg_hex):
        try:
            color = QColor(bg_hex)
            brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
            return "white" if brightness < 128 else "black"
        except Exception:
            return "black"

    def adjust_color(self, hex_color, amount):
        try:
             color = QColor(hex_color)
             r = max(0, min(255, color.red() + amount))
             g = max(0, min(255, color.green() + amount))
             b = max(0, min(255, color.blue() + amount))
             return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
             return hex_color

    def send_color_command(self, hex_code):
        """Elküldi a színváltás parancsot."""
        self.main_app.last_user_input = time.time()
        self.main_app.last_color_hex = hex_code
        self.main_app.is_led_on = True
        self.update_power_buttons()
        # Aszinkron parancsküldés a helperen keresztül, a command_error_signal-t használva
        self.main_app.async_helper.run_async_task(
            self.main_app.ble.send_command(hex_code),
            callback_error_signal=self.main_app.command_error_signal # Signal objektum átadása
        )

    def turn_off_led(self):
        """Elküldi a kikapcsolás parancsot."""
        self.main_app.last_user_input = time.time()
        self.main_app.is_led_on = False
        self.update_power_buttons()
        # Aszinkron parancsküldés a helperen keresztül, a command_error_signal-t használva
        self.main_app.async_helper.run_async_task(
            self.main_app.ble.send_command("7e00050300000000ef"),
            callback_error_signal=self.main_app.command_error_signal # Signal objektum átadása
        )

    def turn_on_led(self):
        """Elküldi a bekapcsolás parancsot (utolsó színnel)."""
        self.main_app.last_user_input = time.time()
        if self.main_app.last_color_hex:
            self.main_app.is_led_on = True
            self.update_power_buttons()
            # Aszinkron parancsküldés a helperen keresztül, a command_error_signal-t használva
            self.main_app.async_helper.run_async_task(
                self.main_app.ble.send_command(self.main_app.last_color_hex),
                callback_error_signal=self.main_app.command_error_signal # Signal objektum átadása
            )
        else:
            log_event("Figyelmeztetés: Nincs utoljára használt szín a bekapcsoláshoz.")

    def update_power_buttons(self):
        """Frissíti a ki/bekapcsoló gombok állapotát és stílusát."""
        if self.main_app.is_led_on:
            self.power_off_btn.setEnabled(True)
            self.power_off_btn.setStyleSheet("background-color: #ff6b6b; color: white; border: 1px solid #555; border-radius: 3px;")
            self.power_on_btn.setEnabled(False)
            self.power_on_btn.setStyleSheet("background-color: #dddddd; color: #888888; border: 1px solid #aaaaaa; border-radius: 3px;")
        else:
            self.power_off_btn.setEnabled(False)
            self.power_off_btn.setStyleSheet("background-color: #dddddd; color: #888888; border: 1px solid #aaaaaa; border-radius: 3px;")
            self.power_on_btn.setEnabled(True)
            self.power_on_btn.setStyleSheet("background-color: #4CAF50; color: white; border: 1px solid #555; border-radius: 3px;")
