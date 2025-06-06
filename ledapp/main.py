"""Entry point for the LED application."""

import logging
from .app import LEDApplication

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s - %(module)s @ %(asctime)s]: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


def main(argv=None):
    app = LEDApplication(argv)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
