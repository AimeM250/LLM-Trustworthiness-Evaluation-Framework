"""Portable JSON and human-readable Markdown; no raw model text in reports."""

import json
from pathlib import Path


def render(report):
    lines = ["# LTEF evaluation report", "", "Evidence class: **" + report["evidence_class"] + "**", "",
             "Profile: " + report["profile"]["id"] + " / " + report["profile"]["version"], "",
             "No sector acceptance thresholds have been calibrated. NIST references indicate relevance, not certification.", ""]
    def fmt(v):
        return "not measured" if v is None else f"{v:.4f}"
    for sid, result in report["systems"].items():
        lines += ["## " + sid, "", "| Metric | Value | Cases | Coverage | Status |", "|---|---:|---:|---:|---|"]
        summaries = dict(result["metrics"])
        for name in ("delivery_rate", "reference_success_intent_to_test", "all_trials_reference_success",
                     "repeated_output_exact_agreement", "counterfactual_output_exact_agreement"):
            summaries[name] = result[name]
        for mid, s in summaries.items():
            lines.append(f"| {mid} | {fmt(s['value'])} | {s['cases_scored']} | {fmt(s['coverage'])} | {s['status']} |")
        lines += ["", "Annotation methods: " + json.dumps(result["annotation_methods"], sort_keys=True), "",
                  "Subgroup and interval details, denominators, missingness, and per-case scores are in report.json.", ""]
    lines += ["## Interpretation limits", ""] + ["- " + t for t in report["limitations"]]
    lines += ["", "## Metric definitions and limitations", ""]
    for d in report["metric_definitions"]:
        lines += ["- **" + d["id"] + "** (" + d["direction"] + " is preferred): " + d["limitation"]]
    lines += ["", "## Provenance", "", "```json", json.dumps(report["manifest"], indent=2), "```", ""]
    return "\n".join(lines)


def save_report(report, output):
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)
    (path / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (path / "report.md").write_text(render(report), encoding="utf-8")
