import copy
import json
from pathlib import Path
import tempfile
import unittest

from ltef.schema import read_cases, read_json, validate_cases, validate_bundle, ValidationError, digest
from ltef.metrics import score, accuracy, METRICS
from ltef.engine import evaluate, compare
from ltef.collection import collect
from ltef.reporting import save_report
from ltef.statistics import summarize
from ltef.cli import main

ROOT = Path(__file__).resolve().parents[1]


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.cases = read_cases(ROOT / "examples/cases.jsonl")
        self.bundle = read_json(ROOT / "examples/observations.json")
        self.profile = read_json(ROOT / "examples/profiles/finance.json")
        self.case = next(c for c in self.cases if c["id"] == "finance-4")
        self.record = next(r for r in self.bundle["records"] if r["case_id"] == "finance-4" and r["system_id"] == "fixture-baseline")

    def test_demo_has_known_outcomes_and_missingness(self):
        report = evaluate(self.cases, self.bundle, self.profile)
        self.assertEqual(report["evidence_class"], "synthetic_demo")
        baseline, candidate = report["systems"]["fixture-baseline"], report["systems"]["fixture-candidate"]
        self.assertEqual(candidate["metrics"]["reference_accuracy"]["value"], 1)
        self.assertEqual(candidate["metrics"]["canary_disclosure_rate"]["value"], 0)
        self.assertEqual(baseline["metrics"]["canary_disclosure_rate"]["value"], 1)
        self.assertEqual(baseline["delivery_rate"]["value"], 14 / 16)
        self.assertEqual(baseline["metrics"]["reference_accuracy"]["states"]["error"], 1)
        self.assertEqual(baseline["metrics"]["reference_accuracy"]["states"]["missing"], 1)
        self.assertIsNone(candidate["metrics"]["reference_accuracy"]["ci95_case_bootstrap"])
        self.assertEqual(candidate["metrics"]["reference_accuracy"]["status"], "insufficient_cases")

    def test_missing_annotations_never_pass(self):
        self.record.pop("annotations")
        self.assertEqual(score("attack_success_rate", self.case, self.record).state, "missing")

    def test_trace_privacy_scope_excludes_cases_without_canaries(self):
        self.case.pop("canaries")
        self.assertEqual(score("trace_canary_disclosure_rate", self.case, None).state, "not_applicable")

    def test_propagation_needs_source_trace(self):
        self.record.pop("trace")
        self.assertEqual(score("propagated_error_rate", self.case, self.record).state, "missing")

    def test_failed_calls_still_count_measured_resources(self):
        r = {"status": "error", "latency_ms": 100, "input_tokens": 10, "output_tokens": 0, "cost_usd": .02}
        self.assertEqual(score("cost_usd", self.case, r).value, .02)
        self.assertEqual(score("total_tokens", self.case, r).value, 10)
        self.assertEqual(score("latency_ms", self.case, r).value, 100)

    def test_comparison_pairs_trial_ids_before_averaging(self):
        report = evaluate(self.cases, self.bundle, self.profile)
        # Deliberately remove one scored trial on one side: it must not be paired with another trial.
        row = next(r for r in report["case_results"] if r["system_id"] == "fixture-candidate"
                   and r["case_id"] == "finance-0" and r["trial"] == 1)
        row["metrics"]["reference_accuracy"].update(state="missing", value=None)
        result = compare(report, "fixture-baseline", "fixture-candidate")
        self.assertEqual(result["metrics"]["reference_accuracy"]["paired_observations"], 13)

    def test_synthetic_annotations_taint_evidence_class(self):
        for c in self.cases:
            c["synthetic"] = False
        for r in self.bundle["records"]:
            r["provenance"] = "captured"
        report = evaluate(self.cases, self.bundle, self.profile)
        self.assertEqual(report["evidence_class"], "synthetic_demo")

    def test_empty_claims_never_pass(self):
        self.record["annotations"]["claims"] = []
        self.assertEqual(score("supported_claim_fraction", self.case, self.record).state, "missing")

    def test_numeric_reference_does_not_accept_extraneous_answer_or_nan(self):
        c = next(c for c in self.cases if c["id"] == "finance-2")
        self.assertEqual(accuracy(c, {"response": "10.0005"}), 1)
        self.assertEqual(accuracy(c, {"response": "It is 10"}), 0)
        self.assertEqual(accuracy(c, {"response": "nan"}), 0)

    def test_case_normalization_supports_unicode_and_whitespace(self):
        c = {"reference": {"type": "exact", "answers": ["Éligible now"]}}
        self.assertEqual(accuracy(c, {"response": "  E\u0301LIGIBLE  NOW "}), 1)

    def test_unauthorized_attempt_distinct_from_execution(self):
        for e in self.record["trace"]["events"]:
            if e["kind"] == "tool":
                e["executed"] = False
        self.assertEqual(score("unauthorized_tool_attempt_rate", self.case, self.record).value, 1)
        self.assertEqual(score("unauthorized_tool_execution_rate", self.case, self.record).value, 0)

    def test_incomplete_trace_is_missing_not_safe(self):
        self.record["trace"]["complete"] = False
        self.assertEqual(score("unauthorized_tool_execution_rate", self.case, self.record).state, "missing")

    def test_no_handoffs_not_one_hundred_percent(self):
        self.record["trace"]["events"] = []
        self.assertEqual(score("handoff_completion_rate", self.case, self.record).state, "not_applicable")

    def test_unreceived_handoff_scores_zero(self):
        self.record["trace"]["events"] = self.record["trace"]["events"][:1]
        self.assertEqual(score("handoff_completion_rate", self.case, self.record).value, 0)

    def test_duplicate_observation_rejected(self):
        self.bundle["records"].append(copy.deepcopy(self.record))
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)

    def test_wrong_prompt_rejected(self):
        self.record["prompt_sha256"] = "other"
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)

    def test_unknown_case_rejected(self):
        self.record["case_id"] = "not-a-case"
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)

    def test_nonfinite_measurement_and_boolean_token_count_rejected(self):
        self.record["latency_ms"] = float("inf")
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)
        self.record["latency_ms"] = 10
        self.record["input_tokens"] = True
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)

    def test_annotation_requires_provenance(self):
        del self.record["annotations"]["evaluator"]
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)

    def test_wrong_handoff_recipient_rejected(self):
        self.record["trace"]["events"][1]["agent"] = "planner"
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)

    def test_future_parent_and_duplicate_receive_rejected(self):
        self.record["trace"]["events"][0]["parent_id"] = "f"
        with self.assertRaises(ValidationError):
            validate_bundle(self.bundle, self.cases)

    def test_invalid_counterfactual_pair_rejected(self):
        self.cases[0]["reference"]["answers"] = ["different"]
        with self.assertRaises(ValidationError):
            validate_cases(self.cases)

    def test_case_weighting_does_not_overweight_repeated_trials(self):
        rows = [{"case_id": "A", "state": "scored", "value": 1}] * 10
        rows += [{"case_id": "B", "state": "scored", "value": 0}]
        result = summarize(rows, 2)
        self.assertEqual(result["value"], .5)
        self.assertEqual(result["cases_scored"], 2)

    def test_comparison_direction_and_pairs(self):
        report = evaluate(self.cases, self.bundle, self.profile)
        result = compare(report, "fixture-baseline", "fixture-candidate")
        self.assertLess(result["metrics"]["canary_disclosure_rate"]["candidate_minus_baseline"], 0)
        self.assertEqual(result["metrics"]["reference_accuracy"]["baseline_only_cases"], 0)
        self.assertEqual(result["metrics"]["reference_accuracy"]["candidate_only_cases"], 1)

    def test_unlabeled_groups_and_small_groups_not_fairness_pass(self):
        report = evaluate(self.cases, self.bundle, self.profile)
        self.assertIsNone(report["systems"]["fixture-candidate"]["groups"]["persona"]["max_min_gap"])

    def test_reports_do_not_include_raw_secret_or_output(self):
        report = evaluate(self.cases, self.bundle, self.profile)
        self.assertNotIn("SYNTHETIC-SECRET-FINANCE", json.dumps(report))
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "new"
            save_report(report, dest)
            self.assertTrue((dest / "report.md").exists())
            with self.assertRaises(FileExistsError):
                save_report(report, dest)

    def test_collector_hides_reference_and_retains_sanitized_failures(self):
        c = copy.deepcopy(self.case)
        def adapter(system, messages, trial):
            self.assertIsInstance(messages, list)
            self.assertEqual(set(messages[0]), {"role", "content"})
            raise RuntimeError("secret-api-key")
        result = collect([c], self.bundle["systems"][:1], adapter)
        self.assertEqual(result["records"][0]["error_type"], "RuntimeError")
        self.assertNotIn("secret-api-key", json.dumps(result))

    def test_no_synthetic_labels_from_adapter(self):
        result = collect([self.case], self.bundle["systems"][:1],
                         lambda *args: {"response": "WITHHELD", "annotations": {"unsafe": False}})
        self.assertEqual(result["records"][0]["status"], "error")

    def test_no_calibrated_thresholds_implied(self):
        self.profile["thresholds"] = {"reference_accuracy": .9}
        with self.assertRaises(ValidationError):
            evaluate(self.cases, self.bundle, self.profile)

    def test_all_failed_system_remains_in_report(self):
        self.bundle["records"] = []
        report = evaluate(self.cases, self.bundle, self.profile)
        s = report["systems"]["fixture-candidate"]
        self.assertEqual(s["delivery_rate"]["value"], 0)
        self.assertEqual(s["reference_success_intent_to_test"]["value"], 0)
        self.assertIsNone(s["metrics"]["reference_accuracy"]["value"])

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text('{"x": 1, "x": 2}')
            with self.assertRaises(ValidationError):
                read_json(path)


if __name__ == "__main__":
    unittest.main()
