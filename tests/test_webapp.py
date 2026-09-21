import json
from pathlib import Path
import tempfile
import unittest

from ltef.webapp import Handler, Workspace, parse_json
from ltef.schema import ValidationError

ROOT = Path(__file__).resolve().parent.parent


class FakeServer:
    def __init__(self, port, extra_allowed_hosts=()):
        self.server_port = port
        self.extra_allowed_hosts = set(extra_allowed_hosts)


class TrustedHostTests(unittest.TestCase):
    """Handler.trusted() gates every request; --allowed-host must extend, not weaken, it."""

    def handler(self, host_header, extra_allowed_hosts=()):
        instance = Handler.__new__(Handler)
        instance.server = FakeServer(8765, extra_allowed_hosts)
        instance.headers = {'Host': host_header}
        return instance

    def test_default_loopback_hosts_are_trusted(self):
        self.assertTrue(self.handler('127.0.0.1:8765').trusted())
        self.assertTrue(self.handler('localhost:8765').trusted())

    def test_unknown_host_is_rejected_by_default(self):
        self.assertFalse(self.handler('ltef.example.com:8765').trusted())

    def test_explicitly_allowed_extra_host_is_trusted(self):
        self.assertTrue(self.handler('ltef.example.com:8765', {'ltef.example.com:8765'}).trusted())

    def test_extra_allowed_hosts_do_not_trust_other_hosts(self):
        handler = self.handler('someone-else.example.com:8765', {'ltef.example.com:8765'})
        self.assertFalse(handler.trusted())

    def test_mismatched_origin_is_rejected_even_for_an_allowed_host(self):
        handler = self.handler('ltef.example.com:8765', {'ltef.example.com:8765'})
        handler.headers['Origin'] = 'http://attacker.example.com'
        self.assertFalse(handler.trusted())

class WebWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'workspace.sqlite3'
        self.workspace = Workspace(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def inputs(self):
        return {'mode':'upload', 'name':'Imported test',
                'cases':(ROOT/'examples/cases.jsonl').read_text(),
                'observations':(ROOT/'examples/observations.json').read_text(),
                'profile':(ROOT/'examples/profiles/finance.json').read_text()}

    def test_seeds_three_sectors_and_persists_without_reseeding(self):
        self.assertEqual(len(self.workspace.listing()),3)
        run = self.workspace.run({'mode':'demo','sector':'finance','name':'Saved run'})
        other = Workspace(self.path)
        self.assertEqual(len(other.listing()),4)
        self.assertEqual(other.get(run['id'])['name'],'Saved run')
        self.assertNotEqual(other.token,self.workspace.token)

    def test_upload_runs_actual_engine_and_omits_raw_content(self):
        result = self.workspace.run(self.inputs())
        report = result['report']
        self.assertEqual(report['evidence_class'],'synthetic_demo')
        self.assertEqual(report['systems']['fixture-candidate']['metrics']['reference_accuracy']['value'],1)
        self.assertNotIn('response',json.dumps(report['case_results']))
        self.assertTrue(report['manifest']['dataset_sha256'])

    def test_invalid_inputs_do_not_create_runs(self):
        data = self.inputs()
        data['profile'] = '{bad json}'
        with self.assertRaises(ValueError):
            self.workspace.run(data)
        self.assertEqual(len(self.workspace.listing()),3)

    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        for raw in ['{"x":1,"x":2}', '{"x":NaN}']:
            with self.assertRaises(ValidationError):
                parse_json(raw)

    def test_expansion_limit_applies_before_evaluation(self):
        data = self.inputs()
        bundle = json.loads(data['observations'])
        bundle['trials'] = 1000
        data['observations'] = json.dumps(bundle)
        with self.assertRaisesRegex(ValidationError,'10,000'):
            self.workspace.run(data)

    def test_missing_run_and_invalid_name(self):
        with self.assertRaises(LookupError):
            self.workspace.get("' OR 1=1 --")
        with self.assertRaises(ValidationError):
            self.workspace.run({'mode':'demo','sector':'finance','name':'  '})

    def test_prompt_hash_mismatch_rejected_and_atomic(self):
        data = self.inputs()
        bundle = json.loads(data['observations'])
        bundle['records'][0]['prompt_sha256'] = 'wrong'
        data['observations'] = json.dumps(bundle)
        with self.assertRaisesRegex(ValidationError,'prompt hash'):
            self.workspace.run(data)
        self.assertEqual(len(self.workspace.listing()),3)

if __name__ == '__main__':
    unittest.main()
