# Proposed Modular Structure for LEDapp

This document outlines a potential modular restructuring of the project. The goal is to
improve code readability and maintainability and to separate responsibilities.

## Proposed Package Layout

```
ledapp/
├── app/          # Application startup and high level controllers
│   ├── __init__.py
│   └── main.py   # Creates QApplication and boots modules
├── ble/          # Bluetooth communication layer
│   ├── __init__.py
│   └── service.py
├── config/       # Configuration and persistence logic
│   ├── __init__.py
│   └── service.py
├── schedule/     # Scheduling, sunrise/sunset logic
│   ├── __init__.py
│   └── manager.py
├── ui/           # GUI components (PySide windows, dialogs)
│   ├── __init__.py
│   ├── main_window.py
│   └── widgets/
├── util/         # Generic helper utilities
│   ├── __init__.py
│   └── async_helper.py
└── services/     # Cross‑cutting services (facades to the other modules)
    ├── __init__.py
    └── ble_facade.py
```

## Rationale

- **Separation of concerns** – business logic, BLE communication, and GUI
  elements live in separate packages.
- **Better testability** – the services expose clean interfaces that can be
  mocked or replaced in unit tests.
- **Extensibility** – additional communication methods or UI frameworks can be
  integrated without touching the core logic.

## Migration

1. Move existing files to the packages above.
2. Update imports accordingly.
3. Provide thin facade classes under `services/` that translate between the UI
   and the underlying modules.

This is only a draft. The exact naming and hierarchy can be adjusted as the
codebase evolves.
