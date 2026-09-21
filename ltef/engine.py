"""Evaluation and paired comparison of declared systems on fixed cases."""

from collections import defaultdict, Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import statistics

from . import __version__
from .schema import validate_cases, validate_bundle, validate_profile, digest, require
from .metrics import METRICS, catalog, score, normalize, accuracy
from .statistics import summarize, interval


def code_digest():
    sha = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        sha.update(path.name.encode())
        sha.update(path.read_bytes())
    return sha.hexdigest()


def evaluate(cases, bundle, profile):
    validate_cases(cases)
    validate_bundle(bundle, cases)
    validate_profile(profile, METRICS)
    selected = sorted([c for c in cases if c["sector"] == profile["sector"]], key=lambda c: c["id"])
    require(selected, "No cases for selected sector")
    observations = {(r["system_id"], r["case_id"], r["trial"]): r for r in bundle["records"]}
    results, case_results = {}, []
    minimum = profile["minimum_cases"]
    trials = bundle["trials"]
    for system in bundle["systems"]:
        sid = system["id"]
        rows = defaultdict(list)
        operational, effective_accuracy, all_trial_success, consistency = [], [], [], []
        ann_methods = Counter()
        for case in selected:
            responses, accuracies = [], []
            for trial in range(trials):
                record = observations.get((sid, case["id"], trial))
                delivered = record is not None and record["status"] == "ok"
                base = {"system_id": sid, "case_id": case["id"], "trial": trial}
                operational.append(dict(base, state="scored", value=float(delivered)))
                if "reference" in case:
                    a = accuracy(case, record) if delivered else 0.0
                    effective_accuracy.append(dict(base, state="scored", value=a))
                    accuracies.append(a)
                if delivered:
                    responses.append(normalize(record["response"]))
                    if record.get("annotations"):
                        ann_methods[record["annotations"]["method"]] += 1
                values = {}
                for mid in profile["metrics"]:
                    v = asdict(score(mid, case, record))
                    rows[mid].append(dict(base, **v))
                    values[mid] = v
                # Deliberately omit raw responses, traces, secret canaries and evidence text from reports.
                case_results.append(dict(base, status="missing" if record is None else record["status"], metrics=values))
            if accuracies:
                all_trial_success.append({"case_id": case["id"], "state": "scored", "value": float(all(accuracies))})
            if trials >= 2:
                consistency.append({"case_id": case["id"], "state": "scored" if len(responses) == trials else "missing",
                                    "value": float(len(set(responses)) == 1) if len(responses) == trials else None})
        metric_summaries = {mid: summarize(rows[mid], minimum) for mid in profile["metrics"]}
        group_results = {}
        for dim in profile["group_dimensions"]:
            group_rows = defaultdict(list)
            for case in selected:
                group = case.get("groups", {}).get(dim, "__unlabeled__")
                group_rows[group].extend(r for r in effective_accuracy if r["case_id"] == case["id"])
            groups = {g: summarize(v, minimum) for g, v in sorted(group_rows.items())}
            named = [v for g, v in groups.items() if g != "__unlabeled__"]
            adequate = len(named) >= 2 and all(v["cases_scored"] >= minimum for v in named)
            group_results[dim] = {
                "metric": "reference_success_intent_to_test", "groups": groups,
                "max_min_gap": max(v["value"] for v in named) - min(v["value"] for v in named) if adequate else None,
                "status": "descriptive" if adequate else "insufficient_groups_or_cases",
                "limitation": "Descriptive subgroup gap, not causal bias or fairness certification; case mix may differ.",
            }
        pairs = defaultdict(list)
        for c in selected:
            if c.get("pair_id"):
                pairs[c["pair_id"]].append(c)
        pair_rows = []
        for pid, members in pairs.items():
            for t in range(trials):
                records = [observations.get((sid, c["id"], t)) for c in members]
                ready = all(r is not None and r["status"] == "ok" for r in records)
                pair_rows.append({"case_id": pid, "trial": t, "state": "scored" if ready else "missing",
                                  "value": float(normalize(records[0]["response"]) == normalize(records[1]["response"])) if ready else None})
        results[sid] = {
            "system": system, "annotation_methods": dict(ann_methods), "metrics": metric_summaries,
            "delivery_rate": summarize(operational, minimum),
            "reference_success_intent_to_test": summarize(effective_accuracy, minimum),
            "all_trials_reference_success": summarize(all_trial_success, minimum),
            "all_trials_k": trials,
            "repeated_output_exact_agreement": summarize(consistency, minimum),
            "counterfactual_output_exact_agreement": summarize(pair_rows, minimum),
            "groups": group_results,
        }
    synthetic = any(c["synthetic"] for c in selected) or any(
        r["provenance"] == "synthetic" or r.get("annotations", {}).get("method") == "synthetic"
        for r in bundle["records"])
    return {
        "schema_version": 1, "ltef_version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_class": "synthetic_demo" if synthetic else "imported_observations_unverified",
        "manifest": {"dataset_sha256": digest(cases), "observations_sha256": digest(bundle),
                     "profile_sha256": digest(profile), "code_sha256": code_digest(),
                     "selected_case_ids": [c["id"] for c in selected], "trials": trials,
                     "bootstrap_seed": 1729, "bootstrap_samples": 1000},
        "profile": profile,
        "metric_definitions": [m for m in catalog() if m["id"] in profile["metrics"]],
        "systems": results, "case_results": case_results,
        "limitations": [
            "Research prototype: no global trust score or compliance certification.",
            "Synthetic examples demonstrate scoring behavior; they are not model, sector or clinical validation.",
            "Most means condition on measured observations. Check coverage; errors and missing runs remain in intent-to-test accuracy.",
            "Intervals resample case means, not trials; related cases may remain correlated. Small samples are descriptive only.",
            "Annotations and trace completeness are assertions from the data producer, not authenticated evidence.",
            "No human overreliance study, causal fairness conclusion, general semantic-factuality evaluator or full information-flow validation is implemented.",
        ],
    }


def compare(report, baseline, candidate):
    require(baseline != candidate, "Comparison needs different systems")
    require(baseline in report["systems"] and candidate in report["systems"], "Unknown comparison system")
    comparisons = {}
    a, b = report["systems"][baseline], report["systems"][candidate]
    for mid in a["metrics"]:
        measured = {}
        for sid in (baseline, candidate):
            measured[sid] = {(r["case_id"], r["trial"]): r["metrics"][mid]["value"]
                             for r in report["case_results"]
                             if r["system_id"] == sid and r["metrics"][mid]["state"] == "scored"}
        left, right = measured[baseline], measured[candidate]
        common = sorted(set(left) & set(right))
        by_case = defaultdict(list)
        for key in common:
            by_case[key[0]].append(right[key] - left[key])
        delta = [statistics.mean(v) for _, v in sorted(by_case.items())]
        comparisons[mid] = {
            "candidate_minus_baseline": statistics.mean(delta) if delta else None,
            "paired_cases": len(by_case), "paired_observations": len(common),
            "baseline_only_cases": len({k[0] for k in left} - {k[0] for k in right}),
            "candidate_only_cases": len({k[0] for k in right} - {k[0] for k in left}),
            "baseline_unpaired_observations": len(set(left) - set(right)),
            "candidate_unpaired_observations": len(set(right) - set(left)),
            "ci95_paired_case_bootstrap": interval(delta, report["profile"]["minimum_cases"]),
            "direction": METRICS[mid].direction,
        }
    return {"baseline": baseline, "candidate": candidate, "manifest": report["manifest"],
            "metrics": comparisons,
            "limitations": "Paired descriptive comparison on shared measured cases. Inspect missing/error coverage; no causal attribution or significance claim."}
