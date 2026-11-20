"""Authorize ChatGPT plan usage from the Ubuntu browser, then store the session on Lenovo."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
from shlex import quote
import subprocess
from time import monotonic, time
from urllib.parse import parse_qs, urlencode, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .chatgpt_plan import ISSUER, RESOURCE, SCOPES, exchange, token_fields
from .youtube_growth import request


def decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def identity(token, client, nonce):
    head, body, signature = token.split('.')
    header = json.loads(decode(head))
    if header['alg'] != 'RS256':
        raise ValueError('Unsupported identity signature')
    keys = json.loads(request(ISSUER + '/.well-known/jwks.json'))['keys']
    key = next(key for key in keys if key['kid'] == header['kid'] and key['kty'] == 'RSA')
    public = rsa.RSAPublicNumbers(*(int.from_bytes(decode(key[name]), 'big') for name in ('e', 'n'))).public_key()
    public.verify(decode(signature), (head + '.' + body).encode(), padding.PKCS1v15(), hashes.SHA256())
    claims = json.loads(decode(body))
    audience = claims['aud']
    if (claims['iss'] != ISSUER or client not in ([audience] if isinstance(audience, str) else audience)
            or claims['exp'] <= time() or claims['iat'] > time() + 5 or claims['nonce'] != nonce
            or not isinstance(claims['sub'], str) or not claims['sub']):
        raise ValueError('Invalid ChatGPT identity')
    return claims


def main():
    remote = (Path.home() / '.local/state/nexus-lenovo-pilot/remote').read_text().strip()
    directory = quote(remote + '/release')
    python = quote(remote + '/bin/python3.13')
    root = remote + '/production-data/chatgpt'
    shell = f'cd {directory} && {python} -B -c '

    def lenovo(code, body=None):
        return subprocess.run(['adb', '-d', 'shell', '-T', shell + quote(code)],
                              input=body or '', text=True, capture_output=True, check=True, timeout=12).stdout

    profile = json.loads(lenovo(
        'import json, uuid\nfrom pathlib import Path\nfrom backend.youtube_growth import write_credentials\n'
        f'root=Path({root!r})\n'
        'host=root/"host.json"\n'
        'if not host.exists(): write_credentials(host, {"id":uuid.uuid4().urn})\n'
        'session=root/"oauth.json"\n'
        'saved=json.loads(session.read_text()) if session.exists() else {}\n'
        'print(json.dumps(dict(host=json.loads(host.read_text())["id"], '
        'client=saved.get("client_id"), subject=saved.get("subject"))))'
    ))
    state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result = None

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            nonlocal result
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            if url.path != '/auth/callback' or self.headers.get('Host') != address:
                self.send_error(404)
                return
            if not secrets.compare_digest(query.get('state', [''])[0], state):
                self.send_error(400)
                return
            try:
                client = query.get('client_id', [''])[0] or profile['client']
                if not client or not client.startswith('oaiapp_') or (profile['client'] and client != profile['client']):
                    raise ValueError('Missing registered client')
                tokens = exchange(grant_type='authorization_code', client_id=client, code=query['code'][0],
                                  code_verifier=verifier, redirect_uri=redirect)
                claims = identity(tokens['id_token'], client, nonce)
                if profile['subject'] and profile['subject'] != claims['sub']:
                    raise ValueError('Different account')
                saved = token_fields(tokens) | dict(client_id=client, subject=claims['sub'])
                lenovo('import json, sys\nfrom pathlib import Path\n'
                       'from backend.youtube_growth import write_credentials\n'
                       f'write_credentials(Path({root + "/oauth.json"!r}), json.load(sys.stdin))',
                       json.dumps(saved))
                result = 'connected'
            except Exception as error:
                result = f'unavailable ({type(error).__name__})'
            self.send_response(200 if result == 'connected' else 400)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(('ChatGPT plan connected. You can close this tab.' if result == 'connected'
                              else 'ChatGPT plan connection unavailable. You can close this tab.').encode())

    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 1
        address = f'127.0.0.1:{server.server_port}'
        redirect = 'http://' + address + '/auth/callback'
        fields = dict(client_id=profile['client'] or 'dynamic_agent_client', redirect_uri=redirect,
                      response_type='code', scope=SCOPES, resource=RESOURCE, state=state, nonce=nonce,
                      code_challenge=challenge, code_challenge_method='S256', ext_agent_host_id=profile['host'])
        if not profile['client']:
            fields['agent_name_hint'] = 'NEXUS AI'
        print(ISSUER + '/api/accounts/authorize?' + urlencode(fields), flush=True)
        deadline = monotonic() + 300
        while result is None and monotonic() < deadline:
            server.handle_request()
        print(result or 'expired', flush=True)
        if result != 'connected':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
