# Modular Refactor Progress

This document tracks the ongoing migration to the proposed modular package layout.

## Step 1: create `app` package

- Moved `ledapp/app.py` to `ledapp/app/main.py`.
- Added `ledapp/app/__init__.py` re-exporting `LEDApplication`.
- Adjusted relative imports inside the new module.
- Existing entry point `ledapp/main.py` continues to work.

## Step 2: move BLE logic and rename UI package

- Moved `ledapp/services/ble_service.py` to `ledapp/ble/service.py`.
- Added `ledapp/ble/__init__.py` exposing `BLEService`.
- Renamed `ledapp/gui` to `ledapp/ui` and updated imports.

Next steps:
- Extract configuration module into `ledapp/config/` package.
