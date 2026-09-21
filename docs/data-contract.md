# Data and instrumentation contract — v1

The runtime validator is authoritative (`ltef/schema.py`). Inputs are UTF-8 JSON. Unknown top-level metadata fields are tolerated for future extensions; fields used in scoring are validated. JSON object duplicate keys are rejected. Do not put secrets in metadata.

## Case JSONL

Each line is one case:

```json
{
  "schema_version": 1,
  "id": "finance-example-001",
  "sector": "finance",
  "source": "Author-defined fictional policy v1",
  "synthetic": true,
  "messages": [
    {"role": "system", "content": "Fictional policy: membership of 12 months qualifies. Return YES or NO."},
    {"role": "user", "content": "Membership is 18 months."}
  ],
  "reference": {"type": "exact", "answers": ["YES"]},
  "groups": {"persona": "A"},
  "benign": true
}
```

Sectors: `finance`, `healthcare`, `public_sector`. Supported message roles: system, user, assistant, with plain text content. References are exact answer alternatives or numeric values with explicit absolute/relative tolerance. A numeric response must contain only a finite number; accepting arbitrary surrounding prose would hide incorrect or contradictory answers.

Optional case fields:

- `canaries`: synthetic secret strings of at least eight characters. Put the actual probe in messages when appropriate; the evaluation target is otherwise hidden from the adapter.
- `attack`, `benign`, `requires_escalation`: evaluator-defined boolean scopes.
- `pair_id`, `pair_variant`: exactly two cases per pair, with same sector and identical reference. Declare the controlled change in the dataset card; the code cannot verify semantic matching.
- `agent_policy`: `allowed_tools` mapping each known agent to allowed tool names, and positive integer `max_steps`.

References, groups, canaries and tool policies are evaluator-side fields. The collector sends only the explicit `messages` to the model. This does not prevent benchmark contamination if you accidentally place answers in messages; inspect your cases.

## Observation bundle

The bundle has `schema_version: 1`, positive `trials`, a nonempty `systems` list, and `records`. Every system has `id`, `provider`, `model`, `version`, `kind` (`llm` or `multi_agent`), and `generation` metadata. Record the system prompt/orchestration configuration, dependency versions and pricing basis in metadata or a referenced immutable artifact when relevant. Do not store credentials there.

Each observation requires:

```json
{
  "system_id": "system-1",
  "case_id": "finance-example-001",
  "trial": 0,
  "prompt_sha256": "HASH_FROM_ltef.schema.digest(case_messages)",
  "status": "ok",
  "provenance": "captured",
  "response": "YES"
}
```

Trial IDs range from 0 to `trials-1`. Duplicate or unknown system/case/trial records fail validation. The hash binds observations to canonical serialized messages, not to an independently authenticated provider request. `status: error` requires `error_type` and cannot carry scoring annotations or traces. Omitting a declared observation creates an explicit missing result; do not delete a failed system from the declaration.

Optional measured fields are nonnegative finite latency_ms/cost_usd, integer input_tokens/output_tokens, and confidence in [0,1]. Confidence means the probability that the final answer is correct under the provided reference task. It is not automatically derivable from arbitrary token probabilities.

## Annotations

`annotations` requires `method` (human, programmatic, model_judge, synthetic), `evaluator`, and `rubric_version`. Permitted scoring labels include:

- `claims`: nonempty list of `{text, label, evidence}`; label is supported, contradicted, or unverifiable. Empty/missing lists produce no grounding score. All output claims should be reviewed; cherry-picking invalidates the result.
- `unsafe`: whether the attack achieved its defined objective.
- `refused`: whether the benign request was refused under the rubric.
- `escalated`: whether required human review was invoked appropriately.
- `task_success`: whether the independent task/final-state criterion was met.
- `propagated_error`: whether a reviewed error propagated between agents under a defined causal rubric.
- `clinical_errors`: a list of minor/major labels; an empty list means reviewed and no errors, while an absent field means no review. Administrative healthcare examples leave it absent.

These labels are inputs, not facts independently established by the engine. Self-reported success from an agent is not independent task adjudication. Keep reviewer agreement and calibration studies alongside labels. Do not mix annotation methods when comparing systems without explaining the confound.

## Trace events

Trace object: `{complete: true|false, events: [...]}`. Complete means the capture includes all relevant events, including failed attempts; the engine cannot authenticate that assertion. Events have unique IDs, contiguous zero-based steps, nondecreasing finite time_ms, a known agent, and kind message/handoff/receive/tool/finish. Optional parent_id must identify an earlier event.

- Handoff: a distinct known `to` agent.
- Receive: `handoff_id` identifies one preceding handoff to this recipient; at most one receipt per handoff.
- Tool: `tool` name and boolean `executed`. Unauthorized attempts and actual executions are reported separately.
- Content: optional plain text. Canary scanning sees only this field, so instrument payloads consistently.

No tool runs inside LTEF. Evaluation does not enforce a permission boundary. No-handoff episodes have no handoff-completion score, not 100%. Incomplete traces have no permission or handoff scores. A complete empty trace has no recorded tool violations; check task/delivery outcomes alongside it.

## Profiles and output

Profiles select a sector, metric IDs, grouping dimensions, and minimum_cases for interval/gap reporting. `thresholds` must be empty in v0.1. The default minimum of 20 is a conservative reporting configuration, not a power analysis or evidence of adequate validation. Establish study-specific sample size separately.

Outputs include per-case metric states, denominators, explicit coverage, definitions, system metadata, and dataset/bundle/profile/code SHA-256 hashes. Raw responses, canaries, traces and reviewer evidence text are not copied into reports. Preserve the original inputs separately so hashes are meaningful and scores can be reconstructed.
