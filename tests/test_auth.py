import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from ltef.auth import VIEWER_METRICS
from ltef.webapp import Workspace, make_server

PASSWORD = 'A substantial test password 42'


class Browser:
    def __init__(self, server):
        self.port = server.server_port
        self.cookie = None
        self.token = None
        self.last_headers = {}

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        request_headers = {}
        if self.cookie:
            request_headers['Cookie'] = self.cookie
        if self.token:
            request_headers['X-LTEF-Token'] = self.token
        if data is not None:
            request_headers['Content-Type'] = 'application/json'
        request_headers.update(headers or {})
        connection.request(method, path, json.dumps(data) if data is not None else None, request_headers)
        response = connection.getresponse()
        self.last_headers = dict(response.getheaders())
        raw = response.read()
        status = response.status
        if response.getheader('Set-Cookie'):
            self.cookie = response.getheader('Set-Cookie').split(';')[0]
        body = json.loads(raw) if response.getheader('Content-Type', '').startswith('application/json') else raw
        connection.close()
        if isinstance(body, dict) and 'token' in body:
            self.token = body['token']
        return status, body

    def bootstrap(self):
        return self.request('GET', '/api/bootstrap')[1]

    def register(self, email='owner@example.test', **extra):
        self.bootstrap()
        return self.request('POST', '/api/auth/register', dict(name='Test Member', email=email, password=PASSWORD, **extra))


class AccountHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'workspace.sqlite3'
        self.server = make_server(0, self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.browser = Browser(self.server)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def test_anonymous_has_no_runs_or_metric_values(self):
        body = self.browser.bootstrap()
        self.assertFalse(body['authenticated'])
        self.assertTrue(body['setup_required'])
        self.assertEqual(body['runs'], [])
        self.assertEqual(body['metric_access'], [])
        self.assertTrue(all(not m['accessible'] for m in body['metrics']))
        rid = self.server.workspace.listing()[0]['id']
        self.assertEqual(self.browser.request('GET', '/api/runs/' + rid)[0], 401)
        self.assertEqual(self.browser.request('GET', '/api/users')[0], 401)
        self.assertEqual(self.browser.request('POST', '/api/runs', {'mode': 'demo', 'sector': 'finance', 'name': 'Private'})[0], 401)

    def test_initial_owner_login_rotates_session_and_logout_revokes(self):
        status, body = self.browser.register()
        self.assertEqual(status, 201)
        self.assertEqual(body['user']['role'], 'admin')
        self.assertFalse(body['setup_required'])
        self.assertEqual(len(body['runs']), 3)
        self.assertIn('HttpOnly', self.browser.last_headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', self.browser.last_headers['Set-Cookie'])
        first_cookie, first_token = self.browser.cookie, self.browser.token
        status, body = self.browser.request('POST', '/api/auth/login', {'email': 'OWNER@EXAMPLE.TEST', 'password': PASSWORD})
        self.assertEqual(status, 200)
        self.assertNotEqual(first_cookie, self.browser.cookie)
        self.assertNotEqual(first_token, self.browser.token)
        old = Browser(self.server)
        old.cookie = first_cookie
        self.assertFalse(old.bootstrap()['authenticated'])
        latest_cookie = self.browser.cookie
        self.assertEqual(self.browser.request('POST', '/api/auth/logout', {})[0], 200)
        old.cookie = latest_cookie
        self.assertFalse(old.bootstrap()['authenticated'])

    def test_wrong_password_and_unknown_account_use_same_response(self):
        self.browser.register()
        self.browser.request('POST', '/api/auth/logout', {})
        wrong = self.browser.request('POST', '/api/auth/login', {'email': 'owner@example.test', 'password': 'wrong'})
        unknown = self.browser.request('POST', '/api/auth/login', {'email': 'missing@example.test', 'password': 'wrong'})
        self.assertEqual(wrong, unknown)
        self.assertEqual(wrong[0], 401)
        self.assertFalse(self.browser.bootstrap()['authenticated'])

    def test_viewer_values_are_filtered_and_restricted_actions_fail(self):
        self.browser.register()
        viewer = Browser(self.server)
        status, body = viewer.register('viewer@example.test', role='admin')
        self.assertEqual(status, 201)
        self.assertEqual(body['user']['role'], 'viewer')
        self.assertEqual(set(body['metric_access']), VIEWER_METRICS)
        self.assertFalse(body['permissions']['can_run'])
        rid = body['runs'][0]['id']
        status, result = viewer.request('GET', '/api/runs/' + rid)
        self.assertEqual(status, 200)
        report = result['report']
        self.assertEqual(set(report['profile']['metrics']), VIEWER_METRICS)
        self.assertEqual({m['id'] for m in report['metric_definitions']}, VIEWER_METRICS)
        for system in report['systems'].values():
            self.assertEqual(set(system['metrics']), VIEWER_METRICS)
            self.assertNotIn('groups', system)
        for row in report['case_results']:
            self.assertTrue(set(row['metrics']) <= VIEWER_METRICS)
        for path in ('/api/runs/' + rid + '/export', '/api/runs/' + rid + '/comparison', '/api/users', '/samples/cases.jsonl'):
            self.assertEqual(viewer.request('GET', path)[0], 403)
        self.assertEqual(viewer.request('POST', '/api/runs', {'mode': 'demo', 'sector': 'finance', 'name': 'Unauthorized'})[0], 403)
        self.assertEqual(viewer.request('POST', '/api/users/' + body['user']['id'] + '/role', {'role': 'admin'})[0], 403)

    def test_role_changes_apply_to_existing_sessions_and_preserve_last_admin(self):
        _, admin = self.browser.register()
        member = Browser(self.server)
        _, viewer = member.register('member@example.test')
        uid = viewer['user']['id']
        self.assertEqual(self.browser.request('POST', '/api/users/' + uid + '/role', {'role': 'researcher'})[0], 200)
        current = member.bootstrap()
        self.assertEqual(current['user']['role'], 'researcher')
        self.assertEqual(len(current['metric_access']), 18)
        self.assertTrue(current['permissions']['can_run'])
        rid = current['runs'][0]['id']
        self.assertEqual(member.request('GET', '/api/runs/' + rid + '/export')[0], 200)
        self.assertEqual(member.request('GET', '/api/runs/' + rid + '/comparison?baseline=fixture-baseline&candidate=fixture-candidate')[0], 200)
        self.assertEqual(self.browser.request('POST', '/api/users/' + uid + '/role', {'role': 'viewer'})[0], 200)
        self.assertEqual(member.request('GET', '/api/runs/' + rid + '/export')[0], 403)
        self.assertEqual(self.browser.request('POST', '/api/users/' + admin['user']['id'] + '/role', {'role': 'viewer'})[0], 400)
        self.assertEqual(self.browser.bootstrap()['user']['role'], 'admin')

    def test_private_runs_are_inaccessible_even_to_other_admin(self):
        _, admin = self.browser.register()
        member = Browser(self.server)
        _, viewer = member.register('member@example.test')
        self.browser.request('POST', '/api/users/' + viewer['user']['id'] + '/role', {'role': 'researcher'})
        status, created = member.request('POST', '/api/runs', {'mode': 'demo', 'sector': 'finance', 'name': 'My research'})
        self.assertEqual(status, 201)
        self.assertFalse(created['shared_sample'])
        rid = created['id']
        self.assertEqual(member.request('GET', '/api/runs/' + rid)[0], 200)
        self.assertNotIn(rid, [r['id'] for r in self.browser.bootstrap()['runs']])
        for suffix in ('', '/export', '/comparison?baseline=fixture-baseline&candidate=fixture-candidate'):
            self.assertEqual(self.browser.request('GET', '/api/runs/' + rid + suffix)[0], 404)
        self.browser.request('POST', '/api/users/' + viewer['user']['id'] + '/role', {'role': 'viewer'})
        status, owned = member.request('GET', '/api/runs/' + rid)
        self.assertEqual(status, 200)
        self.assertEqual(len(owned['report']['metric_definitions']), 6)

    def test_csrf_origin_and_host_enforced(self):
        self.browser.bootstrap()
        signup = {'name': 'Member', 'email': 'member@example.test', 'password': PASSWORD}
        self.assertEqual(self.browser.request('POST', '/api/auth/register', signup, {'X-LTEF-Token': 'wrong'})[0], 403)
        self.assertEqual(self.browser.request('POST', '/api/auth/register', signup, {'Origin': 'https://hostile.example'})[0], 403)
        self.assertEqual(self.browser.request('GET', '/api/bootstrap', headers={'Host': 'hostile.example'})[0], 403)
        self.assertTrue(self.browser.bootstrap()['setup_required'])

    def test_passwords_salted_and_sessions_survive_restart_until_expiry(self):
        _, first = self.browser.register()
        other = Browser(self.server)
        other.register('second@example.test')
        with self.server.workspace.connection() as db:
            rows = db.execute('SELECT salt, password_hash FROM users').fetchall()
        self.assertNotEqual(rows[0][0], rows[1][0])
        self.assertNotEqual(rows[0][1], rows[1][1])
        self.assertNotIn(PASSWORD, str(rows))
        token = self.browser.cookie.split('=', 1)[1]
        restarted = Workspace(self.path)
        self.assertEqual(restarted.accounts.session(token)['user']['id'], first['user']['id'])
        with restarted.connection() as db:
            db.execute('UPDATE sessions SET expires = ?', (time.time() - 1,))
        self.assertFalse(self.browser.bootstrap()['authenticated'])

    def test_login_attempts_are_bounded(self):
        self.browser.bootstrap()
        with patch('ltef.auth.MAX_ATTEMPTS', 2):
            for _ in range(2):
                self.assertEqual(self.browser.request('POST', '/api/auth/login', {'email': 'missing@example.test', 'password': 'wrong'})[0], 401)
            self.assertEqual(self.browser.request('POST', '/api/auth/login', {'email': 'another@example.test', 'password': 'wrong'})[0], 429)

    def test_password_policy_and_duplicate_account_do_not_change_users(self):
        self.browser.bootstrap()
        self.assertEqual(self.browser.request('POST', '/api/auth/register', {'name': 'Member', 'email': 'member@example.test', 'password': 'short'})[0], 400)
        self.browser.register()
        other = Browser(self.server)
        self.assertEqual(other.register()[0], 400)
        self.assertEqual(len(self.server.workspace.accounts.users()), 1)


class MigrationTests(unittest.TestCase):
    def test_only_original_seeds_shared_and_legacy_runs_assigned_first_admin(self):
        with tempfile.TemporaryDirectory() as temp:
            original = Workspace(Path(temp) / 'source.sqlite3')
            path = Path(temp) / 'legacy.sqlite3'
            with sqlite3.connect(str(path)) as db:
                db.execute('CREATE TABLE runs (id TEXT PRIMARY KEY, name TEXT NOT NULL, report TEXT NOT NULL)')
                with original.connection() as source:
                    rows = source.execute('SELECT id, name, report FROM runs ORDER BY rowid').fetchall()
                db.executemany('INSERT INTO runs VALUES (?, ?, ?)', rows)
                db.execute('INSERT INTO runs VALUES (?, ?, ?)', ('private', rows[0][1], rows[0][2]))
            migrated = Workspace(path)
            admin = migrated.accounts.register({'name': 'Owner', 'email': 'owner@example.test', 'password': PASSWORD}, 'local')
            viewer = migrated.accounts.register({'name': 'Viewer', 'email': 'viewer@example.test', 'password': PASSWORD}, 'local')
            self.assertEqual(len(migrated.listing(admin)), 4)
            self.assertEqual(len(migrated.listing(viewer)), 3)
            self.assertFalse(migrated.get('private', admin)['shared_sample'])
            with self.assertRaises(LookupError):
                migrated.get('private', viewer)
            again = Workspace(path)
            self.assertEqual(len(again.listing(viewer)), 3)

    def test_concurrent_first_registration_creates_exactly_one_admin(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / 'workspace.sqlite3')
            errors = []
            def register(index):
                try:
                    workspace.accounts.register({'name': 'Member', 'email': 'member%d@example.test' % index, 'password': PASSWORD}, str(index))
                except Exception as exc:
                    errors.append(exc)
            threads = [threading.Thread(target=register, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(sorted(user['role'] for user in workspace.accounts.users()), ['admin', 'viewer'])


if __name__ == '__main__':
    unittest.main()
