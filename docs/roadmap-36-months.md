# Revised 36-month LTEF implementation and validation roadmap

Drafted September 16, 2026. Month 1 begins when you commit the project scope and actual time/resources; this document does not backdate development. Multi-agent evaluation is an explicit extension to the original LLM-focused endeavor.

## What exists at the starting point

Local v0.1 scoring engine; 18 metric definitions/scorers; three uncalibrated sector profiles; synthetic fixtures; per-case and aggregate reports; paired comparisons; corrected NIST relevance mappings; validation tests. No public release, external pilot, live-model result, or calibrated sector acceptance threshold is claimed.

## Proposed sequence and measurable gates

| Period | Work | Reviewable deliverables | Gate before expansion |
|---|---|---|---|
| Months 1–3 | Freeze definitions, choose initial sector/use case, implement selected provider adapters, validate deterministic scorers and trace contract | Specification v1; data/rubric cards; reproducible live baseline; complete request/error accounting | Demonstrate that reported scores agree with independently checked example outcomes; resolve the papers' mapping/methodology issues |
| Months 4–6 | Build representative initial-sector development and held-out sets; establish annotation procedure; compare at least two model configurations if resources permit | Versioned dataset with rights/provenance; reviewer disagreement analysis; model comparison report with coverage and uncertainty | Document reference/annotation validity, feasible sample sizes, reproducible runs, and known measurement limitations |
| Months 7–9 | Add executable isolated single-agent and two-agent scenarios; integrate full event capture; test handoffs, permissions, failures, and retries | Trace adapter; controlled fault-injection fixtures; permission/task checks; resource accounting | Demonstrate capture completeness on instrumented scenarios and distinguish agent success from policy compliance |
| Months 10–12 | Controlled single-agent versus multi-agent evaluation; first research release and technical manuscript submission | Reproducible experiment package; equal-task and budget-aware comparisons; documented limitations; release candidate | Independent reproduction by a collaborator where available; no unsupported claims of superiority or adoption |
| Months 13–18 | Deepen first-sector calibration and pilot, subject to genuine partner interest; improve reference/semantic evaluation | Sector expert review; agreed pilot protocol if a partner commits; held-out results; error taxonomy | Demonstrate usefulness in a specific decision workflow, not just benchmark improvement |
| Months 19–24 | Adapt to the second and third sectors with domain-specific cases and reviewers; expand indirect-injection and multi-turn agent tests | Separate sector dataset cards, rubrics, calibration reports, and comparison results | Evaluate each sector independently; do not transfer thresholds without evidence |
| Months 25–30 | Longitudinal model/version monitoring; stronger multi-agent causal analyses; human–AI interaction study if feasible | Drift protocol; repeated snapshots; propagation/recovery analyses; study protocol and results when conducted | Validate whether metrics track relevant outcomes and identify failure modes missed by proxies |
| Months 31–36 | External reproducibility, hardening, dissemination and possible standards submissions | Versioned stable research release; independent replication reports; educational materials; documented submissions | Report actual external decisions accurately; distinguish submission, review, acceptance, adoption and endorsement |

These are planned milestones, not guaranteed publication or partner outcomes. Advance based on evidence and available resources. A review manuscript alone does not establish validity of a runtime metric.

## Multi-agent metric development stages

**Implemented operational baseline:** externally judged task success; handoff receipt fraction; episodes with unauthorized tool attempts/executions; recorded step-budget exceedance; canary exposure in event content; externally judged propagation; request-level latency/tokens/cost.

**Months 7–12:** executable tool argument/policy validators, final-state verifiers, termination reasons, agent-local versus end-to-end latency, retries, communication volume, outcome agreement/disagreement, controlled error-injection and recovery scenarios. Compare these against single-agent baselines with the same task and an explicit budget.

**Months 13–24:** privilege escalation across handoffs, indirect-injection transfer, memory contamination, recovery after a faulty agent, cost per successful policy-compliant task, and controlled coordination ablations. Metrics need case definitions and validated instrumentation before scores are published.

**Months 25–36:** causal propagation attribution, robustness under agent replacement/failure, human intervention effectiveness, and longitudinal reliability. Treat causal and human-outcome claims as studies, not automatic trace statistics.

## Required resource decisions

- Confirm the first sector and one initial use case. The code supports all three profiles, but deep validation should start with one.
- Record your actual weekly availability, budget, API/model access, compute, and storage.
- Identify who can independently review sector labels; healthcare research needs appropriately qualified expertise for clinical claims.
- Decide what existing artifacts can be published and what is employer-owned or confidential.
- Define dataset permissions, annotation access, release scope, and reproducibility responsibilities.
- Set study-specific sample sizes and acceptance criteria before looking at held-out results.

The code is intentionally provider-neutral until these choices are made. No live API costs or external messages were incurred in creating it.

## Changes to the original plan

Move reproducible implementation and evidence of progress to the front. Introduce multi-agent traces and controlled experiments during year one instead of appending vague agent metrics in year three. Validate one sector before scaling to three. Replace promised journal acceptance or standards integration with controllable submissions and actual documented outcomes. Separate reporting thresholds from scientifically validated acceptance criteria. Reserve human-overreliance claims for a real human study.

## Evidence to retain at each milestone

Keep dated specifications, immutable code versions, dataset/rubric versions, model and orchestration metadata, run manifests, raw observations in controlled storage, failed runs, reports, test outputs, reviewer records, and actual external correspondence. Describe a local prototype as local until publicly released. Describe synthetic demonstrations as synthetic until real experiments exist.
