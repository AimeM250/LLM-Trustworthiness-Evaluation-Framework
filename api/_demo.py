"""Stateless logic behind the public LTEF demo (deployed as a Vercel serverless function).

Unlike ltef/webapp.py (a real local server with real accounts and a persistent SQLite
workspace), everything here is a pure function: there is no database, no password storage,
and nothing that needs protecting the way a real account system would. "Signing in" on the
public demo is cosmetic — it only toggles whether the fixed DEMO_USER identity is attached to
the response, purely so the existing frontend (which expects a logged-out vs. logged-in
distinction) has something sensible to render. See SECURITY.md for the reasoning.

Evaluation results carry themselves instead of living in a database:
  - "sample:<sector>" resolves to a report bundled in examples/reports/.
  - "adhoc:<token>" decodes a freshly computed report straight out of the id, so a result
    a visitor generated from their own upload survives a refresh or a shared link without
    any server-side storage.
"""
import base64
import json
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ltef.auth import VIEWER_METRICS, filter_report, metric_access, permissions
from ltef.engine import compare, evaluate
from ltef.metrics import catalog
from ltef.reporting import render
from ltef.requirements import load_upload, readiness as _readiness  # noqa: F401 (re-exported)
from ltef.schema import read_json, require

SAMPLE_SECTORS = ('finance', 'healthcare', 'public_sector')
DEMO_USER = {'id': 'demo', 'name': 'Demo Researcher', 'email': None, 'role': 'researcher'}
DEMO_TOKEN = 'public-demo'
MAX_ADHOC_TOKEN = 220_000  # generous headroom over any bundled sample's compressed size


def readiness(body):
    return _readiness(body)


_sample_reports = None


def sample_reports():
    """Lazily load the three committed synthetic sample reports (cached per warm invocation)."""
    global _sample_reports
    if _sample_reports is None:
        _sample_reports = {
            sector: read_json(ROOT / 'examples/reports' / sector / 'report.json')
            for sector in SAMPLE_SECTORS
        }
    return _sample_reports


def sample_id(sector):
    require(sector in SAMPLE_SECTORS, 'Unknown sector')
    return 'sample:' + sector


def _summary(rid, name, report, shared_sample):
    return {'id': rid, 'name': name, 'sector': report['profile']['sector'],
            'created_utc': report['created_utc'], 'evidence_class': report['evidence_class'],
            'cases': len(report['manifest']['selected_case_ids']), 'systems': len(report['systems']),
            'trials': report['manifest']['trials'], 'shared_sample': shared_sample}


def sample_listing():
    return [_summary(sample_id(sector), sector.replace('_', ' ').title() + ' · sample evaluation',
                      report, True)
            for sector, report in sample_reports().items()]


def bootstrap_payload(user):
    available = metric_access(user, catalog())
    metrics = [dict(m, accessible=m['id'] in available,
                    required_role='viewer' if m['id'] in VIEWER_METRICS else 'researcher')
               for m in catalog()]
    return {'authenticated': bool(user), 'user': user, 'setup_required': False,
            'token': DEMO_TOKEN, 'runs': sample_listing() if user else [], 'metrics': metrics,
            'permissions': permissions(user), 'metric_access': available,
            'demo': True}


def encode_adhoc(report):
    payload = zlib.compress(json.dumps(report, ensure_ascii=False, allow_nan=False).encode('utf-8'), 9)
    token = 'adhoc:' + base64.urlsafe_b64encode(payload).decode('ascii')
    require(len(token) <= MAX_ADHOC_TOKEN, 'Evaluation result is too large for the stateless public demo')
    return token


def decode_adhoc(token):
    try:
        raw = zlib.decompress(base64.urlsafe_b64decode(token.encode('ascii')))
        return json.loads(raw)
    except Exception:
        raise LookupError('Evaluation not found')


def resolve_run(run_id, user):
    if run_id.startswith('sample:'):
        sector = run_id[len('sample:'):]
        if sector not in SAMPLE_SECTORS:
            raise LookupError('Evaluation not found')
        report = sample_reports()[sector]
        name = sector.replace('_', ' ').title() + ' · sample evaluation'
        shared = True
    elif run_id.startswith('adhoc:'):
        report = decode_adhoc(run_id[len('adhoc:'):])
        name = 'Untitled evaluation'
        shared = False
    else:
        raise LookupError('Evaluation not found')
    if user is not None:
        report = filter_report(report, metric_access(user, catalog()))
    return {'id': run_id, 'name': name, 'report': report, 'shared_sample': shared}


def run_comparison(run_id, baseline, candidate, user):
    run = resolve_run(run_id, user)
    return compare(run['report'], baseline, candidate)


def run_export(run_id, user, markdown=False):
    run = resolve_run(run_id, user)
    return render(run['report']) if markdown else run['report']


def new_evaluation(body, user):
    require(isinstance(body, dict), 'Request must be a JSON object')
    name = body.get('name', 'Untitled evaluation')
    require(isinstance(name, str) and 1 <= len(name.strip()) <= 120, 'Name must contain 1–120 characters')
    if body.get('mode') == 'demo':
        sector = body.get('sector')
        require(sector in SAMPLE_SECTORS, 'Unknown sector')
        return resolve_run(sample_id(sector), user)
    require(body.get('mode') == 'upload', 'Unknown evaluation mode')
    cases, bundle, profile = load_upload(body)
    report = evaluate(cases, bundle, profile)
    token = encode_adhoc(report)
    result = resolve_run(token, user)
    result['name'] = name.strip()
    return result
