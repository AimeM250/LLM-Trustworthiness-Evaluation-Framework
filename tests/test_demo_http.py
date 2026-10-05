"""Exercise the public demo through HTTP, including browser-encoded run IDs."""
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlencode

from handler import handler

ROOT = Path(__file__).resolve().parent.parent


class DemoHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None, authenticated=True):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        headers = {'Content-Type': 'application/json', 'X-LTEF-Token': 'public-demo'}
        if authenticated:
            headers['Cookie'] = 'ltef_demo=in'
        try:
            conn.request('POST' if body is not None else 'GET', path,
                         json.dumps(body) if body is not None else None, headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def verify_result(self, result):
        path = '/api/runs/' + quote(result['id'], safe='')
        status, raw = self.request(path)
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw)['report'], result['report'])
        systems = list(result['report']['systems'])
        query = urlencode({'baseline': systems[0], 'candidate': systems[1]})
        status, raw = self.request(path + '/comparison?' + query)
        self.assertEqual(status, 200, raw)
        self.assertIsInstance(json.loads(raw), dict)
        status, raw = self.request(path + '/export')
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw), result['report'])
        status, raw = self.request(path + '/export?format=md')
        self.assertEqual(status, 200, raw)
        self.assertIn(b'fixture-candidate', raw)

    def test_all_samples_load_compare_and_export(self):
        for sector in ('finance', 'healthcare', 'public_sector'):
            with self.subTest(sector=sector):
                status, raw = self.request('/api/runs', {
                    'mode': 'demo', 'name': 'HTTP verification', 'sector': sector})
                self.assertEqual(status, 201, raw)
                self.verify_result(json.loads(raw))

    def test_newly_computed_upload_loads_compares_and_exports(self):
        status, raw = self.request('/api/runs', {
            'mode': 'upload', 'name': 'Synthetic upload verification',
            'cases': (ROOT / 'examples/cases.jsonl').read_text(),
            'observations': (ROOT / 'examples/observations.json').read_text(),
            'profile': (ROOT / 'examples/profiles/finance.json').read_text()})
        self.assertEqual(status, 201, raw)
        result = json.loads(raw)
        self.assertTrue(result['id'].startswith('adhoc:'))
        self.verify_result(result)

    def test_unknown_and_double_encoded_ids_remain_not_found(self):
        for rid in ('sample%3Aunknown', 'sample%253Afinance', 'sample%3Afinance%2Fexport'):
            self.assertEqual(self.request('/api/runs/' + rid)[0], 404)

    def test_encoded_id_still_requires_sign_in(self):
        self.assertEqual(self.request('/api/runs/sample%3Afinance', authenticated=False)[0], 401)
