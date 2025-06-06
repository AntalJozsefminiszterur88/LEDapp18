"""High level application controller for LEDapp."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMetaObject, Qt, Q_ARG

from ..app_utils import load_app_icon
from ..ui.main_window_pyside import LEDApp_PySide
from ..services import config_service


async def attempt_auto_connect(app_instance: LEDApp_PySide):
    """Try to reconnect to the previously used device in the background."""
    if not app_instance:
        return False

    try:
        logging.info(
            "Short delay before auto-connect to allow Bluetooth stack to init..."
        )
        await asyncio.sleep(2.0)

        last_addr = config_service.get_setting("last_device_address")
        last_name = config_service.get_setting("last_device_name")
        if not last_addr or not last_name:
            logging.info(
                "Auto-connect skipped: no previously used device saved.")
            return False

        logging.info(
            "Auto-connect attempt: %s (%s)", last_name, last_addr
        )
        app_instance.selected_device = (last_name, last_addr)
        QMetaObject.invokeMethod(
            app_instance,
            "update_connection_status_gui",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, "connecting"),
        )
        future = app_instance.async_helper.run_async_task(
            app_instance.ble.connect(last_addr),
            app_instance.connect_results_signal,
            app_instance.connect_error_signal,
        )
        if not future:
            logging.error(
                "Auto-connect: failed to start connection task")
    except Exception as e:  # pragma: no cover - just in case
        logging.error(
            "Unexpected error starting auto-connect: %s", e,
            exc_info=True,
        )
        if hasattr(app_instance, "_handle_connect_error"):
            error_msg = f"Startup error: {e}"
            QMetaObject.invokeMethod(
                app_instance,
                "_handle_connect_error",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, error_msg),
            )
    finally:
        app_instance._initial_connection_attempted = True
        logging.info("_initial_connection_attempted flag set to True")

    return None


class LEDApplication:
    """Application bootstrapper encapsulating startup logic."""

    def __init__(self, argv: list[str] | None = None):
        self.argv = argv if argv is not None else sys.argv[1:]
        self.args = self._parse_args(self.argv)
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)

        icon = load_app_icon()
        if not icon.isNull():
            self.qt_app.setWindowIcon(icon)

        self.main_window = LEDApp_PySide(start_hidden=self.args.tray)
        self.main_window._is_auto_starting = self.args.tray
        if not icon.isNull():
            self.main_window.setWindowIcon(icon)

        if self.args.tray:
            logging.info("Started with --tray")
            if config_service.get_setting("auto_connect_on_startup"):
                async def delayed():
                    await asyncio.sleep(0.5)
                    await attempt_auto_connect(self.main_window)
                self.main_window.async_helper.run_async_task(delayed())
            else:
                logging.info(
                    "Auto-connect disabled by configuration.")
                self.main_window._initial_connection_attempted = True
        else:
            logging.info("Normal start")
            self.main_window._initial_connection_attempted = True
            self.main_window.show()

    @staticmethod
    def _parse_args(argv: list[str]):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--tray",
            action="store_true",
            help="Start hidden in the system tray.",
        )
        return parser.parse_args(argv)

    def run(self) -> int:
        """Start the Qt event loop."""
        return self.qt_app.exec()

