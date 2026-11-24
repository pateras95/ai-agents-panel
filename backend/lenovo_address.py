"""Find the current Wi-Fi dashboard address of the Lenovo tablet over USB ADB."""

import os
import re
import shutil
import subprocess
import time


ADB = os.environ.get("NEXUS_ADB") or shutil.which("adb") or "/usr/bin/adb"
PORT = 18767
FALLBACK = "192.168.1.248"
_CACHE = {"time": 0.0, "address": None}


def dashboard_base():
    """Return http://<tablet Wi-Fi IP>:18767, cached for a few seconds."""
    now = time.monotonic()
    if now - _CACHE["time"] > 10:
        address = None
        try:
            result = subprocess.run(
                [ADB, "-d", "shell", "ip -4 addr show wlan0"],
                capture_output=True, text=True, timeout=5)
            found = re.search(r"inet (\d{1,3}(?:\.\d{1,3}){3})/", result.stdout)
            address = found.group(1) if found else None
        except (OSError, subprocess.TimeoutExpired):
            pass
        _CACHE.update(time=now, address=address or _CACHE["address"])
    return f"http://{_CACHE['address'] or FALLBACK}:{PORT}"
