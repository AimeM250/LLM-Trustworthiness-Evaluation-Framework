"""Vercel serverless entrypoint for the public LTEF demo (everything under /api/*).

This is deliberately separate from ltef/webapp.py, the real local server: there is no
SQLite workspace here, no password storage, and "signing in" only toggles a cosmetic
cookie (see api/_demo.py and SECURITY.md). The frontend it serves (ltef/web/*, published
as static files by vercel.json) is completely unmodified — every fetch() call it makes
already goes to a relative /api/... path handled here with the same JSON shapes the local
server returns, so a visitor can browse the exact same UI.
"""
import json
from http.client import responses as http_reasons
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

# Import _demo first: it inserts the repo root onto sys.path so `ltef` is importable below.
from _demo import (DEMO_TOKEN, DEMO_USER, bootstrap_payload, new_evaluation, readiness,
                    resolve_run, run_comparison, run_export)

from ltef.requirements import data_requirements, starter_bundle
from ltef.schema import ValidationError, require

MAX_BODY = 12 * 1024 * 1024
DEMO_COOKIE = 'ltef_demo'


class AccessError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class handler(BaseHTTPRequestHandler):
    server_version = 'LTEF-demo'

    def log_message(self, fmt, *args):
        pass

    def current_user(self):
        raw = self.headers.get('Cookie', '')
        if len(raw) > 4096:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return None
        return DEMO_USER if cookie.get(DEMO_COOKIE) and cookie[DEMO_COOKIE].value == 'in' else None

    def require_signed_in(self, user):
        if not user:
            raise AccessError(401, 'Sign in to access the demo workspace')
        return user

    def respond(self, status, data, content_type='application/json; charset=utf-8',
                attachment=None, cookie=None):
        payload = (json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
                   if content_type.startswith('application/json') else data)
        self.send_response(status, http_reasons.get(status, ''))
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy',
                          "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                          "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                          "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if attachment:
            self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
        if cookie is not None:
            max_age = 30 * 24 * 60 * 60 if cookie else 0
            self.send_header('Set-Cookie', f'{DEMO_COOKIE}={cookie}; Path=/; HttpOnly; '
                                            f'SameSite=Strict; Max-Age={max_age}')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlsplit(self.path).path
        query = parse_qs(urlsplit(self.path).query)
        user = self.current_user()
        try:
            if path == '/api/bootstrap':
                return self.respond(200, bootstrap_payload(user))
            if path == '/api/data-requirements':
                self.require_signed_in(user)
                return self.respond(200, data_requirements())
            if path == '/api/templates':
                self.require_signed_in(user)
                sector = query.get('sector', ['finance'])[0]
                metrics = query['metrics'][0].split(',') if 'metrics' in query else None
                return self.respond(200, starter_bundle(sector, metrics), 'application/zip',
                                     f'ltef-{sector}-starter.zip')
            if path.startswith('/api/runs/'):
                self.require_signed_in(user)
                pieces = path.split('/')
                run_id = pieces[3]
                if len(pieces) == 5 and pieces[4] == 'comparison':
                    return self.respond(200, run_comparison(
                        run_id, query.get('baseline', [''])[0], query.get('candidate', [''])[0], user))
                if len(pieces) == 5 and pieces[4] == 'export':
                    if query.get('format') == ['md']:
                        return self.respond(200, run_export(run_id, user, markdown=True).encode(),
                                             'text/markdown; charset=utf-8', 'ltef-report.md')
                    return self.respond(200, run_export(run_id, user), attachment='ltef-report.json')
                if len(pieces) == 4:
                    return self.respond(200, resolve_run(run_id, user))
            return self.respond(404, {'error': 'Not found'})
        except AccessError as exc:
            return self.respond(exc.status, {'error': str(exc)})
        except LookupError as exc:
            return self.respond(404, {'error': str(exc)})
        except (ValidationError, ValueError, TypeError) as exc:
            return self.respond(400, {'error': str(exc)})

    def do_POST(self):
        path = urlsplit(self.path).path
        user = self.current_user()
        supplied = self.headers.get('X-LTEF-Token', '')
        if supplied != DEMO_TOKEN:
            return self.respond(403, {'error': 'Refresh the page and try again'})
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self.respond(415, {'error': 'Expected application/json'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.respond(400, {'error': 'Invalid content length'})
        if not 0 < length <= MAX_BODY:
            return self.respond(413, {'error': 'Evaluation inputs must be under 12 MB combined'})
        try:
            body = json.loads(self.rfile.read(length).decode('utf-8'))
            require(isinstance(body, dict), 'Request must be a JSON object')
            if path == '/api/auth/register' or path == '/api/auth/login':
                return self.respond(200, bootstrap_payload(DEMO_USER), cookie='in')
            if path == '/api/auth/logout':
                return self.respond(200, bootstrap_payload(None), cookie='')
            if path == '/api/validate':
                self.require_signed_in(user)
                return self.respond(200, readiness(body))
            if path == '/api/runs':
                self.require_signed_in(user)
                return self.respond(201, new_evaluation(body, user))
            return self.respond(404, {'error': 'Not found'})
        except AccessError as exc:
            return self.respond(exc.status, {'error': str(exc)})
        except LookupError as exc:
            return self.respond(404, {'error': str(exc)})
        except (ValidationError, ValueError, TypeError, KeyError, AttributeError) as exc:
            if path == '/api/validate':
                return self.respond(200, {'valid': False, 'errors': [str(exc)[:500]]})
            return self.respond(400, {'error': str(exc)[:500]})
