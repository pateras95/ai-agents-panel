#!/usr/bin/env python3
"""Serve the NEXUS AI usage dashboard on the Ubuntu host."""

import argparse
from datetime import date, datetime
import os
import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address, ip_network
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from .activity import collect_draft

from .limits import ATHENS, UNAVAILABLE, WINDOWS, limit_samples
from .network_status import configured_monitor
from .reports import read_reports, report_version, save_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
DATA_ROOT = Path(os.environ.get("NEXUS_DATA_DIR") or Path.home() / ".local" / "share" / "nexus-ai").resolve()
REPORTS_DIRECTORY = DATA_ROOT / "reports"
REPORT_LOCK = Lock()
COLLECTOR_URL = os.environ.get("NEXUS_COLLECTOR_URL", "").rstrip("/")
STARTED = datetime.now(ATHENS).isoformat(timespec="seconds")
SPOTIFY_LAN = ip_network(os.environ.get("NEXUS_SPOTIFY_LAN", "192.168.1.0/24"))


def collector_data(path, timeout=20, *, body=None, authorization=None):
    request = Request(COLLECTOR_URL + path, data=body)
    if authorization:
        request.add_header("Authorization", authorization)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def dashboard_limits():
    if not COLLECTOR_URL:
        return list(limit_samples())
    try:
        return collector_data("/limits")
    except (OSError, ValueError):
        return [
            dict(tool=tool, window=window, remaining=UNAVAILABLE, reset=UNAVAILABLE, updated=UNAVAILABLE)
            for tool in ("Claude Code", "Codex") for window, _, _ in WINDOWS
        ]
ASSET_PATH = re.compile(r"/assets/[a-zA-Z0-9_-]+\.(?:js|css)")


def report_history():
    with REPORT_LOCK:
        return [
            {
                "date": day.isoformat(),
                "version": report_version(REPORTS_DIRECTORY, day),
                "sections": [{"label": label, "items": items} for label, items in sections],
            }
            for day, sections in read_reports(REPORTS_DIRECTORY)
        ]


def dashboard_data():
    return {"limits": dashboard_limits(), "reports": report_history()}


class DashboardHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def do_GET(self):
        request = urlsplit(self.path)
        path = request.path
        if path == "/api/network":
            if self.server.network_monitor is None:
                self.send_error(503, "Network monitor unavailable")
                return
            self.send_json(self.server.network_monitor.snapshot())
            return
        if path in ("/api/week", "/api/ubuntu"):
            if not COLLECTOR_URL:
                self.send_error(503, "Ubuntu collector unavailable")
                return
            upstream = "/ubuntu"
            if path == "/api/week":
                try:
                    start = report_day(parse_qs(request.query).get("start", [""])[0])
                    if start.weekday() != 0:
                        raise ValueError
                except ValueError:
                    self.send_error(400, "Invalid week")
                    return
                upstream = "/week?start=" + start.isoformat()
            try:
                self.send_json(collector_data(upstream, timeout=20))
            except (OSError, ValueError):
                self.send_error(503, "Ubuntu collector unavailable")
            return
        if path == "/api/status":
            collector = False
            if COLLECTOR_URL:
                try:
                    collector = collector_data("/health", timeout=2).get("collecting") is True
                except (OSError, ValueError):
                    pass
            self.send_json({
                "backend": True, "collector": collector, "started": STARTED,
                "reports": sum(1 for _ in REPORTS_DIRECTORY.glob("????-??-??.json")),
            })
            return
        if path == "/api/scheduled":
            if not COLLECTOR_URL:
                self.send_json({"dates": []})
                return
            try:
                dates = collector_data("/scheduled", timeout=3)["dates"]
            except (OSError, ValueError, KeyError):
                self.send_error(503)
                return
            with REPORT_LOCK:
                pending = [day for day in dates
                           if report_version(REPORTS_DIRECTORY, day) is None
                           and not reviewed_path(day).exists()]
            self.send_json({"dates": pending})
            return
        if path in ("/api/draft", "/api/scheduled/draft"):
            try:
                day = report_day(parse_qs(request.query).get("date", [""])[0])
            except ValueError:
                self.send_error(400, "Invalid date")
                return
            scheduled = path == "/api/scheduled/draft"
            if scheduled and (not COLLECTOR_URL
                              or report_version(REPORTS_DIRECTORY, day) is not None
                              or reviewed_path(day).exists()):
                self.send_error(404)
                return
            try:
                upstream = "/scheduled/draft" if scheduled else "/draft"
                draft = (
                    collector_data(upstream + "?date=" + day.isoformat())
                    if COLLECTOR_URL else collect_draft(day, PROJECT_ROOT)
                )
            except HTTPError as error:
                self.send_error(404 if error.code == 404 else 503, "Draft unavailable")
                return
            except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError):
                self.send_error(503, "Git unavailable")
                return
            draft["version"] = report_version(REPORTS_DIRECTORY, day)
            self.send_json(draft)
            return
        if path == "/api/reports":
            self.send_json({"reports": report_history()})
            return
        if path == "/api/limits":
            self.send_json({"limits": dashboard_limits()})
            return
        if path == "/api/dashboard":
            self.send_json(dashboard_data())
            return

        if path == "/":
            file = FRONTEND_DIST / "index.html"
            content_type = "text/html; charset=utf-8"
        elif ASSET_PATH.fullmatch(path):
            file = FRONTEND_DIST / path.lstrip("/")
            content_type = "text/css" if file.suffix == ".css" else "text/javascript"
        else:
            self.send_error(404)
            return

        try:
            body = file.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_content(body, content_type, asset=path.startswith("/assets/"))

    def do_DELETE(self):
        if self.path == "/api/network/devices":
            self.update_known_device(delete=True)
            return
        if self.path != "/api/reports":
            self.send_error(404)
            return
        if not self.is_same_origin():
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 512:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            day = report_day(payload["date"])
            version = payload["version"]
            if payload.get("approved") is not True or not isinstance(version, str):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            self.send_error(400, "Invalid deletion")
            return
        with REPORT_LOCK:
            current = report_version(REPORTS_DIRECTORY, day)
            if current is None:
                self.send_error(404, "Report not found")
                return
            if current != version:
                self.send_error(409, "Report changed")
                return
            reviewed_path(day).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            reviewed_path(day).touch()
            (REPORTS_DIRECTORY / f"{day}.json").unlink()
        self.send_json({"date": day.isoformat()})

    def is_same_origin(self):
        host, port = self.server.server_address
        return self.headers.get("Origin") == f"http://{host}:{port}"

    def post_spotify(self):
        if not self.is_same_origin() or IPv4Address(self.client_address[0]) not in SPOTIFY_LAN:
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        authorization = self.headers.get("Authorization")
        pairing = self.path == "/api/spotify/pair"
        if not pairing and (not authorization or len(authorization) > 100):
            self.send_error(401)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 512:
                raise ValueError
        except ValueError:
            self.send_error(400)
            return
        if not COLLECTOR_URL:
            self.send_error(503)
            return
        try:
            upstream = "/spotify/pair" if pairing else "/spotify"
            self.send_json(collector_data(upstream, timeout=12, body=self.rfile.read(size),
                                          authorization=None if pairing else authorization))
        except HTTPError as error:
            self.send_error(error.code if error.code in (400, 401, 409, 410) else 503)
        except (OSError, ValueError):
            self.send_error(503)

    def update_known_device(self, *, delete=False):
        monitor = self.server.network_monitor
        if monitor is None:
            self.send_error(503)
            return
        if not self.is_same_origin() or IPv4Address(self.client_address[0]) not in monitor.lan:
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 512:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            fields = ("ip",) if delete else ("ip", "name", "kind")
            if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) for key in fields):
                raise ValueError
            if delete:
                monitor.delete(payload["ip"])
            else:
                device = monitor.save(payload)
        except (TypeError, ValueError, KeyError):
            self.send_error(400, "Invalid known device")
            return
        except OSError:
            self.send_error(503)
            return
        self.send_json({"deleted": True} if delete else {"device": device})

    def do_POST(self):
        if self.path == "/api/network/devices":
            self.update_known_device()
            return
        if self.path in ("/api/spotify", "/api/spotify/pair"):
            self.post_spotify()
            return
        if self.path != "/api/reports":
            self.send_error(404)
            return
        if not self.is_same_origin():
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 24000:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            day = report_day(payload["date"])
            if payload.get("approved") is not True or "version" not in payload:
                raise ValueError
            sections = {}
            for field in ("completed", "next", "blockers"):
                items = payload.get(field, [])
                if not isinstance(items, list) or len(items) > 30:
                    raise ValueError
                if any(not isinstance(item, str) or not item.strip() or len(item) > 600 for item in items):
                    raise ValueError
                if items:
                    sections[field] = items
            if not sections.get("completed"):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            self.send_error(400, "Invalid report")
            return
        with REPORT_LOCK:
            if report_version(REPORTS_DIRECTORY, day) != payload["version"]:
                self.send_error(409, "Report changed")
                return
            save_report(REPORTS_DIRECTORY, day, sections)
        self.send_json({"date": day.isoformat()})

    def send_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_content(body, "application/json; charset=utf-8")

    def send_content(self, body, content_type, *, asset=False):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=31536000, immutable" if asset else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https://i.scdn.co; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)


def reviewed_path(day):
    return DATA_ROOT / "reviewed" / f"{day}.done"


def report_day(value):
    day = date.fromisoformat(value)
    if day.isoformat() != value or day > datetime.now(ATHENS).date():
        raise ValueError
    return day


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", type=IPv4Address, default="127.0.0.1",
                        help="IPv4 address of the Ubuntu interface to listen on.")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if args.bind.is_unspecified:
        parser.error("--bind requires a specific interface address")

    if not (FRONTEND_DIST / "index.html").is_file():
        parser.error("build the dashboard with npm --prefix frontend run build")

    if REPORTS_DIRECTORY.is_relative_to(PROJECT_ROOT):
        parser.error("NEXUS_DATA_DIR must be outside the checkout")
    REPORTS_DIRECTORY.mkdir(parents=True, mode=0o700, exist_ok=True)

    with ThreadingHTTPServer((str(args.bind), args.port), DashboardHandler) as server:
        server.network_monitor = configured_monitor(DATA_ROOT, args.bind)
        print(f"http://{args.bind}:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
