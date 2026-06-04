"""Settings persistence and startup registration for PeriphWatcher.

Responsibilities:
- JSON config at %APPDATA%\\PeriphWatcher\\config.json (SYS-02)
- HKCU Run key startup registration via winreg (SYS-01)
- Battery threshold colour mapping (D-01)

No Qt imports here — pure stdlib so tests run headlessly.
"""
import json
import os
import sys
import winreg
from pathlib import Path

# ---------------------------------------------------------------------------
# Config constants
# ---------------------------------------------------------------------------

CONFIG_DIR: Path = Path(os.environ["APPDATA"]) / "PeriphWatcher"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"

_DEFAULTS: dict = {"launch_at_startup": False, "thresholds": {}, "close_behavior": None}

# ---------------------------------------------------------------------------
# winreg constants
# ---------------------------------------------------------------------------

RUN_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME: str = "PeriphWatcher"


# ---------------------------------------------------------------------------
# JSON config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Return the persisted settings, merged over defaults.

    Falls back to defaults if the file is absent or malformed.
    The merge pattern ({**_DEFAULTS, **data}) ensures Phase 6 can add new keys
    without breaking Phase 4 reads — unknown keys survive, missing keys are filled.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        with CONFIG_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_config(config: dict) -> None:
    """Persist config to disk, creating the directory if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Battery threshold colour mapping (D-01)
# ---------------------------------------------------------------------------

def battery_color(percent: int | None) -> str:
    """Return a QSS hex color string for the given battery percentage.

    Thresholds per D-01:
      None / offline -> grey
      <= 8%          -> critical red
      <= 45%         -> warning amber
      > 45%          -> normal teal
    """
    if percent is None:
        return "#888888"  # offline / unknown
    if percent <= 8:
        return "#E50000"  # critical
    if percent <= 45:
        return "#E5A300"  # warning
    return "#4FC3F7"      # normal


# ---------------------------------------------------------------------------
# winreg startup registration (SYS-01)
# ---------------------------------------------------------------------------

def _get_exe_path() -> str:
    """Return the launch command wrapped in outer double-quotes.

    In dev mode (python.exe): includes '-m src' so Windows actually launches
    the app at login. In packaged mode (Phase 7), sys.executable IS the app
    exe and no extra args are needed.
    Quoting is required so Windows handles paths with spaces correctly (Pitfall 4).
    """
    exe = sys.executable
    if exe.lower().endswith("python.exe") or exe.lower().endswith("python3.exe"):
        # Dev mode — must include the module argument
        import os
        src_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(src_dir)
        return f'"{exe}" -m src'
    # Packaged exe — path only
    return f'"{exe}"'


def set_startup(enabled: bool) -> None:
    """Write or remove the HKCU Run key entry for PeriphWatcher.

    Writing to HKCU (current user) requires no admin rights.
    set_startup(False) is idempotent — swallows FileNotFoundError if the value
    was not present.
    """
    if enabled:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                access=winreg.KEY_WRITE,
            ) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
        except OSError:
            pass  # registry write failed — UI checkbox state and registry may diverge
    else:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                access=winreg.KEY_WRITE,
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass  # value did not exist — idempotent, no action needed


def is_startup_enabled() -> bool:
    """Return True if the HKCU Run key entry for PeriphWatcher exists."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
