"""Local accounts, expiring sessions, and authorization for the loopback workspace."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from copy import deepcopy

from .schema import ValidationError, require

PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 12 * 60 * 60
ATTEMPT_WINDOW = 15 * 60
MAX_ATTEMPTS = 12
ROLES = ('viewer', 'researcher', 'admin')
VIEWER_METRICS = frozenset({'reference_accuracy', 'supported_claim_fraction', 'brier_score',
                            'latency_ms', 'total_tokens', 'cost_usd'})


class AccessError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def permissions(user):
    research = bool(user and user['role'] in ('researcher', 'admin'))
    return {'can_run': research, 'can_compare': research, 'can_export': research,
            'can_manage_users': bool(user and user['role'] == 'admin')}


def metric_access(user, metrics):
    if not user:
        return []
    return [m['id'] for m in metrics if user['role'] != 'viewer' or m['id'] in VIEWER_METRICS]


def filter_report(report, allowed):
    result = deepcopy(report)
    allowed = set(allowed)
    result['profile']['metrics'] = [m for m in result['profile']['metrics'] if m in allowed]
    if isinstance(result['profile'].get('thresholds'), dict):
        result['profile']['thresholds'] = {k: v for k, v in result['profile']['thresholds'].items() if k in allowed}
    result['metric_definitions'] = [m for m in result['metric_definitions'] if m['id'] in allowed]
    for system in result['systems'].values():
        system['metrics'] = {k: v for k, v in system['metrics'].items() if k in allowed}
        # Supplementary metrics are a research-level feature, not an escape hatch
        # for unauthorized metrics through a separate response field.
        if allowed <= VIEWER_METRICS:
            for key in list(system):
                if key not in ('system', 'annotation_methods', 'metrics', 'delivery_rate'):
                    del system[key]
    for case in result.get('case_results', []):
        case['metrics'] = {k: v for k, v in case['metrics'].items() if k in allowed}
    result['access'] = {'metric_ids': sorted(allowed), 'filtered': len(result['metric_definitions']) != len(report['metric_definitions'])}
    return result


def public_user(row):
    return {'id': row[0], 'name': row[1], 'email': row[2], 'role': row[3]}


def email_value(value):
    require(isinstance(value, str), 'Enter a valid email address')
    value = value.strip().lower()
    require(len(value) <= 254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value), 'Enter a valid email address')
    return value


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PASSWORD_ITERATIONS).hex()


class Accounts:
    def __init__(self, connection):
        self.connection = connection
        # Equal-work dummy credentials prevent obvious unknown-account timing differences.
        self.dummy_salt = secrets.token_bytes(32)
        self.dummy_hash = password_hash(secrets.token_urlsafe(32), self.dummy_salt)
        with connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, role TEXT NOT NULL, salt BLOB NOT NULL, password_hash TEXT NOT NULL, created REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS auth_attempts (address TEXT NOT NULL, attempted REAL NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS auth_attempt_address ON auth_attempts(address, attempted)')

    def setup_required(self):
        with self.connection() as db:
            return db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0

    def throttle(self, address):
        now = time.time()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_attempts WHERE attempted < ?', (now - ATTEMPT_WINDOW,))
            count = db.execute('SELECT COUNT(*) FROM auth_attempts WHERE address = ?', (address,)).fetchone()[0]
            if count >= MAX_ATTEMPTS:
                raise AccessError(429, 'Too many sign-in attempts. Try again in 15 minutes.')
            db.execute('INSERT INTO auth_attempts VALUES (?, ?)', (address, now))

    def register(self, body, address):
        self.throttle(address)
        name = body.get('name')
        require(isinstance(name, str) and 1 <= len(name.strip()) <= 80, 'Name must contain 1–80 characters')
        email = email_value(body.get('email'))
        password = body.get('password')
        require(isinstance(password, str) and 12 <= len(password) <= 256, 'Password must contain 12–256 characters')
        salt = secrets.token_bytes(32)
        digest = password_hash(password, salt)
        uid = secrets.token_hex(16)
        try:
            with self.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                role = 'admin' if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0 else 'viewer'
                db.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (uid, name.strip(), email, role, salt, digest, time.time()))
                if role == 'admin':
                    db.execute('UPDATE runs SET owner_id = ? WHERE owner_id IS NULL AND shared_sample = 0', (uid,))
        except sqlite3.IntegrityError:
            raise ValidationError('An account with that email already exists. Sign in instead.')
        return {'id': uid, 'name': name.strip(), 'email': email, 'role': role}

    def login(self, body, address):
        self.throttle(address)
        email = email_value(body.get('email'))
        password = body.get('password')
        require(isinstance(password, str) and 1 <= len(password) <= 256, 'Enter your email and password')
        with self.connection() as db:
            row = db.execute('SELECT id, name, email, role, salt, password_hash FROM users WHERE email = ?', (email,)).fetchone()
        digest = password_hash(password, row[4] if row else self.dummy_salt)
        valid = hmac.compare_digest(digest, row[5] if row else self.dummy_hash)
        if not valid or not row:
            raise AccessError(401, 'Email or password is incorrect')
        return public_user(row)

    def issue(self, uid, previous=None):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE expires <= ?', (time.time(),))
            if previous:
                db.execute('DELETE FROM sessions WHERE token_hash = ?', (hashlib.sha256(previous.encode()).hexdigest(),))
            db.execute('INSERT INTO sessions VALUES (?, ?, ?, ?)',
                       (hashlib.sha256(token.encode()).hexdigest(), uid, csrf, time.time() + SESSION_SECONDS))
        return token

    def session(self, token):
        if not token or len(token) > 128:
            return None
        with self.connection() as db:
            row = db.execute('SELECT u.id, u.name, u.email, u.role, s.csrf FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires > ?',
                             (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        return {'user': public_user(row), 'csrf': row[4]} if row else None

    def revoke(self, token):
        if token:
            with self.connection() as db:
                db.execute('DELETE FROM sessions WHERE token_hash = ?', (hashlib.sha256(token.encode()).hexdigest(),))

    def users(self):
        with self.connection() as db:
            return [public_user(row) for row in db.execute('SELECT id, name, email, role FROM users ORDER BY created').fetchall()]

    def change_role(self, uid, role):
        require(role in ROLES, 'Choose viewer, researcher, or admin')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT role FROM users WHERE id = ?', (uid,)).fetchone()
            if current is None:
                raise LookupError('Account not found')
            if current[0] == 'admin' and role != 'admin' and db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0] <= 1:
                raise ValidationError('Keep at least one administrator in this workspace')
            db.execute('UPDATE users SET role = ? WHERE id = ?', (role, uid))
        return self.users()
