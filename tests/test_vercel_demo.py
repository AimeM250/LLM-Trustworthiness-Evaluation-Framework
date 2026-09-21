"""Unit tests for api/_demo.py, the stateless logic behind the public Vercel demo.

These test pure functions only (no HTTP, no filesystem writes) — the public demo has no
database, so every 'run' must be fully reconstructable from its id alone.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'api') not in sys.path:
    sys.path.insert(0, str(ROOT))

from api._demo import (DEMO_USER, SAMPLE_SECTORS, bootstrap_payload, decode_adhoc,
                        encode_adhoc, new_evaluation, resolve_run, sample_id, sample_listing)
from ltef.auth import VIEWER_METRICS


class SampleRunTests(unittest.TestCase):
    def test_every_sector_resolves_for_anonymous_and_demo_user(self):
        for sector in SAMPLE_SECTORS:
            rid = sample_id(sector)
            anon = resolve_run(rid, None)
            demo = resolve_run(rid, DEMO_USER)
            self.assertEqual(anon['report']['profile']['sector'], sector)
            self.assertEqual(demo['report']['profile']['sector'], sector)
            self.assertTrue(anon['shared_sample'])

    def test_unknown_sample_id_is_not_found(self):
        with self.assertRaises(LookupError):
            resolve_run('sample:not-a-real-sector', DEMO_USER)

    def test_garbage_id_is_not_found(self):
        with self.assertRaises(LookupError):
            resolve_run('not-a-known-prefix', DEMO_USER)

    def test_demo_researcher_sees_all_metrics_viewer_role_would_not(self):
        rid = sample_id('finance')
        full = resolve_run(rid, DEMO_USER)['report']
        metric_ids = {m['id'] for m in full['metric_definitions']}
        self.assertTrue(metric_ids - VIEWER_METRICS, 'demo identity should not be viewer-restricted')

    def test_sample_listing_has_one_entry_per_sector(self):
        listing = sample_listing()
        self.assertEqual({row['sector'] for row in listing}, set(SAMPLE_SECTORS))
        self.assertTrue(all(row['shared_sample'] for row in listing))


class AdhocEncodingTests(unittest.TestCase):
    def test_round_trips_a_real_evaluated_report(self):
        report = resolve_run(sample_id('healthcare'), None)['report']
        token = encode_adhoc(report)
        self.assertTrue(token.startswith('adhoc:'))
        self.assertEqual(decode_adhoc(token[len('adhoc:'):]), report)

    def test_corrupted_token_is_not_found_not_a_crash(self):
        with self.assertRaises(LookupError):
            decode_adhoc('not-valid-base64-or-zlib')


class UploadFlowTests(unittest.TestCase):
    def setUp(self):
        self.cases = (ROOT / 'examples/cases.jsonl').read_text()
        self.observations = (ROOT / 'examples/observations.json').read_text()
        self.profile = (ROOT / 'examples/profiles/finance.json').read_text()

    def test_upload_mode_evaluates_for_real_and_yields_a_refreshable_adhoc_id(self):
        body = {'name': 'My upload', 'mode': 'upload', 'cases': self.cases,
                'observations': self.observations, 'profile': self.profile}
        result = new_evaluation(body, DEMO_USER)
        self.assertTrue(result['id'].startswith('adhoc:'))
        self.assertEqual(result['name'], 'My upload')
        again = resolve_run(result['id'], DEMO_USER)
        self.assertEqual(again['report'], result['report'])

    def test_demo_mode_reuses_the_matching_sample_without_recomputation(self):
        result = new_evaluation({'name': 'Quick look', 'mode': 'demo', 'sector': 'public_sector'},
                                 DEMO_USER)
        self.assertEqual(result['id'], sample_id('public_sector'))

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            new_evaluation({'name': 'x', 'mode': 'not-a-mode'}, DEMO_USER)


class BootstrapPayloadTests(unittest.TestCase):
    def test_anonymous_bootstrap_has_no_user_and_no_runs(self):
        payload = bootstrap_payload(None)
        self.assertFalse(payload['authenticated'])
        self.assertIsNone(payload['user'])
        self.assertEqual(payload['runs'], [])
        self.assertEqual(payload['metric_access'], [])

    def test_demo_user_bootstrap_is_authenticated_with_full_metric_access_and_sample_runs(self):
        payload = bootstrap_payload(DEMO_USER)
        self.assertTrue(payload['authenticated'])
        self.assertEqual(payload['user'], DEMO_USER)
        self.assertTrue(payload['permissions']['can_run'])
        self.assertFalse(payload['permissions']['can_manage_users'])
        self.assertEqual({row['sector'] for row in payload['runs']}, set(SAMPLE_SECTORS))
        self.assertTrue(set(payload['metric_access']) - VIEWER_METRICS)


if __name__ == '__main__':
    unittest.main()
