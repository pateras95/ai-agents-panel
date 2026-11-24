#!/usr/bin/env python3
"""Serve the built dashboard with synthetic data, for screenshots and trying the UI.

No real repositories, devices, accounts or media are read: every API answer is generated here.
Usage: python3 scripts/demo_server.py [--port 8790]   (run `npm --prefix frontend run build` first)
"""

import argparse
import base64
from datetime import date, datetime, timedelta, timezone
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
TZ = timezone(timedelta(hours=2))
CATEGORIES = {"Shop Backend": "mpass", "Admin Portal": "mpass", "Mobile Kiosk": "mpass", "Side Project": "personal"}
WORK = {
    0: [("Shop Backend", "Ολοκλήρωσα τη νέα διαδικασία πληρωμής και τη σύνδεση με την υπηρεσία ειδοποιήσεων."),
        ("Admin Portal", "Πρόσθεσα φίλτρα και σελιδοποίηση στη λίστα χρηστών.")],
    1: [("Mobile Kiosk", "Διόρθωσα το πρόβλημα στην οθόνη αναμονής και ενημέρωσα τις μεταφράσεις."),
        ("Side Project", "Έφτιαξα την αρχική σελίδα και πρόσθεσα σκούρο θέμα.")],
    2: [("Admin Portal", "Αναβάθμισα την εφαρμογή σε Vue 3 και βελτίωσα τα μηνύματα σφάλματος."),
        ("Shop Backend", "Διόρθωσα τη ρύθμιση του build και ανανέωσα την έκδοση του Node.js.")],
}


def monday(day):
    return day - timedelta(days=day.weekday())


def athens_today():
    return datetime.now(TZ).date()


def rows_for(day):
    return WORK.get(day.weekday() % 3 if day.weekday() < 5 else 0, [])


def project(name, text, day):
    return {"name": name, "category": CATEGORIES[name], "summary": text,
            "commits": [{"sha": "a1b2c3d", "subject": "demo commit", "merge": False}],
            "branches": ["main"], "pushes": [], "source": "Δεδομένα επίδειξης (συνθετικά)."}


def week_data(start):
    today = athens_today()
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        projects = [project(n, t, day) for n, t in rows_for(day)] if day <= today and day.weekday() < 5 else []
        days.append({"date": day.isoformat(), "state": "checked" if day <= today else "unchecked", "projects": projects,
                     "unavailable": [], "categories": CATEGORIES})
    return {"days": days}


def reports():
    today = athens_today()
    out = []
    for back in range(1, 14):
        day = today - timedelta(days=back)
        if day.weekday() >= 5 or day > today:
            continue
        lines = [f"{n}: {t}" for n, t in rows_for(day)]
        out.append({"date": day.isoformat(), "version": "demo", "sections": [
            {"label": "Ολοκληρώθηκαν", "items": lines}, {"label": "Επόμενα βήματα", "items": []}, {"label": "Εμπόδια", "items": []}]})
    return out


def svg(color_a, color_b, label=""):
    markup = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 90"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
              f'<stop offset="0" stop-color="{color_a}"/><stop offset="1" stop-color="{color_b}"/></linearGradient></defs>'
              f'<rect width="160" height="90" fill="url(#g)"/><text x="80" y="52" font-size="16" fill="#fff" text-anchor="middle" '
              f'font-family="sans-serif" font-weight="700">{label}</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(markup.encode()).decode()


def limits():
    stamp = datetime.now(TZ).strftime("%d/%m/%Y %H:%M EET")
    tomorrow = (datetime.now(TZ) + timedelta(days=1)).strftime("%d/%m/%Y 05:00 EET")
    soon = (datetime.now(TZ) + timedelta(hours=3)).strftime("%d/%m/%Y %H:%M EET")
    week = (datetime.now(TZ) + timedelta(days=4)).strftime("%d/%m/%Y 22:00 EET")
    rows = (("Claude Code", "5ωρο", "68%", soon), ("Claude Code", "7 ημέρες", "91%", tomorrow),
            ("Codex", "5ωρο", "96%", soon), ("Codex", "7 ημέρες", "74%", week))
    return {"limits": [{"tool": t, "window": w, "remaining": r, "reset": z, "updated": stamp} for t, w, r, z in rows]}


def ubuntu():
    now = datetime.now(TZ).isoformat(timespec="seconds")
    sensor = lambda device, name, value: {"device": device, "sensor": name, "value": value, "unit": "°C", "sampledAt": now}
    return {"metrics": {
        "cpu": {"value": 14.0, "unit": "%", "sampledAt": now},
        "gpu": {"value": 22.0, "unit": "%", "sampledAt": now, "device": "Demo GPU"},
        "ram": {"value": 41.0, "unit": "%", "sampledAt": now, "usedGiB": 13.1, "totalGiB": 32.0},
        "temperatures": [sensor("Demo CPU", "Package id 0", 46.0), sensor("Demo GPU", "GPU", 38.0), sensor("nvme", "Composite", 31.0)]},
        "spotify": {"state": "playing", "title": "Midnight Drive", "artist": "Demo Artist", "volume": 62, "sampledAt": now,
                    "artwork": svg("#3b2a6d", "#d9696a", "♫"), "actions": ["previous", "pause", "next", "volume"]}}


def network():
    now = datetime.now(TZ).isoformat(timespec="seconds")
    devices = [("Router", "router", True), ("Living room TV", "tv", True), ("Kitchen speaker", "speaker", True),
               ("Front door camera", "camera", True), ("Robot vacuum", "vacuum", False), ("Work laptop", "computer", True),
               ("Phone", "phone", True), ("Printer", "printer", False), ("Αυτό το tablet", "tablet", True)]
    return {"source": "discovered", "router": {"available": True, "checkedAt": now, "lastSuccess": now, "address": "192.168.1.1"},
            "internet": {"available": True, "checkedAt": now, "lastSuccess": now},
            "devices": [{"ip": f"192.168.1.{10 + i}", "name": name, "kind": kind, "available": up, "lastSeen": now,
                         "connection": None, "discovered": False, "guessed": False, **({"fixed": True} if kind in ("router", "tablet") else {})}
                        for i, (name, kind, up) in enumerate(devices)]}


def youtube():
    names = ["Weekend trip highlights", "How I set up my workshop", "Quick tips for beginners", "Gear review after one year",
             "Behind the scenes", "Q&A special", "Short: favourite place", "Short: 30 second tip", "Short: before and after"]
    colors = [("#3b6fb6", "#1f3a63"), ("#4b9a73", "#1d4a37"), ("#c9953a", "#6b4a14"), ("#8a6ad0", "#3b2a6d")]
    videos = []
    for i, name in enumerate(names):
        short = name.startswith("Short")
        videos.append({"id": f"demo{i:07d}"[:11].ljust(11, "x"), "title": name, "format": "short" if short else "long",
                       "published": (datetime.now(TZ) - timedelta(days=3 + i * 4)).isoformat(),
                       "thumbnail": svg(*colors[i % 4], "▶"), "impressions": 9000 - i * 700, "ctr": 4.1 + (i % 4) * .8,
                       "average": 22 + i * 3.1, "hours": 41.5 - i * 3, "subscribers": 6 - i // 2})
    today = athens_today()
    return {"status": "connected", "channel": {"title": "Demo Channel"}, "cloudProject": "", "warnings": [],
            "period": {"start": (today - timedelta(days=30)).isoformat(), "end": today.isoformat(), "reachDays": 29}, "videos": videos}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        path = url.path
        today = athens_today()
        if path == "/api/limits":
            return self.send_json(limits())
        if path == "/api/reports":
            return self.send_json({"reports": reports()})
        if path == "/api/week":
            return self.send_json(week_data(date.fromisoformat(query["start"][0])))
        if path == "/api/scheduled":
            return self.send_json({"dates": []})
        if path in ("/api/draft", "/api/scheduled/draft"):
            day = date.fromisoformat(query["date"][0])
            return self.send_json({"date": day.isoformat(), "version": None, "unavailable": [], "categories": CATEGORIES,
                                   "projects": [project(n, t, day) for n, t in rows_for(day)]})
        if path == "/api/ubuntu":
            return self.send_json(ubuntu())
        if path == "/api/network":
            return self.send_json(network())
        if path == "/api/youtube/videos":
            return self.send_json(youtube())
        if path == "/api/youtube/models":
            return self.send_json({"status": "connected", "models": [{"slug": "demo", "label": "Demo model"}]})
        if path == "/api/youtube/retention":
            return self.send_json({"points": [[i / 20, max(.05, 1 - i * .045)] for i in range(21)]})
        if path == "/api/status":
            return self.send_json({"backend": True, "collector": True, "started": datetime.now(TZ).isoformat(), "reports": len(reports())})
        file = DIST / "index.html" if path == "/" else DIST / path.lstrip("/")
        if file.is_file() and DIST in file.resolve().parents or file == DIST / "index.html":
            body = file.read_bytes()
            kind = {".css": "text/css", ".js": "text/javascript", ".html": "text/html; charset=utf-8"}.get(file.suffix, "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        self.send_json({"error": "Η λειτουργία επίδειξης δεν αποθηκεύει δεδομένα."}, 403)

    do_DELETE = do_POST


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        print(f"Demo dashboard: http://127.0.0.1:{args.port}/")
        server.serve_forever()


if __name__ == "__main__":
    main()
