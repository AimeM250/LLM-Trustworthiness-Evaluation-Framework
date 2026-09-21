"""Small transactional storage boundary for SQLite and PostgreSQL.

Application SQL uses positional ``?`` parameters. The PostgreSQL adapter maps
those placeholders to psycopg's bound parameters; values are never interpolated.
SQLite is for persistent single-host use. PostgreSQL supports multiple workers
and serverless instances, including transaction-mode connection poolers.
"""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3


def _lock_key(name):
    """Stable signed bigint for PostgreSQL advisory locks (not Python hash())."""
    return int.from_bytes(hashlib.sha256(('ltef:' + name).encode()).digest()[:8],
                          byteorder='big', signed=True)


class Connection:
    def __init__(self, connection, dialect):
        self.raw = connection
        self.dialect = dialect

    def execute(self, statement, parameters=()):
        if self.dialect == 'postgresql':
            # Application statements are static and do not contain literal '?'.
            statement = statement.replace('?', '%s')
            try:
                return self.raw.execute(statement, parameters)
            except Exception as exc:
                import psycopg
                if isinstance(exc, psycopg.IntegrityError):
                    raise sqlite3.IntegrityError('Database constraint violated') from exc
                raise
        return self.raw.execute(statement, parameters)

    def executemany(self, statement, parameters):
        if self.dialect == 'postgresql':
            with self.raw.cursor() as cursor:
                return cursor.executemany(statement.replace('?', '%s'), parameters)
        return self.raw.executemany(statement, parameters)

    def transaction_lock(self, name):
        """Serialize an invariant until the enclosing connection commits.

        SQLite's writer lock covers all names; PostgreSQL serializes by name.
        Call before reading any rows on which a subsequent mutation depends.
        """
        if self.dialect == 'postgresql':
            self.execute('SELECT pg_advisory_xact_lock(?)', (_lock_key(name),))
        elif not self.raw.in_transaction:
            self.raw.execute('BEGIN IMMEDIATE')

    def columns(self, table):
        if table not in ('runs', 'users', 'sessions', 'auth_attempts'):
            raise ValueError('Unknown application table')
        if self.dialect == 'postgresql':
            return {row[0] for row in self.execute(
                'SELECT column_name FROM information_schema.columns '
                'WHERE table_schema = current_schema() AND table_name = ?', (table,)).fetchall()}
        return {row[1] for row in self.execute('PRAGMA table_info(' + table + ')').fetchall()}


class Database:
    def __init__(self, path=None, *, database_url=None):
        self.dialect = 'postgresql' if database_url else 'sqlite'
        self.database_url = database_url
        self.path = None if database_url else str(path or Path('runs/web/workspace.sqlite3'))
        if self.path:
            if self.path == ':memory:':
                raise ValueError('Use a database file so independent connections share state')
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self):
        if self.dialect == 'postgresql':
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError('PostgreSQL requires the psycopg dependency; install LTEF with its web dependencies') from exc
            # No prepared statements: compatible with transaction-mode poolers.
            raw = psycopg.connect(self.database_url, connect_timeout=10, prepare_threshold=None)
            try:
                with raw:
                    yield Connection(raw, self.dialect)
            finally:
                raw.close()
        else:
            raw = sqlite3.connect(self.path, timeout=15)
            try:
                raw.execute('PRAGMA foreign_keys = ON')
                with raw:
                    yield Connection(raw, self.dialect)
            finally:
                raw.close()

    @contextmanager
    def evaluation_slot(self):
        """Nonblocking, crash-released mutex shared by workers.

        PostgreSQL holds a transaction advisory lock on a dedicated connection.
        SQLite holds a writer transaction in a separate lock database, allowing
        the evaluation to save its report in the primary database. Neither
        implementation uses expiring leases that might permit overlapping work.
        """
        if self.dialect == 'postgresql':
            with self.connection() as db:
                acquired = db.execute('SELECT pg_try_advisory_xact_lock(?)',
                                      (_lock_key('evaluation'),)).fetchone()[0]
                yield bool(acquired)
            return
        raw = sqlite3.connect(self.path + '.evaluation-lock', timeout=0)
        acquired = False
        try:
            try:
                raw.execute('BEGIN IMMEDIATE')
                acquired = True
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower():
                    raise
            yield acquired
        finally:
            if acquired:
                raw.rollback()
            raw.close()
