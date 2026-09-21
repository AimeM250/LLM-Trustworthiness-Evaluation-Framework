"""Loopback-only LTEF web workspace. Run: python3 -m ltef.webapp."""
import argparse
from contextlib import contextmanager
import hmac
import json
import logging
import secrets
import sqlite3
import threading
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from .auth import Accounts, AccessError, VIEWER_METRICS, SESSION_SECONDS, permissions, metric_access, filter_report
from .engine import evaluate, compare
from .metrics import catalog
from .reporting import render
from .requirements import data_requirements, load_upload, parse_json, readiness, starter_bundle
from .schema import ValidationError, require, read_cases, read_json

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "web"
MAX_BODY = 12 * 1024 * 1024


class Workspace:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, name TEXT NOT NULL, report TEXT NOT NULL, owner_id TEXT, shared_sample INTEGER NOT NULL DEFAULT 0)")
            columns = {row[1] for row in db.execute('PRAGMA table_info(runs)')}
            if 'owner_id' not in columns:
                db.execute('ALTER TABLE runs ADD COLUMN owner_id TEXT')
            if 'shared_sample' not in columns:
                db.execute('ALTER TABLE runs ADD COLUMN shared_sample INTEGER NOT NULL DEFAULT 0')
                # Only the original seed rows become shared; later demo evaluations remain private.
                rows = db.execute('SELECT id, name, report FROM runs ORDER BY rowid LIMIT 3').fetchall()
                for row, sector in zip(rows, ('finance', 'healthcare', 'public_sector')):
                    report = json.loads(row[2])
                    if (row[1] == sector.replace('_', ' ').title() + ' · sample evaluation'
                            and report.get('evidence_class') == 'synthetic_demo'
                            and report.get('profile', {}).get('sector') == sector):
                        db.execute('UPDATE runs SET shared_sample = 1 WHERE id = ?', (row[0],))
            count = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        self.accounts = Accounts(self.connection)
        if count == 0:
            for sector in ("finance", "healthcare", "public_sector"):
                self.save(self.demo(sector), sector.replace('_', ' ').title() + " · sample evaluation", shared_sample=True)
        with self.connection() as db:
            admin = db.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY created LIMIT 1").fetchone()
            if admin:
                db.execute('UPDATE runs SET owner_id = ? WHERE owner_id IS NULL AND shared_sample = 0', (admin[0],))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def demo(self, sector):
        require(sector in {"finance", "healthcare", "public_sector"}, "Unknown sector")
        return evaluate(read_cases(ROOT / "examples/cases.jsonl"),
                        read_json(ROOT / "examples/observations.json"),
                        read_json(ROOT / "examples/profiles" / (sector + ".json")))

    def save(self, report, name, owner_id=None, shared_sample=False):
        rid = uuid.uuid4().hex
        with self.connection() as db:
            db.execute("INSERT INTO runs (id, name, report, owner_id, shared_sample) VALUES (?, ?, ?, ?, ?)",
                       (rid, name, json.dumps(report, allow_nan=False), owner_id, int(shared_sample)))
        return rid

    def get(self, rid, user=None):
        with self.connection() as db:
            row = db.execute("SELECT name, report, owner_id, shared_sample FROM runs WHERE id = ?", (rid,)).fetchone()
        if row is None or (user is not None and not row[3] and row[2] != user['id']):
            raise LookupError("Evaluation not found")
        report = json.loads(row[1])
        if user is not None:
            report = filter_report(report, metric_access(user, catalog()))
        return {"id": rid, "name": row[0], "report": report, "shared_sample": bool(row[3])}

    def listing(self, user=None):
        with self.connection() as db:
            if user is None:
                rows = db.execute("SELECT id, name, report, shared_sample FROM runs ORDER BY rowid DESC").fetchall()
            else:
                rows = db.execute("SELECT id, name, report, shared_sample FROM runs WHERE shared_sample = 1 OR owner_id = ? ORDER BY rowid DESC", (user['id'],)).fetchall()
        result = []
        for rid, name, payload, shared in rows:
            r = json.loads(payload)
            result.append({"id": rid, "name": name, "sector": r['profile']['sector'],
                           "created_utc": r['created_utc'], "evidence_class": r['evidence_class'],
                           "cases": len(r['manifest']['selected_case_ids']), "systems": len(r['systems']),
                           "trials": r['manifest']['trials'], "shared_sample": bool(shared)})
        return result

    def run(self, body, user=None):
        require(isinstance(body, dict), "Request must be a JSON object")
        name = body.get('name', 'Untitled evaluation')
        require(isinstance(name, str) and 1 <= len(name.strip()) <= 120, "Name must contain 1–120 characters")
        if body.get('mode') == 'demo':
            report = self.demo(body.get('sector'))
        else:
            require(body.get('mode') == 'upload', "Unknown evaluation mode")
            cases, bundle, profile = load_upload(body)
            report = evaluate(cases, bundle, profile)
        return self.get(self.save(report, name.strip(), owner_id=user['id'] if user else None), user)


class Handler(BaseHTTPRequestHandler):
    server_version = "LTEF"

    def log_message(self, fmt, *args):
        logging.info("%s %s", self.command, urlsplit(self.path).path)

    def trusted(self):
        host = self.headers.get('Host', '')
        port = self.server.server_port
        allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
        allowed.update(getattr(self.server, 'extra_allowed_hosts', ()))
        return host in allowed and self.headers.get('Origin', 'http://' + host) == 'http://' + host

    def session_token(self):
        raw = self.headers.get('Cookie', '')
        if len(raw) > 4096:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
            return cookie['ltef_session'].value if 'ltef_session' in cookie else None
        except Exception:
            return None

    def session(self):
        return self.server.workspace.accounts.session(self.session_token())

    def bootstrap(self, session=None):
        workspace = self.server.workspace
        user = session['user'] if session else None
        available = metric_access(user, catalog())
        metrics = [dict(m, accessible=m['id'] in available,
                        required_role='viewer' if m['id'] in VIEWER_METRICS else 'researcher') for m in catalog()]
        return {'authenticated': bool(user), 'user': user,
                'setup_required': workspace.accounts.setup_required(),
                'token': session['csrf'] if session else workspace.token,
                'runs': workspace.listing(user) if user else [], 'metrics': metrics,
                'permissions': permissions(user), 'metric_access': available}

    def require_user(self, session, permission=None):
        if not session:
            raise AccessError(401, 'Sign in to access your workspace')
        user = session['user']
        if permission and not permissions(user)[permission]:
            raise AccessError(403, 'Your account does not have access to this feature')
        return user

    def respond(self, status, data, content_type='application/json; charset=utf-8', attachment=None, cookie=None):
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if attachment:
            self.send_header('Content-Disposition', 'attachment; filename="' + attachment + '"')
        if cookie is not None:
            self.send_header('Set-Cookie', 'ltef_session=' + cookie + '; Path=/; HttpOnly; SameSite=Strict; Max-Age=' + str(SESSION_SECONDS if cookie else 0))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.trusted():
            return self.respond(403, {'error': 'Only same-origin local requests are accepted'})
        path = urlsplit(self.path).path
        try:
            session = self.session()
            if path == '/api/bootstrap':
                return self.respond(200, self.bootstrap(session))
            if path == '/api/users':
                self.require_user(session, 'can_manage_users')
                return self.respond(200, {'users': self.server.workspace.accounts.users()})
            if path == '/api/data-requirements':
                self.require_user(session)
                return self.respond(200, data_requirements())
            if path == '/api/templates':
                self.require_user(session, 'can_run')
                q = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                sector = q.get('sector', ['finance'])[0]
                metrics = q['metrics'][0].split(',') if 'metrics' in q else None
                return self.respond(200, starter_bundle(sector, metrics), 'application/zip', 'ltef-' + sector + '-starter.zip')
            design_files = {'technical-design.html': 'text/html; charset=utf-8',
                            'technical-design.pdf': 'application/pdf',
                            'evidence-matrix.csv': 'text/csv; charset=utf-8',
                            'LTEF-technical-design.drawio': 'application/xml',
                            'design-package.zip': 'application/zip'}
            if path.startswith('/design/'):
                self.require_user(session)
                filename = path[len('/design/'):]
                artifact = ROOT / 'docs/design' / filename
                if filename not in design_files or not artifact.is_file():
                    return self.respond(404, {'error': 'Design document not found'})
                return self.respond(200, artifact.read_bytes(), design_files[filename],
                                    None if filename.endswith('.html') else filename)
            if path.startswith('/api/runs/'):
                user = self.require_user(session)
                pieces = path.split('/')
                if len(pieces) == 5 and pieces[4] in ('comparison', 'export'):
                    self.require_user(session, 'can_compare' if pieces[4] == 'comparison' else 'can_export')
                run = self.server.workspace.get(pieces[3], user)
                if len(pieces) == 5 and pieces[4] == 'comparison':
                    q = parse_qs(urlsplit(self.path).query)
                    return self.respond(200, compare(run['report'], q.get('baseline', [''])[0], q.get('candidate', [''])[0]))
                if len(pieces) == 5 and pieces[4] == 'export':
                    if parse_qs(urlsplit(self.path).query).get('format') == ['md']:
                        return self.respond(200, render(run['report']).encode(), 'text/markdown; charset=utf-8', 'ltef-report.md')
                    return self.respond(200, run['report'], attachment='ltef-report.json')
                if len(pieces) == 4:
                    return self.respond(200, run)
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/data.js': ('data.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8'), '/favicon.svg': ('favicon.svg', 'image/svg+xml'),
                     '/fonts/Manrope.ttf': ('fonts/Manrope.ttf', 'font/ttf'), '/fonts/InstrumentSerif.ttf': ('fonts/InstrumentSerif.ttf', 'font/ttf'),
                     '/fonts/Manrope-OFL.txt': ('fonts/Manrope-OFL.txt', 'text/plain; charset=utf-8'), '/fonts/InstrumentSerif-OFL.txt': ('fonts/InstrumentSerif-OFL.txt', 'text/plain; charset=utf-8')}
            if path in files:
                filename, mime = files[path]
                return self.respond(200, (STATIC / filename).read_bytes(), mime)
            if path.startswith('/samples/'):
                self.require_user(session, 'can_run')
                if path in {'/samples/cases.jsonl', '/samples/observations.json'}:
                    filename = path.rsplit('/', 1)[1]
                    return self.respond(200, (ROOT / 'examples' / filename).read_bytes(), 'application/octet-stream', filename)
                if path.startswith('/samples/profile/') and path.rsplit('/', 1)[1] in {'finance', 'healthcare', 'public_sector'}:
                    filename = path.rsplit('/', 1)[1] + '.json'
                    return self.respond(200, (ROOT / 'examples/profiles' / filename).read_bytes(), 'application/octet-stream', filename)
            return self.respond(404, {'error': 'Not found'})
        except AccessError as exc:
            return self.respond(exc.status, {'error': str(exc)})
        except LookupError as exc:
            return self.respond(404, {'error': str(exc)})
        except (ValidationError, ValueError, TypeError) as exc:
            return self.respond(400, {'error': str(exc)})

    def do_POST(self):
        if not self.trusted():
            return self.respond(403, {'error': 'Only same-origin local requests are accepted'})
        path = urlsplit(self.path).path
        session = self.session()
        expected = session['csrf'] if session else self.server.workspace.token
        supplied = self.headers.get('X-LTEF-Token', '')
        if not hmac.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8')):
            return self.respond(403, {'error': 'Refresh the page and try again'})
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self.respond(415, {'error': 'Expected application/json'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.respond(400, {'error': 'Invalid content length'})
        if not 0 < length <= MAX_BODY:
            return self.respond(413, {'error': 'Evaluation inputs must be under 12 MB combined'})
        acquired = False
        try:
            self.connection.settimeout(30)
            body = parse_json(self.rfile.read(length).decode('utf-8'))
            require(isinstance(body, dict), 'Request must be a JSON object')
            accounts = self.server.workspace.accounts
            if path in ('/api/auth/register', '/api/auth/login'):
                user = (accounts.register(body, self.client_address[0]) if path.endswith('register')
                        else accounts.login(body, self.client_address[0]))
                token = accounts.issue(user['id'], self.session_token())
                return self.respond(201 if path.endswith('register') else 200,
                                    self.bootstrap(accounts.session(token)), cookie=token)
            if path == '/api/auth/logout':
                self.require_user(session)
                accounts.revoke(self.session_token())
                return self.respond(200, self.bootstrap(), cookie='')
            if path.startswith('/api/users/') and path.endswith('/role') and len(path.split('/')) == 5:
                self.require_user(session, 'can_manage_users')
                return self.respond(200, {'users': accounts.change_role(path.split('/')[3], body.get('role'))})
            if path not in ('/api/runs', '/api/validate'):
                return self.respond(404, {'error': 'Not found'})
            user = self.require_user(session, 'can_run')
            acquired = self.server.workspace.lock.acquire(blocking=False)
            if not acquired:
                return self.respond(409, {'error': 'An evaluation is already running. Please try again shortly.'})
            if path == '/api/validate':
                return self.respond(200, readiness(body))
            return self.respond(201, self.server.workspace.run(body, user))
        except AccessError as exc:
            return self.respond(exc.status, {'error': str(exc)})
        except LookupError as exc:
            return self.respond(404, {'error': str(exc)})
        except (ValidationError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
            if path == '/api/validate':
                return self.respond(200, {'valid': False, 'errors': [str(exc)[:500]]})
            return self.respond(400, {'error': str(exc)[:500]})
        except Exception:
            logging.exception('Request failed')
            return self.respond(500, {'error': 'Request could not be completed. Check the local server log.'})
        finally:
            if acquired:
                self.server.workspace.lock.release()


def make_server(port=8765, database=None, host='127.0.0.1', allowed_hosts=()):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.extra_allowed_hosts = set(allowed_hosts)
    server.workspace = Workspace(database or ROOT / 'runs/web/workspace.sqlite3')
    return server


def main():
    parser = argparse.ArgumentParser(description='Open the local LTEF web workspace')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--host', default='127.0.0.1',
                         help='Bind address. Only change this if you know what you are doing: '
                              'the built-in accounts/session model assumes a trusted network '
                              'boundary, not public internet exposure (see SECURITY.md).')
    parser.add_argument('--allowed-host', action='append', default=[], metavar='HOST:PORT',
                         help='Additional Host header value to trust (repeatable), e.g. '
                              '--allowed-host ltef.example.com:8765. Needed only when reaching '
                              'the server through a hostname other than 127.0.0.1/localhost, '
                              'such as a LAN IP, container hostname, or reverse-proxy domain.')
    parser.add_argument('--open', action='store_true', help='Open the workspace in your default browser')
    args = parser.parse_args()
    try:
        server = make_server(args.port, args.database, args.host, args.allowed_host)
    except OSError as exc:
        parser.exit(1, f'Cannot start LTEF on port {args.port}: {exc}. Try --port 8766.\n')
    if args.host not in ('127.0.0.1', 'localhost'):
        print(f'WARNING: binding to {args.host} may expose this workspace beyond your own '
              'machine. Put it behind your own TLS/access control (see SECURITY.md).', flush=True)
    if args.open:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{server.server_port}')
    print(f'LTEF workspace: http://{args.host}:{server.server_port}', flush=True)
    print('Press Ctrl+C to stop. Evaluation reports are saved locally.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
