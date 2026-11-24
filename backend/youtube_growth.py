"""Read channel metadata and non-monetary analytics with server-side OAuth."""
import base64
from collections import defaultdict
import csv
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
from http.client import HTTPSConnection
from ipaddress import IPv4Address
import io
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import socket
import subprocess
from statistics import median
import sys
from tempfile import NamedTemporaryFile
from threading import Lock
from time import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

DATA = 'https://www.googleapis.com/youtube/v3'
ANALYTICS = 'https://youtubeanalytics.googleapis.com/v2/reports'
REPORTING = 'https://youtubereporting.googleapis.com/v1'
TOKEN = 'https://oauth2.googleapis.com/token'
REDIRECT = 'http://127.0.0.1:8768/youtube/callback'
SCOPES = 'https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly'
REACH = 'channel_reach_basic_a1'
METRICS = 'averageViewPercentage,estimatedMinutesWatched,subscribersGained,subscribersLost'
VIDEO_ID = re.compile(r'[\w-]{11}', re.ASCII)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def android_connection(address, *args, **kwargs):
    host, port = address
    # Portable glibc Python has no resolv.conf on Android. Native ping uses Android DNS.
    try:
        result = subprocess.run(['/system/bin/ping', '-c', '1', '-W', '1', host],
                                capture_output=True, text=True, timeout=3)
    except subprocess.SubprocessError as error:
        raise OSError('Android DNS lookup timed out') from error
    match = re.search(r'^PING .*?\(([0-9.]+)\)', result.stdout)
    if not match:
        raise OSError('Android DNS lookup failed')
    return socket.create_connection((str(IPv4Address(match[1])), port), *args, **kwargs)


class AndroidHTTPSConnection(HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = android_connection


class AndroidHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(AndroidHTTPSConnection, request, context=self._context)


@lru_cache(maxsize=1)
def google_opener():
    context = ssl.create_default_context()
    android_roots = Path('/system/etc/security/cacerts')
    if android_roots.is_dir() and context.cert_store_stats()['x509_ca'] == 0:
        for certificate in android_roots.glob('*'):
            context.load_verify_locations(cafile=str(certificate))
    handler = AndroidHTTPSHandler if android_roots.is_dir() else HTTPSHandler
    return build_opener(NoRedirect(), ProxyHandler({}), handler(context=context))


def request(url, *, params=None, data=None, token=None, content_type=None):
    if params:
        url += '?' + urlencode(params)
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    if content_type:
        headers['Content-Type'] = content_type
    with google_opener().open(Request(url, data=data, headers=headers), timeout=12) as response:
        body = response.read(12_000_001)
        if len(body) > 12_000_000:
            raise ValueError('Response too large')
        return body.decode('utf-8-sig')


def api(url, token, **params):
    return json.loads(request(url, params=params, token=token))


def pages(url, key, token, **params):
    while True:
        page = api(url, token, **params)
        yield from page.get(key, [])
        if not page.get('nextPageToken'):
            return
        params['pageToken'] = page['nextPageToken']


def exchange(client, **params):
    credentials = {key: client[key] for key in ('client_id', 'client_secret')}
    return json.loads(request(TOKEN, data=urlencode(credentials | params).encode()))


def channel_info(token, expected):
    channels = api(DATA + '/channels', token, part='snippet,contentDetails', mine='true')['items']
    channel = next((item for item in channels if item['id'] == expected), None)
    if channel is None:
        raise ValueError('The authorized channel does not match the expected channel ID.')
    return channel


def write_credentials(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, mode='w', encoding='utf-8', delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(value, output)
            output.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def authorize(path):
    setup = json.loads(input())
    client = setup['client']['installed']
    expected = setup['channel']
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', expected):
        raise ValueError('Invalid channel ID')
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    print('https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(dict(
        client_id=client['client_id'], redirect_uri=REDIRECT, response_type='code',
        scope=SCOPES, access_type='offline', prompt='consent select_account',
        state=state, code_challenge=challenge, code_challenge_method='S256',
    )), flush=True)
    callback = json.loads(input())
    if not secrets.compare_digest(state, callback.get('state', '')) or not callback.get('code'):
        raise ValueError('Google consent was canceled or the callback was invalid.')
    tokens = exchange(client, grant_type='authorization_code', code=callback['code'],
                      redirect_uri=REDIRECT, code_verifier=verifier)
    channel = channel_info(tokens['access_token'], expected)
    write_credentials(path, dict(client={key: client[key] for key in ('client_id', 'client_secret')},
                                 channel=expected, refresh=tokens['refresh_token']))
    project = client.get('project_id', '')
    if re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', project):
        write_credentials(path.with_name('project.json'), {'id': project})
    print(json.dumps({'channel': channel['snippet']['title'], 'id': expected}), flush=True)


class YouTubeGrowth:
    def __init__(self, directory):
        self.path = Path(directory) / 'youtube' / 'oauth.json'
        self.lock = Lock()
        self.access = None
        self.cached = None
        self.cache_until = 0
        self.reach_files = {}

    def token(self, config):
        if not self.access or self.access[1] < time():
            try:
                data = exchange(config['client'], grant_type='refresh_token', refresh_token=config['refresh'])
            except HTTPError as error:
                if error.code in (400, 401):
                    raise PermissionError from None
                raise
            self.access = data['access_token'], time() + data['expires_in'] - 60
        return self.access[0]

    def run(self, action, video=None):
        with self.lock:
            if not self.path.is_file():
                return {'status': 'disconnected'}
            config = json.loads(self.path.read_text(encoding='utf-8'))
            revision = self.path.stat().st_mtime_ns
            if revision != getattr(self, 'revision', None):
                self.revision = revision
                self.access = self.cached = None
                self.reach_files.clear()
            token = self.token(config)
            if self.cached is None or self.cache_until < time():
                self.cached = self.dashboard(token, config['channel'])
                self.cache_until = time() + 900
            if action == 'analysis-input':
                return self.cached
            if action == 'videos':
                project_file = self.path.with_name('project.json')
                project = json.loads(project_file.read_text(encoding='utf-8')).get('id', '') if project_file.is_file() else ''
                return self.cached | {'cloudProject': project, 'videos': [
                    {key: value for key, value in item.items() if key not in ('description', 'tags')}
                    for item in self.cached['videos']
                ]}
            if action == 'retention':
                if not any(item['id'] == video for item in self.cached['videos']):
                    raise ValueError('Unknown upload')
                try:
                    rows = self.analytics(token, self.cached['period'], METRICS_RETENTION,
                                          'elapsedVideoTimeRatio', 'video==' + video)
                except (OSError, ValueError, KeyError):
                    rows = []
                return {'points': rows}
            return suggestions(self.cached['videos'])

    @staticmethod
    def analytics(token, period, metrics, dimension, filters):
        ordering = {'sort': '-estimatedMinutesWatched', 'maxResults': 50} if dimension == 'video' else {'sort': dimension}
        return api(ANALYTICS, token, ids='channel==MINE', startDate=period['start'], endDate=period['end'],
                   metrics=metrics, dimensions=dimension, filters=filters, **ordering).get('rows', [])

    def dashboard(self, token, expected):
        channel = channel_info(token, expected)
        uploads = channel['contentDetails']['relatedPlaylists']['uploads']
        playlist = api(DATA + '/playlistItems', token, part='contentDetails', playlistId=uploads, maxResults=50)
        ids = [item['contentDetails']['videoId'] for item in playlist.get('items', [])]
        items = api(DATA + '/videos', token, part='snippet,status,contentDetails', id=','.join(ids)).get('items', []) if ids else []
        today = datetime.now(ZoneInfo('America/Los_Angeles')).date()
        period = {'start': (today - timedelta(days=30)).isoformat(), 'end': (today - timedelta(days=1)).isoformat()}
        warnings = []
        analytics, reach, formats = {}, {}, {}
        if ids:
            try:
                analytics = {row[0]: row[1:] for row in self.analytics(token, period, METRICS, 'video',
                                                                     'video==' + ','.join(ids))}
            except (OSError, ValueError, KeyError):
                warnings.append('Τα στοιχεία του YouTube Analytics δεν ήταν διαθέσιμα.')
            try:
                rows = api(ANALYTICS, token, ids='channel==MINE', startDate=period['start'],
                           endDate=period['end'], metrics='views', dimensions='video,creatorContentType',
                           filters='video==' + ','.join(ids), sort='-views', maxResults=200).get('rows', [])
                confirmed = defaultdict(set)
                for video_id, content_type, _ in rows:
                    normalized = content_type.replace('_', '').casefold()
                    if normalized != 'unspecified':
                        confirmed[video_id].add(normalized)
                formats = {video_id: next(iter(types)) for video_id, types in confirmed.items() if len(types) == 1}
            except (OSError, ValueError, KeyError):
                pass
            try:
                reach, days = self.reach(token, expected, period)
                if not days:
                    warnings.append('Το YouTube δεν έχει ακόμη διαθέσιμο reach report για την περίοδο.')
                else:
                    period['reachDays'] = days
            except (OSError, ValueError, KeyError):
                warnings.append('Το YouTube Reporting API δεν επέστρεψε στοιχεία reach.')
        videos = []
        for item in items:
            snippet = item['snippet']
            if item['status']['privacyStatus'] != 'public' or snippet['channelId'] != expected:
                continue
            vid = item['id']
            percent, minutes, gains, losses = analytics.get(vid, (None,) * 4)
            impressions, ctr = reach.get(vid, (None, None))
            thumbnail = snippet.get('thumbnails', {}).get('medium', {}).get('url')
            if thumbnail and urlsplit(thumbnail).netloc != 'i.ytimg.com':
                thumbnail = None
            content_type = formats.get(vid)
            duration = item.get('contentDetails', {}).get('duration', '')
            match = re.fullmatch(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
            seconds = sum(int(value or 0) * unit for value, unit in zip(match.groups(), (86400, 3600, 60, 1))) if match else 0
            if content_type == 'shorts':
                video_format = 'short'
            elif content_type == 'videoondemand' or (content_type is None and seconds > 180):
                video_format = 'long'
            else:
                video_format = 'other'
            videos.append(dict(id=vid, format=video_format, title=snippet['title'], published=snippet['publishedAt'], thumbnail=thumbnail,
                               description=snippet.get('description', '')[:800], tags=snippet.get('tags', []),
                               impressions=impressions, ctr=ctr, average=percent,
                               hours=None if minutes is None else minutes / 60,
                               subscribers=None if gains is None or losses is None else gains - losses))
        videos.sort(key=lambda video: video['published'], reverse=True)
        return dict(status='connected', channel={'id': expected, 'title': channel['snippet']['title']},
                    videos=videos, period=period, warnings=warnings)

    def reach(self, token, expected, period):
        jobs = REPORTING + '/jobs'
        job = next((item for item in pages(jobs, 'jobs', token) if item['reportTypeId'] == REACH), None)
        if not job:
            try:
                body = json.dumps({'reportTypeId': REACH, 'name': 'NEXUS AI · Reach'}).encode()
                job = json.loads(request(jobs, token=token, data=body, content_type='application/json'))
            except HTTPError as error:
                if error.code != 409:
                    raise
                job = next((item for item in pages(jobs, 'jobs', token) if item['reportTypeId'] == REACH), None)
            if not job:
                return {}, 0
        reports = {}
        for item in pages(jobs + '/' + job['id'] + '/reports', 'reports', token,
                          startTimeAtOrAfter=period['start'] + 'T00:00:00Z'):
            day = item['startTime'][:10]
            if day <= period['end'] and (day not in reports or item['createTime'] > reports[day]['createTime']):
                reports[day] = item
        files = {}
        totals = defaultdict(lambda: [0, 0.0, 0])
        for report in reports.values():
            identity = report['id']
            if identity not in self.reach_files:
                target = report['downloadUrl']
                parsed = urlsplit(target)
                if parsed.scheme != 'https' or parsed.netloc != 'youtubereporting.googleapis.com':
                    raise ValueError('Unexpected report origin')
                rows = csv.DictReader(io.StringIO(request(target, token=token)))
                self.reach_files[identity] = [
                    (row['video_id'], int(row['video_thumbnail_impressions']), row['video_thumbnail_impressions_ctr'])
                    for row in rows if row['channel_id'] == expected
                ]
            files[identity] = self.reach_files[identity]
            for video, impressions, ctr in files[identity]:
                total = totals[video]
                total[0] += impressions
                if ctr != '':
                    total[1] += impressions * float(ctr)
                    total[2] += impressions
        self.reach_files = files
        return {video: (count, weighted * 100 / covered if covered else None)
                for video, (count, weighted, covered) in totals.items()}, len(reports)


METRICS_RETENTION = 'audienceWatchRatio'


def suggestions(videos):
    candidates = [video for video in videos if video['ctr'] is not None and video['impressions'] >= 100]
    if len(candidates) < 3:
        return {'titles': [], 'thumbnails': [],
                'note': 'Χρειάζονται τουλάχιστον 3 βίντεο με CTR και 100 εμφανίσεις το καθένα για προτάσεις.'}
    best = max(candidates, key=lambda video: video['ctr'])
    typical = median(video['ctr'] for video in candidates)
    evidence = (f'«{best["title"]}» · CTR {best["ctr"]:.1f}% σε {best["impressions"]} εμφανίσεις. '
                f'Διάμεσο CTR δείγματος {typical:.1f}%.')
    titles = []
    for matches, proposal, pattern in (
        (lambda title: len(title) <= 55, '[Θέμα] σε μία γραμμή', 'τίτλοι έως 55 χαρακτήρες'),
        (lambda title: '?' in title, 'Αξίζει [το θέμα του βίντεο];', 'τίτλοι με ερώτηση'),
        (lambda title: bool(re.search(r'[|:–—]', title)),
         '[Θέμα] | [Τοποθεσία ή συγκεκριμένο όφελος]', 'τίτλοι με διαχωριστικό'),
    ):
        matched = [video['ctr'] for video in candidates if matches(video['title'])]
        other = [video['ctr'] for video in candidates if not matches(video['title'])]
        if len(matched) >= 2 and len(other) >= 2 and median(matched) > median(other):
            titles.append({'text': proposal,
                           'reason': (f'{pattern.capitalize()} · διάμεσο CTR {median(matched):.1f}% '
                                      f'σε {len(matched)} βίντεο και {median(other):.1f}% στα υπόλοιπα.')})
    if not titles:
        titles.append({'text': '[Θέμα] | [Προορισμός ή αποτέλεσμα]',
                       'reason': evidence + ' Δοκίμασε διατύπωση με σαφές θέμα και χρησιμοποίησε το διάμεσο CTR ως αφετηρία.'})
    thumbnails = [
        {'text': 'Το κύριο θέμα μπροστά, ευανάγνωστο σημείο ή κείμενο που δείχνει τον προορισμό πίσω.',
         'reason': evidence + ' Δοκιμή για να φαίνεται με μια ματιά ο προορισμός.'},
        {'text': 'Ένα κοντινό από το πιο αναγνωρίσιμο σημείο, με έως τρεις λέξεις.',
         'reason': f'Διάμεσο CTR {typical:.1f}% σε {len(candidates)} βίντεο ως βάση για δοκιμή πιο απλής σύνθεσης.'},
    ]
    return {
        'titles': titles, 'thumbnails': thumbnails,
        'note': 'Το CTR δεν απομονώνει την επίδραση τίτλου ή thumbnail. Δεν υπάρχουν στοιχεία ωριαίας παρουσίας κοινού για πρόταση ώρας Αθήνας.',
    }



if __name__ == '__main__':
    try:
        authorize(Path(os.environ['NEXUS_DATA_DIR']) / 'youtube' / 'oauth.json')
    except (OSError, ValueError, KeyError, EOFError):
        print(json.dumps({'error': 'Η σύνδεση απέτυχε. Έλεγξε τον OAuth client, τις άδειες API και το Channel ID.'}), flush=True)
        sys.exit(1)
