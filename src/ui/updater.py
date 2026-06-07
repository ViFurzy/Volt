import os
import sys
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Optional, Callable

import requests
from PySide6.QtCore import QObject, Signal

from __version__ import __version__

# GitHub repository for auto-updates.
GITHUB_REPO = "ViFurzy/Volt"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

class UpdaterWorker(QObject):
    update_available = Signal(str, str)  # version, download_url
    no_update = Signal()
    error = Signal(str)

    def check_for_updates(self):
        """Check GitHub Releases for a newer version in a background thread."""
        def _check():
            try:
                response = requests.get(API_URL, timeout=10)
                if response.status_code != 200:
                    self.error.emit(f"Failed to check updates (HTTP {response.status_code})")
                    return
                
                data = response.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                
                if not latest_version:
                    self.error.emit("Invalid release format")
                    return
                    
                # Simple version comparison
                if latest_version != __version__ and _is_newer(latest_version, __version__):
                    assets = data.get("assets", [])
                    download_url = None
                    for asset in assets:
                        if asset.get("name", "").endswith(".exe"):
                            download_url = asset.get("browser_download_url")
                            break
                    
                    if download_url:
                        self.update_available.emit(latest_version, download_url)
                    else:
                        self.error.emit("No installer (.exe) found in the latest release")
                else:
                    self.no_update.emit()
            except Exception as e:
                self.error.emit(str(e))
                
        threading.Thread(target=_check, daemon=True).start()

    def download_and_install(self, download_url: str):
        """Download the installer and run it."""
        def _download():
            try:
                # We need a temp path that survives our process exit
                temp_dir = tempfile.gettempdir()
                installer_path = os.path.join(temp_dir, "Volt_Update.exe")
                
                response = requests.get(download_url, stream=True, timeout=30)
                response.raise_for_status()
                
                with open(installer_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                # Launch the installer
                subprocess.Popen(
                    [installer_path, "/SILENT"],
                    creationflags=subprocess.CREATE_NO_WINDOW | 0x00000008 # DETACHED_PROCESS
                )
                
                # Exit the app so installer can overwrite files
                sys.exit(0)
            except Exception as e:
                self.error.emit(f"Download failed: {str(e)}")
                
        threading.Thread(target=_download, daemon=True).start()


def _is_newer(latest: str, current: str) -> bool:
    """Very naive version check. Assumes standard semver (e.g. 1.0.1 > 1.0.0)."""
    def parse_ver(v):
        try:
            return [int(x) for x in v.split('.')]
        except ValueError:
            return [0]
    return parse_ver(latest) > parse_ver(current)
