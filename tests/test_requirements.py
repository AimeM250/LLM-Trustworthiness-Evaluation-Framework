import http.client
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from zipfile import ZipFile

from ltef.engine import evaluate
from ltef.metrics import METRICS
from ltef.requirements import data_requirements, load_upload, readiness, starter_bundle
from ltef.schema import ValidationError
from ltef.webapp import make_server


def starter_inputs(sector='finance', metrics=None):
    with ZipFile(BytesIO(starter_bundle(sector, metrics))) as archive:
        return {name: archive.read(name + suffix).decode() for name, suffix in
                [('cases', '.jsonl'), ('observations', '.json'), ('profile', '.json')]}


class RequirementsTests(unittest.TestCase):
    def test_catalog_covers_executable_metrics_and_supplied_evidence(self):
        requirements = data_requirements()
        self.assertEqual({m['id'] for m in requirements['metrics']}, set(METRICS))
        self.assertEqual(len(requirements['common']), 4)
        for metric in requirements['metrics']:
            self.assertTrue(metric['required_fields'])
            self.assertTrue(metric['guidance'])
            self.assertTrue(metric['applicability'])
        supplied = {m['id']: m for m in requirements['metrics']}
        for mid in ('attack_success_rate', 'supported_claim_fraction', 'propagated_error_rate'):
            self.assertIn('annotations.rubric_version', supplied[mid]['required_fields'])
        self.assertIn('trace.complete = true', supplied['propagated_error_rate']['required_fields'])

    def test_templates_are_sector_scoped_valid_and_explicitly_synthetic(self):
        for sector in ('finance', 'healthcare', 'public_sector'):
            with self.subTest(sector=sector):
                raw = starter_bundle(sector)
                with ZipFile(BytesIO(raw)) as archive:
                    self.assertEqual(set(archive.namelist()), {'cases.jsonl', 'observations.json', 'profile.json', 'README.md'})
                    self.assertIn('fictional', archive.read('README.md').decode())
                cases, bundle, profile = load_upload(starter_inputs(sector))
                self.assertEqual({case['sector'] for case in cases}, {sector})
                self.assertEqual(len(cases), 8)
                self.assertTrue(all(case['synthetic'] for case in cases))
                self.assertEqual(len(profile['metrics']), 18 if sector == 'healthcare' else 17)
                report = evaluate(cases, bundle, profile)
                self.assertEqual(report['evidence_class'], 'synthetic_demo')

    def test_template_selection_is_exact_and_invalid_choices_rejected(self):
        _, _, profile = load_upload(starter_inputs(metrics=['reference_accuracy', 'cost_usd']))
        self.assertEqual(profile['metrics'], ['reference_accuracy', 'cost_usd'])
        for sector, metrics in [('unknown', None), ('finance', []), ('finance', ['invalid']), ('finance', ['cost_usd', 'cost_usd'])]:
            with self.assertRaises(ValidationError):
                starter_bundle(sector, metrics)

    def test_readiness_distinguishes_missing_failed_and_inapplicable(self):
        body = starter_inputs(metrics=['reference_accuracy', 'major_clinical_error_rate', 'cost_usd'])
        result = readiness(body)
        self.assertTrue(result['valid'])
        self.assertEqual((result['case_count'], result['system_count'], result['trials']), (8, 2, 2))
        metrics = {m['id']: m for m in result['metrics']}
        self.assertEqual(metrics['major_clinical_error_rate']['not_applicable'], 32)
        self.assertIsNone(metrics['major_clinical_error_rate']['coverage'])
        reference = metrics['reference_accuracy']
        self.assertGreater(reference['missing'], 0)
        self.assertGreater(reference['error'], 0)
        self.assertEqual(reference['scored'] + reference['missing'] + reference['error'], reference['eligible'])
        self.assertEqual(reference['coverage'], reference['scored'] / reference['eligible'])
        self.assertGreater(metrics['cost_usd']['scored'], reference['scored'])
        self.assertTrue(any('confidence intervals' in warning for warning in result['warnings']))

    def test_missing_reviews_do_not_become_zero_error_results(self):
        result = readiness(starter_inputs('healthcare', ['major_clinical_error_rate']))
        metric = result['metrics'][0]
        self.assertEqual(metric['scored'], 0)
        self.assertGreater(metric['missing'], 0)
        self.assertEqual(metric['coverage'], 0)


class RequirementsHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(0, Path(self.temp.name) / 'workspace.sqlite3')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None
        self.token = None
        self.request('GET', '/api/bootstrap')

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        extra = {'Content-Type': 'application/json'}
        if self.token:
            extra['X-LTEF-Token'] = self.token
        if self.cookie:
            extra['Cookie'] = self.cookie
        extra.update(headers or {})
        connection.request(method, path, None if body is None else json.dumps(body), extra)
        response = connection.getresponse()
        status = response.status
        raw = response.read()
        self.last_headers = dict(response.getheaders())
        if response.getheader('Set-Cookie'):
            self.cookie = response.getheader('Set-Cookie').split(';')[0]
        result = json.loads(raw) if response.getheader('Content-Type', '').startswith('application/json') else raw
        connection.close()
        if isinstance(result, dict) and 'token' in result:
            self.token = result['token']
        return status, result

    def register(self, email):
        return self.request('POST', '/api/auth/register', {'name': 'Data researcher', 'email': email, 'password': 'Test-only substantial password 42'})

    def test_permissions_guard_readiness_and_template_downloads(self):
        body = starter_inputs()
        for method, path, payload in [('GET', '/api/data-requirements', None), ('GET', '/api/templates', None), ('POST', '/api/validate', body)]:
            self.assertEqual(self.request(method, path, payload)[0], 401)
        self.register('admin@example.test')
        self.request('POST', '/api/auth/logout', {})
        _, viewer = self.register('viewer@example.test')
        self.assertEqual(viewer['user']['role'], 'viewer')
        status, result = self.request('GET', '/api/data-requirements')
        self.assertEqual(status, 200)
        self.assertEqual(len(result['metrics']), 18)
        self.assertEqual(self.request('GET', '/api/templates')[0], 403)
        self.assertEqual(self.request('POST', '/api/validate', body)[0], 403)

    def test_design_downloads_require_session_and_explicit_allowlist(self):
        self.assertEqual(self.request('GET', '/design/technical-design.html')[0], 401)
        self.register('design-admin@example.test')
        status, content = self.request('GET', '/design/technical-design.html')
        self.assertEqual(status, 200)
        self.assertIn(b'LTEF technical design', content)
        self.assertEqual(self.request('GET', '/design/../data-contract.md')[0], 404)
        self.assertEqual(self.request('GET', '/design/technical-design.md')[0], 404)

    def test_readiness_does_not_persist_and_actual_run_revalidates(self):
        self.register('admin@example.test')
        before = len(self.server.workspace.listing())
        body = starter_inputs(metrics=['reference_accuracy'])
        status, result = self.request('POST', '/api/validate', body)
        self.assertEqual(status, 200)
        self.assertTrue(result['valid'])
        self.assertNotIn('report', result)
        self.assertEqual(len(self.server.workspace.listing()), before)
        bundle = json.loads(body['observations'])
        bundle['records'][0]['prompt_sha256'] = 'tampered after checking'
        body['observations'] = json.dumps(bundle)
        status, result = self.request('POST', '/api/validate', body)
        self.assertEqual(status, 200)
        self.assertFalse(result['valid'])
        self.assertIn('prompt hash', result['errors'][0])
        self.assertEqual(self.request('POST', '/api/runs', dict(body, mode='upload', name='Invalid after check'))[0], 400)
        self.assertEqual(len(self.server.workspace.listing()), before)

    def test_errors_limits_csrf_and_download_contract(self):
        self.register('admin@example.test')
        body = starter_inputs()
        self.assertEqual(self.request('POST', '/api/validate', body, {'X-LTEF-Token': 'wrong'})[0], 403)
        self.assertEqual(self.request('POST', '/api/validate', body, {'Origin': 'https://hostile.example'})[0], 403)
        status, invalid = self.request('POST', '/api/validate', dict(body, cases='{bad json}'))
        self.assertEqual(status, 200)
        self.assertFalse(invalid['valid'])
        self.assertIn('cases.jsonl line 1', invalid['errors'][0])
        bundle = json.loads(body['observations'])
        bundle['trials'] = 1000
        status, invalid = self.request('POST', '/api/validate', dict(body, observations=json.dumps(bundle)))
        self.assertEqual(status, 200)
        self.assertFalse(invalid['valid'])
        self.assertIn('10,000', invalid['errors'][0])
        status, raw = self.request('GET', '/api/templates?sector=finance&metrics=reference_accuracy,cost_usd')
        self.assertEqual(status, 200)
        self.assertEqual(self.last_headers['Content-Type'], 'application/zip')
        self.assertIn('attachment;', self.last_headers['Content-Disposition'])
        with ZipFile(BytesIO(raw)) as archive:
            profile = json.loads(archive.read('profile.json'))
        self.assertEqual(profile['metrics'], ['reference_accuracy', 'cost_usd'])
        self.assertEqual(self.request('GET', '/api/templates?metrics=')[0], 400)


if __name__ == '__main__':
    unittest.main()
