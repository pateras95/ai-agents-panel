"""Tablet side of the Windows agent: pairing, reports from the agent and the commands queued for it.

The agent on Windows is a zip downloaded from the tablet (see scripts/build_windows_agent.py). It reports telemetry
every couple of seconds and receives commands in the answer. Commands are only ids of items the agent itself listed
(its own allowlist), plus allowlisted Spotify actions, so the tablet never sends a program path or command line.
"""

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from tempfile import NamedTemporaryFile
from threading import Lock
import time
import zipfile

FRESH_SECONDS = 15
TICKET_SECONDS = 600
ITEM_ID = re.compile(r"[a-z0-9_-]{1,32}")
ICONS = {"spotify", "chrome", "folder", "steam", "epic", "discord", "terminal", "monitor", "generic"}
SPOTIFY_ACTIONS = {"play", "pause", "next", "previous", "volume"}


class AgentHub:
    def __init__(self, root):
        self.directory = Path(root) / "windows-agent"
        self.package = self.directory / "nexus-windows-agent.zip"
        self.token_file = self.directory / "token.sha256"
        self.lock = Lock()
        self.report = None
        self.reported_at = 0.0
        self.queue = []
        self.tickets = {}

    # ---- state
    @property
    def has_package(self):
        return self.package.is_file()

    def fresh(self):
        return self.report is not None and time.monotonic() - self.reported_at < FRESH_SECONDS

    def status(self):
        with self.lock:
            fresh = self.fresh()
            return {"connected": fresh, "os": "windows" if fresh else None, "package": self.has_package,
                    "launcher": self.report["launcher"] if fresh else []}

    def system(self):
        with self.lock:
            return {"metrics": self.report["metrics"], "spotify": self.report["spotify"]} if self.fresh() else None

    # ---- pairing and download
    def new_ticket(self):
        now = time.monotonic()
        with self.lock:
            self.tickets = {ticket: end for ticket, end in self.tickets.items() if end > now}
            ticket = secrets.token_urlsafe(6)
            self.tickets[ticket] = now + TICKET_SECONDS
        return ticket

    def build_download(self, ticket, tablet_url):
        """Return a temporary zip that contains the agent and its private config, or None for a bad ticket."""
        with self.lock:
            end = self.tickets.pop(ticket, 0)
            if end <= time.monotonic() or not self.has_package:
                return None
            token = secrets.token_urlsafe(32)
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.token_file.write_text(hashlib.sha256(token.encode()).hexdigest())
        temporary = NamedTemporaryFile(dir=self.directory, suffix=".zip", delete=False)
        temporary.close()
        shutil.copyfile(self.package, temporary.name)
        with zipfile.ZipFile(temporary.name, "a", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("nexus-windows-agent/config.json", json.dumps({"tablet": tablet_url, "token": token}, indent=2))
        return Path(temporary.name)

    # ---- agent traffic
    def authorized(self, header):
        if not isinstance(header, str) or not header.startswith("Bearer ") or len(header) > 100:
            return False
        try:
            expected = self.token_file.read_text().strip()
        except OSError:
            return False
        return hmac.compare_digest(hashlib.sha256(header[7:].encode()).hexdigest(), expected)

    @staticmethod
    def clean_launcher(items):
        result = []
        for item in items[:24] if isinstance(items, list) else []:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not ITEM_ID.fullmatch(item["id"]):
                continue
            label = item.get("label")
            if not isinstance(label, str) or not label.strip():
                continue
            result.append({"id": item["id"], "label": label.strip()[:40],
                           "icon": item.get("icon") if item.get("icon") in ICONS else "generic"})
        return result

    def accept(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("metrics"), dict) or not isinstance(payload.get("spotify"), dict):
            raise ValueError("Invalid report")
        spotify = payload["spotify"]
        art = spotify.get("artwork")
        if art is not None and not (isinstance(art, str) and (art.startswith("data:image/") or art.startswith("https://i.scdn.co/"))):
            spotify = {**spotify, "artwork": None}
        with self.lock:
            self.report = {"metrics": payload["metrics"], "spotify": spotify,
                           "launcher": self.clean_launcher(payload.get("launcher"))}
            self.reported_at = time.monotonic()
            commands, self.queue = self.queue, []
        return commands

    # ---- commands from the dashboard
    def enqueue_launch(self, item_id):
        with self.lock:
            if not self.fresh() or not any(item["id"] == item_id for item in self.report["launcher"]) or len(self.queue) >= 20:
                return False
            self.queue.append({"type": "launch", "id": item_id})
            return True

    def enqueue_spotify(self, payload):
        action = payload.get("action") if isinstance(payload, dict) else None
        if action not in SPOTIFY_ACTIONS:
            return False
        command = {"type": "spotify", "action": action}
        if action == "volume":
            value = payload.get("value")
            if type(value) not in (int, float) or not 0 <= value <= 100:
                return False
            command["value"] = value
        with self.lock:
            if not self.fresh() or len(self.queue) >= 20:
                return False
            self.queue.append(command)
            return True
