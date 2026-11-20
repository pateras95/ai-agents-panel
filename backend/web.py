#!/usr/bin/env python3
"""Serve the NEXUS AI usage dashboard on the Ubuntu host."""

import argparse
from datetime import date, datetime
import os
import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from .activity import collect_draft

from .limits import ATHENS, limit_samples
from .reports import read_reports, report_version, save_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
DATA_ROOT = Path(os.environ.get("NEXUS_DATA_DIR") or Path.home() / ".local" / "share" / "nexus-ai").resolve()
REPORTS_DIRECTORY = DATA_ROOT / "reports"
REPORT_LOCK = Lock()
ASSET_PATH = re.compile(r"/assets/[a-zA-Z0-9_-]+\.(?:js|css)")


def dashboard_data():
    return {
        "limits": list(limit_samples()),
        "reports": [
            {"date": day.isoformat(),
             "sections": [{"label": label, "items": items} for label, items in sections]}
            for day, sections in read_reports(REPORTS_DIRECTORY)
        ],
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def do_GET(self):
        request = urlsplit(self.path)
        path = request.path
        if path == "/api/draft":
            try:
                day = report_day(parse_qs(request.query).get("date", [""])[0])
            except ValueError:
                self.send_error(400, "Invalid date")
                return
            try:
                draft = collect_draft(day, PROJECT_ROOT, DATA_ROOT)
            except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError):
                self.send_error(503, "Git unavailable")
                return
            draft["version"] = report_version(REPORTS_DIRECTORY, day)
            self.send_json(draft)
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

    def do_POST(self):
        if self.path != "/api/reports":
            self.send_error(404)
            return
        host, port = self.server.server_address
        if self.headers.get("Origin") != f"http://{host}:{port}":
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
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)


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
        print(f"http://{args.bind}:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
