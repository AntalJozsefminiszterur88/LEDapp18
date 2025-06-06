import os
import sys
import logging # Import the logging module
from PySide6.QtGui import QIcon

def load_app_icon(icon_name="led_icon.ico"):
    """Loads the application icon.

    Args:
        icon_name: The name of the icon file.

    Returns:
        A QIcon object.
    """
    # Check if running as a frozen executable
    if getattr(sys, 'frozen', False):
        # If frozen, look for the icon in the executable's directory
        executable_dir = os.path.dirname(sys.executable)
        icon_path = os.path.join(executable_dir, icon_name)
        logging.debug(f"Frozen executable. Trying to load icon from {icon_path}")
    else:
        # If not frozen, look for the icon in the current working directory
        # or a specified relative path
        icon_path = icon_name
        logging.debug(f"Not a frozen executable. Trying to load icon from {icon_path}")

    if os.path.exists(icon_path):
        logging.debug(f"Icon found at {icon_path}")
        return QIcon(icon_path)
    else:
        logging.debug(f"Icon not found at {icon_path}")
        # Fallback: try to find icon in <executable_dir>/../_internal if frozen
        if getattr(sys, 'frozen', False):
            fallback_path = os.path.join(os.path.dirname(sys.executable), "..", "_internal", icon_name)
            logging.debug(f"Frozen executable. Trying fallback icon path {fallback_path}")
            if os.path.exists(fallback_path):
                logging.debug(f"Icon found at {fallback_path}")
                return QIcon(fallback_path)
            else:
                logging.debug(f"Icon not found at {fallback_path}")
        
        # If still not found, try the base directory as a last resort for non-frozen.
        # For frozen, this might be redundant if icon_name was already a relative path.
        if not getattr(sys, 'frozen', False):
            base_dir_path = os.path.join(os.path.dirname(__file__), icon_name)
            logging.debug(f"Trying to load icon from base directory {base_dir_path}")
            if os.path.exists(base_dir_path):
                logging.debug(f"Icon found at {base_dir_path}")
                return QIcon(base_dir_path)
            else:
                logging.debug(f"Icon not found at {base_dir_path}")
        
        logging.debug("Returning empty QIcon.")
        return QIcon() # Return an empty QIcon if not found
