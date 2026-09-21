"""Input guidance, synthetic starter bundles, and non-persistent readiness checks."""

from collections import Counter
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .engine import evaluate
from .metrics import METRICS
from .schema import ValidationError, _unique_object, digest, read_cases, read_json, require


ROOT = Path(__file__).resolve().parent.parent
SECTORS = {"finance", "healthcare", "public_sector"}
ANNOTATION_FIELDS = ["annotations.method", "annotations.evaluator", "annotations.rubric_version"]
TRACE_FIELDS = ["case.agent_policy.allowed_tools", "case.agent_policy.max_steps",
                "trace.complete = true", "trace.events"]


def parse_json(value):
    return json.loads(value, object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValidationError("Non-finite JSON number")))


def data_requirements():
    """Describe executable requirements; these do not authenticate supplied evidence."""
    details = {
        "reference_accuracy": (["case.reference", "response"],
            "Provide accepted exact answers or a numeric value with tolerances. LTEF compares the final response using the reference; it does not grade free-form meaning.", "Cases with a reference answer."),
        "supported_claim_fraction": (["annotations.claims[].text", "annotations.claims[].label", "annotations.claims[].evidence"] + ANNOTATION_FIELDS,
            "Supply a nonempty reviewed claim list, evidence references, and supported / contradicted / unverifiable labels. LTEF counts the supplied labels; it does not verify the sources.", "Any successful response with claim review; absent or empty review is missing."),
        "major_clinical_error_rate": (["annotations.clinical_errors"] + ANNOTATION_FIELDS,
            "Supply a clinical review using minor / major labels. An explicit empty list means reviewed with no identified errors. LTEF checks for a major label; qualified clinical review is external.", "Healthcare cases only."),
        "canary_disclosure_rate": (["case.canaries", "response"],
            "Define synthetic probe strings of at least eight characters. LTEF searches the normalized response for exact probe text. Use fictional secrets, never real credentials.", "Cases with at least one canary probe."),
        "attack_success_rate": (["case.attack = true", "annotations.unsafe"] + ANNOTATION_FIELDS,
            "Mark the adversarial cases and supply an unsafe outcome label under a documented attack rubric. LTEF averages these labels; it does not infer safety from wording.", "Cases marked as attacks."),
        "benign_refusal_rate": (["case.benign = true", "annotations.refused"] + ANNOTATION_FIELDS,
            "Mark legitimate requests and supply a refusal label. Define what counts as a refusal in the rubric. A case cannot be both benign and an attack.", "Cases marked benign."),
        "escalation_rate": (["case.requires_escalation = true", "annotations.escalated"] + ANNOTATION_FIELDS,
            "Identify cases that require human escalation and supply a label for whether it occurred. LTEF measures labeled behavior, not the downstream human outcome.", "Cases marked as requiring escalation."),
        "brier_score": (["case.reference", "response", "confidence"],
            "Record confidence from 0 to 1 as the probability that the final answer is correct. LTEF squares the difference between confidence and reference correctness.", "Cases with a reference answer."),
        "latency_ms": (["latency_ms"],
            "Measure and supply nonnegative end-to-end request time in milliseconds. Failed requests can contribute when timing is recorded.", "All requested case/system/trial combinations."),
        "total_tokens": (["input_tokens", "output_tokens"],
            "Supply both nonnegative integer token counts from the run. LTEF adds them. Record the tokenizer or provider usage basis in generation metadata.", "All requested combinations, including failed requests with usage."),
        "cost_usd": (["cost_usd", "systems[].generation (pricing basis)"],
            "Supply actual or explicitly estimated nonnegative request cost in USD and document the pricing basis in generation metadata. LTEF does not calculate pricing from tokens.", "All requested combinations, including failed requests with cost."),
        "task_success_rate": (["case.agent_policy", "annotations.task_success"] + ANNOTATION_FIELDS,
            "Define the agent policy and independently judge the final task state under a versioned rubric. LTEF averages supplied success labels. A trace is recommended for review but is not required by this metric.", "Cases with an agent policy."),
        "unauthorized_tool_attempt_rate": (TRACE_FIELDS + ["trace.events[].tool", "trace.events[].executed"],
            "Instrument complete episodes and supply each agent's allowed tool names. LTEF flags episodes with any tool call outside that agent's allowlist, whether executed or blocked.", "Cases with an agent policy and complete trace."),
        "unauthorized_tool_execution_rate": (TRACE_FIELDS + ["trace.events[].tool", "trace.events[].executed"],
            "Record truthful executed flags for tool events. LTEF flags episodes containing an executed tool outside that agent's allowlist. It does not enforce permissions or inspect tool arguments.", "Cases with an agent policy and complete trace."),
        "handoff_completion_rate": (TRACE_FIELDS + ["handoff events: id, to", "receive events: handoff_id"],
            "Record sends and matching receipts with correct recipient identities and causal event order. LTEF divides receipts by sends per episode; no handoffs means not applicable.", "Agent episodes with a complete trace and at least one handoff."),
        "step_budget_exceedance_rate": (TRACE_FIELDS,
            "Set a positive maximum event budget before the run. LTEF compares the complete trace's event count with that budget; a step means one recorded event.", "Cases with an agent policy and complete trace."),
        "trace_canary_disclosure_rate": (TRACE_FIELDS + ["case.canaries", "trace.events[].content"],
            "Use synthetic probe strings and capture the event content being evaluated. LTEF searches recorded content for exact normalized probe text. Omitted channels are not assessed.", "Agent cases with canary probes and a complete trace."),
        "propagated_error_rate": (TRACE_FIELDS + ["annotations.propagated_error"] + ANNOTATION_FIELDS,
            "Supply an external causal review of whether an error propagated between agents, plus the complete source trace. LTEF averages the supplied label; it does not infer causality.", "Cases with an agent policy and complete trace."),
    }
    metrics = [dict(id=mid, title=metric.title, dimension=metric.dimension,
                    required_fields=details[mid][0], guidance=details[mid][1], applicability=details[mid][2])
               for mid, metric in METRICS.items()]
    common = [
        {"title": "Cases · what you test", "fields": ["schema_version = 1", "id", "sector", "source", "synthetic", "messages[].role", "messages[].content"],
         "guidance": "Provide one JSON object per line in cases.jsonl. IDs must be unique; messages use system, user, or assistant roles. Keep source provenance and explicitly identify synthetic examples."},
        {"title": "Observations · what actually happened", "fields": ["schema_version = 1", "trials", "systems[].id/provider/model/version/kind/generation", "records[].system_id/case_id/trial/prompt_sha256/status/provenance"],
         "guidance": "Provide observations.json. Trial indexes start at zero. Each successful record needs response; failures need error_type. Hash the exact case messages with ltef.schema.digest. Missing records remain missing. Captured provenance is your assertion, not provider verification."},
        {"title": "Profile · what to measure", "fields": ["schema_version = 1", "id", "version", "sector", "metrics", "minimum_cases", "thresholds = {}", "group_dimensions"],
         "guidance": "Provide profile.json with selected metric IDs. minimum_cases must be at least two; starter files use 20, which is a display threshold, not a statistical power calculation. Deployment pass/fail thresholds are not calibrated."},
        {"title": "Review and instrumentation · metric-specific evidence", "fields": ["annotations.method/evaluator/rubric_version (when annotations are supplied)", "trace.complete/events (for trace metrics)", "case.groups (for selected group dimensions)"],
         "guidance": "Supply only observed measurements and completed reviews. Every trace event needs a unique id, contiguous step from zero, nondecreasing time_ms, known agent, and kind. Missing labels or instrumentation cannot become a passing score."},
    ]
    return {"metrics": metrics, "common": common}


def load_upload(body):
    """Share parsing and expansion limits between preview and persisted evaluation."""
    require(isinstance(body, dict), "Request must be a JSON object")
    require(all(isinstance(body.get(k), str) for k in ("cases", "observations", "profile")), "Provide all three input files")
    cases = []
    for line_no, line in enumerate(body["cases"].splitlines(), 1):
        if line.strip():
            try:
                cases.append(parse_json(line))
            except (ValueError, TypeError) as exc:
                raise ValidationError(f"cases.jsonl line {line_no}: {exc}") from exc
    parsed = {}
    for key in ("observations", "profile"):
        try:
            parsed[key] = parse_json(body[key])
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"{key}.json: {exc}") from exc
    bundle = parsed["observations"]
    require(isinstance(bundle, dict), "Observations must be an object")
    systems, trials = bundle.get("systems"), bundle.get("trials")
    require(isinstance(systems, list) and type(trials) is int and trials >= 1, "Declare systems and positive trials")
    require(len(cases) <= 2000 and len(cases) * len(systems) * trials <= 10000,
            "Web evaluations support 2,000 cases and 10,000 case/system/trial combinations; use the CLI for larger datasets")
    return cases, bundle, parsed["profile"]


def readiness(body):
    """Evaluate in memory solely to summarize input coverage; do not persist anything."""
    cases, bundle, profile = load_upload(body)
    report = evaluate(cases, bundle, profile)
    metrics = []
    warnings = []
    if report["evidence_class"] == "synthetic_demo":
        warnings.append("Synthetic examples are present. Results demonstrate scoring and are not evidence of real model performance.")
    else:
        warnings.append("Imported observations and reviewer labels are supplied evidence; LTEF does not authenticate their origin or correctness.")
    for mid in profile["metrics"]:
        states = Counter(row["metrics"][mid]["state"] for row in report["case_results"])
        eligible = len(report["case_results"]) - states["not_applicable"]
        metrics.append({"id": mid, "title": METRICS[mid].title, "scored": states["scored"],
                        "eligible": eligible, "missing": states["missing"], "error": states["error"],
                        "not_applicable": states["not_applicable"],
                        "coverage": states["scored"] / eligible if eligible else None})
        if not eligible:
            warnings.append(f"{METRICS[mid].title}: no applicable cases or opportunities in this dataset.")
        elif states["missing"] or states["error"]:
            warnings.append(f"{METRICS[mid].title}: {states['missing']} missing and {states['error']} failed measurements out of {eligible} eligible combinations.")
    if any(summary["status"] == "insufficient_cases" for system in report["systems"].values() for summary in system["metrics"].values()):
        warnings.append(f"Some metrics have fewer than {profile['minimum_cases']} scored cases per system. Their confidence intervals will be withheld; this threshold is not a power analysis.")
    outside = len(cases) - len(report["manifest"]["selected_case_ids"])
    if outside:
        warnings.append(f"The profile selects {profile['sector']}; {outside} cases in other sectors will not be scored.")
    warnings.append("Valid files can still contain missing evidence. Coverage counts case/system/trial combinations across all declared systems; it is not a quality score.")
    return {"valid": True, "evidence_class": report["evidence_class"],
            "case_count": len(report["manifest"]["selected_case_ids"]), "system_count": len(bundle["systems"]),
            "trials": bundle["trials"], "metrics": metrics, "warnings": warnings}


def starter_bundle(sector="finance", metric_ids=None):
    require(sector in SECTORS, "Unknown sector")
    if metric_ids is None:
        metric_ids = [mid for mid in METRICS if mid != "major_clinical_error_rate" or sector == "healthcare"]
    require(isinstance(metric_ids, list) and metric_ids and all(mid in METRICS for mid in metric_ids), "Choose at least one known metric")
    require(len(metric_ids) == len(set(metric_ids)), "Duplicate metric selection")
    cases = [case for case in read_cases(ROOT / "examples/cases.jsonl") if case["sector"] == sector]
    by_id = {case["id"]: case for case in cases}
    bundle = read_json(ROOT / "examples/observations.json")
    bundle["records"] = [record for record in bundle["records"] if record["case_id"] in by_id]
    for record in bundle["records"]:
        record["prompt_sha256"] = digest(by_id[record["case_id"]]["messages"])
    profile = read_json(ROOT / "examples/profiles" / (sector + ".json"))
    profile["metrics"] = metric_ids
    readme = """# LTEF synthetic starter bundle

These are completed, fictional examples for learning the file format. They are
not blank collection forms, provider results, or validation evidence. Some records,
reviews, and opportunities are deliberately absent so you can see missingness.

1. Upload the three files unchanged to try the data check.
2. For your own study, create cases.jsonl with your prompts, references, source,
   and synthetic flag. Keep test scope and acceptance rubrics versioned.
3. Collect actual runs into observations.json. Replace fixture system identities,
   generation settings, records, response text, timings, usage, cost, provenance,
   and review labels. Never relabel a fictional record as captured.
4. After changing a prompt, calculate its hash with the canonical helper:

       from ltef.schema import digest
       record["prompt_sha256"] = digest(case["messages"])

   The hash binds a record to its prompt; it does not verify that the run happened.
5. Set metric choices and sector in profile.json. Keep thresholds empty.
6. Check the three files in Data requirements, fix structural errors, and inspect
   coverage warnings before creating an evaluation. A successful check saves no
   evaluation and makes no model/provider calls.

Supply review metadata (method, evaluator, rubric_version) with any annotations.
Clinical review, attack/refusal judgments, task success, and causal propagation
labels require external assessment. Instrument agent traces completely and use
only synthetic canary strings. Never invent unavailable measurements or reviews.

Read ltef/docs/data-contract.md and ltef/docs/measurement-protocol.md for the full
contract and formulas. The JSON schema validators remain authoritative.
"""
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("cases.jsonl", "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases))
        archive.writestr("observations.json", json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("profile.json", json.dumps(profile, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("README.md", readme)
    return output.getvalue()
