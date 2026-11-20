"""Serve Ubuntu-only collection over the USB reverse tunnel."""

import argparse
from datetime import datetime, timedelta
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from .activity import collect_draft
from .limits import ATHENS, limit_samples
from .scheduled import available_days, read_draft
from .spotify_pairing import device_grant, redeem
from .ubuntu import spotify, spotify_action, stamp, telemetry
from .web import DashboardHandler, PROJECT_ROOT, report_day


def week_data(start):
    days = []
    now = datetime.now(ATHENS).date()
    for offset in range(7):
        day = start + timedelta(days=offset)
        result = {"date": day.isoformat(), "state": "unchecked", "projects": [], "unavailable": []}
        if day <= now:
            try:
                data = collect_draft(day, PROJECT_ROOT)
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
                days.append(result)
                continue
            result.update(data, state="partial" if data["unavailable"] else "checked", collectedAt=stamp())
        days.append(result)
    return {"days": days}


class CollectorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlsplit(self.path)
        if request.path == "/health":
            DashboardHandler.send_json(self, {"collecting": True})
        elif request.path == "/week":
            try:
                start = report_day(parse_qs(request.query).get("start", [""])[0])
                if start.weekday() != 0:
                    raise ValueError
            except ValueError:
                self.send_error(400)
                return
            DashboardHandler.send_json(self, week_data(start))
        elif request.path == "/ubuntu":
            DashboardHandler.send_json(self, {"metrics": telemetry(), "spotify": spotify()})
        elif request.path == "/scheduled":
            try:
                DashboardHandler.send_json(self, {"dates": available_days()})
            except OSError:
                self.send_error(503)
        elif request.path == "/limits":
            DashboardHandler.send_json(self, list(limit_samples()))
        elif request.path in ("/draft", "/scheduled/draft"):
            try:
                day = report_day(parse_qs(request.query).get("date", [""])[0])
            except ValueError:
                self.send_error(400)
                return
            try:
                draft = read_draft(day) if request.path == "/scheduled/draft" else collect_draft(day, PROJECT_ROOT)
            except FileNotFoundError:
                self.send_error(404)
                return
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
                self.send_error(503)
                return
            DashboardHandler.send_json(self, draft)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path not in ("/spotify", "/spotify/pair"):
            self.send_error(404)
            return
        pairing = self.path == "/spotify/pair"
        grant = device_grant(self.headers.get("Authorization")) if not pairing else None
        if not pairing and grant is None:
            self.send_error(401)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 512:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError
        except (TypeError, ValueError):
            self.send_error(400)
            return
        if pairing:
            token = redeem(payload.get("ticket"))
            if token is None:
                self.send_error(410)
                return
            DashboardHandler.send_json(self, {"token": token})
            return
        if payload == {"action": "authorize"}:
            DashboardHandler.send_json(self, {"authorized": True})
            return
        if payload == {"action": "revoke"}:
            grant.unlink(missing_ok=True)
            DashboardHandler.send_json(self, {"revoked": True})
            return
        if not spotify_action(payload):
            self.send_error(409)
            return
        DashboardHandler.send_json(self, {"spotify": spotify()})

    send_content = DashboardHandler.send_content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-bind", default="192.168.1.138")
    parser.add_argument("--dashboard-url", default="http://192.168.1.238:18767")
    args = parser.parse_args()
    dashboard_url = args.dashboard_url.rstrip("/")

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(302)
            self.send_header("Location", dashboard_url + "/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    with ThreadingHTTPServer(("127.0.0.1", 18769), CollectorHandler) as collector:
        with ThreadingHTTPServer((args.legacy_bind, 8766), RedirectHandler) as legacy:
            Thread(target=legacy.serve_forever, daemon=True).start()
            collector.serve_forever()


if __name__ == "__main__":
    main()
