"""One-time Ubuntu loopback bridge for Google consent on the Lenovo backend."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from shlex import quote
import subprocess
from time import monotonic
from urllib.parse import parse_qs, urlsplit

from .youtube_growth import REDIRECT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client', type=Path, help='Local Desktop OAuth client JSON')
    parser.add_argument('channel', help='Expected YouTube channel ID')
    args = parser.parse_args()
    remote = (Path.home() / '.local/state/nexus-lenovo-pilot/remote').read_text().strip()
    client = json.loads(args.client.read_text(encoding='utf-8'))
    target = urlsplit(REDIRECT)

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never record query strings containing authorization codes.

        def do_GET(self):
            url = urlsplit(self.path)
            if self.headers.get('Host') != target.netloc or url.path != target.path:
                self.send_error(404)
                return
            query = parse_qs(url.query)
            if query.get('state') != expected_state:
                self.send_error(400, 'Invalid OAuth state')
                return
            child.stdin.write(json.dumps({key: query[key][0] for key in ('code', 'state') if key in query}) + '\n')
            child.stdin.flush()
            self.server.result = json.loads(child.stdout.readline())
            success = 'channel' in self.server.result
            body = b'Channel connected. You can close this tab.' if success else b'Channel connection failed. Check the Ubuntu terminal.'
            self.send_response(200 if success else 400)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer((target.hostname, target.port), Callback) as server:
        server.timeout = 1
        server.result = None
        command = (f'cd {quote(remote + "/release")} && '
                   f'NEXUS_DATA_DIR={quote(remote + "/production-data")} '
                   f'PYTHONTZPATH={quote(remote + "/tz")} '
                   f'{quote(remote + "/bin/python3.13")} -B -m backend.youtube_growth')
        with subprocess.Popen(['adb', '-d', 'shell', '-T', command],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as child:
            try:
                child.stdin.write(json.dumps({'client': client, 'channel': args.channel}) + '\n')
                child.stdin.flush()
                link = child.stdout.readline().strip()
                if not link.startswith('https://accounts.google.com/o/oauth2/v2/auth?'):
                    raise SystemExit('Δεν ξεκίνησε το OAuth στο Lenovo. Έλεγξε τον client, το Channel ID και το USB.')
                expected_state = parse_qs(urlsplit(link).query)['state']
                print('Άνοιξε αυτόν τον σύνδεσμο στον browser του Ubuntu και επίλεξε το κανάλι σου:\n' + link, flush=True)
                deadline = monotonic() + 300
                while server.result is None and monotonic() < deadline:
                    server.handle_request()
                if not server.result or 'channel' not in server.result:
                    raise SystemExit('Η εξουσιοδότηση ή η επιβεβαίωση του καναλιού δεν ολοκληρώθηκε.')
                print(f'Επιβεβαιώθηκε: {server.result["channel"]} ({server.result["id"]})')
            finally:
                if child.poll() is None:
                    child.terminate()


if __name__ == '__main__':
    main()
