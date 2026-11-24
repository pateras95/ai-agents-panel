"""Issue single-use Spotify pairing links and persist hashed device grants."""

import argparse
import hashlib
from html import escape
import os
from pathlib import Path
import re
import secrets
from tempfile import NamedTemporaryFile
from threading import Lock
import time
import webbrowser

from .lenovo_address import dashboard_base


STATE = Path(os.environ.get("NEXUS_SPOTIFY_PAIR_STATE")
             or Path.home() / ".local/state/nexus-ai/spotify-pairing")
LIFETIME = 300
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
REDEEM_LOCK = Lock()


def key_path(folder, token):
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return None
    return STATE / folder / hashlib.sha256(token.encode("ascii")).hexdigest()


def issue(folder):
    token = secrets.token_urlsafe(32)
    path = key_path(folder, token)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    return token


def pairing_link():
    tickets = STATE / "tickets"
    for item in tickets.glob("*"):
        try:
            if time.time() - item.stat().st_mtime > LIFETIME:
                item.unlink(missing_ok=True)
        except FileNotFoundError:
            continue
    return dashboard_base() + "/#spotify-pair=" + issue("tickets")


def redeem(token):
    path = key_path("tickets", token)
    if path is None:
        return None
    with REDEEM_LOCK:
        try:
            age = time.time() - path.stat().st_mtime
            path.unlink()
        except FileNotFoundError:
            return None
        return issue("devices") if 0 <= age <= LIFETIME else None


def device_grant(header):
    if not isinstance(header, str) or not header.startswith("Bearer "):
        return None
    path = key_path("devices", header.removeprefix("Bearer "))
    return path if path is not None and path.is_file() else None


def show_qr():
    import qrcode
    from qrcode.image.svg import SvgPathImage

    link = pairing_link()
    qr = qrcode.make(link, image_factory=SvgPathImage, box_size=10, border=4)
    url = escape(link, quote=True)
    markup = qr.to_string().decode()
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix="nexus-spotify-qr-",
        suffix=".html", delete=False, dir=os.environ.get("XDG_RUNTIME_DIR") or None,
    ) as page:
        page.write(f"""<!doctype html>
<html lang="el"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>NEXUS AI · Spotify QR</title>
<style>
body{{background:#18131a;color:#faf3f5;font:1rem system-ui;margin:2rem}}
main{{max-width:38rem;margin:auto;text-align:center}}
svg{{width:min(78vw,24rem);height:auto;background:#fff;border-radius:.5rem}}
a{{display:inline-block;padding:.8rem 1rem;background:#ff8299;color:#241018;
    text-decoration:none;border-radius:.5rem;font-weight:700}}
</style>
<main><h1>Σύζευξη Spotify</h1>
<p>Σάρωσε τον κωδικό με το iPhone στο ίδιο Wi‑Fi. Ισχύει για μία συσκευή και για 5 λεπτά.</p>
{markup}
<p><a href="{url}">Σύζευξη αυτού του browser</a></p></main></html>""")
        path = Path(page.name)
    if not webbrowser.open(path.as_uri()):
        print(path)


def pair_lenovo():
    """Hand a single-use ticket to the NEXUS Dashboard app on the USB-connected Lenovo tablet."""
    import subprocess

    ticket = pairing_link().rsplit("=", 1)[1]
    result = subprocess.run(
        ["/usr/bin/adb", "-d", "shell", "am", "start", "-n",
         "org.nexusai.panel.dashboard/org.nexusai.panel.MainActivity",
         "--es", "nexus_spotify_pair", ticket],
        capture_output=True, text=True, timeout=15)
    print("Έγινε σύζευξη του Lenovo." if result.returncode == 0 else "Το Lenovo δεν είναι συνδεδεμένο μέσω USB.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lenovo", action="store_true", help="Pair the USB-connected Lenovo tablet without a QR code.")
    parser.add_argument("--link", action="store_true", help="Print a single-use pairing link.")
    args = parser.parse_args()
    if args.lenovo:
        pair_lenovo()
    elif args.link:
        print(pairing_link())
    else:
        show_qr()


if __name__ == "__main__":
    main()
