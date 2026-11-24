"""NEXUS AI agent for Windows: reports system data to the tablet and runs the launcher items you allow.

Runs from the zip the tablet serves (embedded Python, no installation). Files next to it:
  config.json    tablet address and private token (created by the tablet when you download the zip)
  launcher.json  the programs, folders and links the tablet may open; edit it to add your own
The tablet never sends a path or a command line: it only sends the id of an item listed in launcher.json.
"""

import concurrent.futures
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from . import windows_system

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
LAUNCHER = ROOT / "launcher.json"
PORT = 18767
INTERVAL = 2.0
ICONS = {"spotify", "chrome", "folder", "steam", "epic", "discord", "terminal", "monitor", "generic"}


def first_existing(*paths):
    for path in paths:
        expanded = os.path.expandvars(path)
        if os.path.exists(expanded):
            return expanded
    return None


def default_items():
    home = Path.home()
    items = [
        {"id": "spotify", "label": "Spotify", "icon": "spotify", "open": "spotify:"},
        {"id": "explorer", "label": "Εξερεύνηση", "icon": "folder", "open": "shell:MyComputerFolder"},
        {"id": "downloads", "label": "Λήψεις", "icon": "folder", "open": str(home / "Downloads")},
        {"id": "documents", "label": "Έγγραφα", "icon": "folder", "open": str(home / "Documents")},
        {"id": "steam", "label": "Steam", "icon": "steam", "open": "steam://open/main"},
        {"id": "epic", "label": "Epic Games", "icon": "epic", "open": "com.epicgames.launcher://apps"},
        {"id": "discord", "label": "Discord", "icon": "discord", "open": "discord://"},
        {"id": "terminal", "label": "Terminal", "icon": "terminal", "run": ["cmd.exe", "/c", "start", "", "wt.exe"]},
        {"id": "taskmgr", "label": "Διαχείριση εργασιών", "icon": "monitor", "run": ["taskmgr.exe"]},
    ]
    chrome = first_existing(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                            r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
    if chrome:
        items.insert(1, {"id": "chrome", "label": "Chrome", "icon": "chrome", "run": [chrome]})
    return items


def load_items():
    """launcher.json is created on first start. Only "open" (file, folder, link) and "run" (program) are understood."""
    if not LAUNCHER.exists():
        LAUNCHER.write_text(json.dumps({"items": default_items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        entries = json.loads(LAUNCHER.read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    items = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("label"), str) \
                and (isinstance(entry.get("open"), str) or (isinstance(entry.get("run"), list) and entry["run"])):
            items[entry["id"]] = entry
    return items


def public_items(items):
    return [{"id": key, "label": item["label"], "icon": item.get("icon") if item.get("icon") in ICONS else "generic"}
            for key, item in items.items()]


def launch(item):
    if isinstance(item.get("open"), str):
        os.startfile(os.path.expandvars(item["open"]))  # noqa: S606 (Windows only, allowlisted item)
    else:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([os.path.expandvars(str(part)) for part in item["run"]], creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def post(url, token, payload):
    request = Request(url, data=json.dumps(payload).encode(), method="POST",
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urlopen(request, timeout=6) as response:
        return json.load(response)


def local_prefix():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("192.0.2.1", 9))  # no packet is sent; this only selects the network card
        return probe.getsockname()[0].rsplit(".", 1)[0]


def find_tablet():
    """The tablet's address changes with DHCP: look for the NEXUS backend on this network."""
    def check(host):
        try:
            with urlopen(f"http://{host}:{PORT}/api/status", timeout=.7) as response:
                return host if json.load(response).get("backend") is True else None
        except (OSError, ValueError):
            return None
    prefix = local_prefix()
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        for found in pool.map(check, [f"{prefix}.{n}" for n in range(1, 255)]):
            if found:
                return f"http://{found}:{PORT}"
    return None


def run_command(command, items):
    kind = command.get("type")
    try:
        if kind == "launch" and command.get("id") in items:
            launch(items[command["id"]])
        elif kind == "spotify":
            windows_system.spotify_action({key: command.get(key) for key in ("action", "value") if key in command})
    except (OSError, ValueError, TypeError) as error:
        print("Command failed:", error, flush=True)


def main():
    if sys.stdout is None or sys.stderr is None:  # started with pythonw: keep messages in a log file instead
        log = open(ROOT / "agent.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        tablet, token = config["tablet"].rstrip("/"), config["token"]
    except (OSError, ValueError, KeyError):
        sys.exit("Λείπει το config.json. Κατέβασε ξανά το agent από το tablet.")
    print("NEXUS AI agent · tablet:", tablet, flush=True)
    items = load_items()
    loaded = LAUNCHER.stat().st_mtime
    while True:
        started = time.monotonic()
        try:
            if LAUNCHER.stat().st_mtime != loaded:
                loaded, items = LAUNCHER.stat().st_mtime, load_items()
            answer = post(tablet + "/api/agent/report", token, {
                "metrics": windows_system.telemetry(), "spotify": windows_system.spotify(), "launcher": public_items(items)})
            for command in answer.get("commands", []):
                run_command(command, items)
        except OSError as error:
            if getattr(error, "code", None) in (401, 403):
                sys.exit("Το tablet απέρριψε τον κωδικό. Κατέβασε ξανά το agent από το tablet.")
            found = find_tablet()
            if found:
                tablet = found
                CONFIG.write_text(json.dumps({"tablet": tablet, "token": token}, indent=2), encoding="utf-8")
            else:
                time.sleep(8)
        time.sleep(max(0.2, INTERVAL - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
