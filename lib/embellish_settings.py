"""Settings persistence for the LLM embellishment feature.

Stores API keys, model selection, tone, and scope preferences in an
OS-appropriate config file (not in the project directory).
"""

import json
import os
import platform


def settings_dir():
    """Return the OS-appropriate config directory for Caverns of Carl."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "CavernsOfCarl")
    elif system == "Darwin":
        return os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Application Support",
            "CavernsOfCarl",
        )
    else:
        base = os.environ.get(
            "XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")
        )
        return os.path.join(base, "caverns-of-carl")


def settings_path():
    """Return the full path to the settings JSON file."""
    return os.path.join(settings_dir(), "settings.json")


_DEFAULTS = {
    "provider": "Anthropic",
    "model": "claude-sonnet-4-5-20250929",
    "api_key": "",
    "tone": "Classic D&D",
    "custom_tone": "",
    "scope_rooms": True,
    "scope_corridors": True,
    "scope_traps": True,
    "scope_books": True,
}


def load_settings():
    """Load settings from disk, filling in defaults for missing keys."""
    settings = dict(_DEFAULTS)
    path = settings_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                settings.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(settings):
    """Persist settings to disk, creating the directory if needed."""
    path = settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
