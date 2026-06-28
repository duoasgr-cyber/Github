"""Shared utility functions for the project."""
import sys
import os


def resource_path(relative_path: str) -> str:
    """Get absolute path to a resource, works for dev and for PyInstaller.

    When running as a PyInstaller bundle, resources are extracted to
    sys._MEIPASS.  In normal dev mode, resources live relative to the
    project root.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)
