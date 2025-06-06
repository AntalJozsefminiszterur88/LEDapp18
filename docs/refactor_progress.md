# Modular Refactor Progress

This document tracks the ongoing migration to the proposed modular package layout.

## Step 1: create `app` package

- Moved `ledapp/app.py` to `ledapp/app/main.py`.
- Added `ledapp/app/__init__.py` re-exporting `LEDApplication`.
- Adjusted relative imports inside the new module.
- Existing entry point `ledapp/main.py` continues to work.

Next steps:
- Move BLE logic under `ledapp/ble/`.
- Rename `gui/` to `ui/` and adjust imports.
