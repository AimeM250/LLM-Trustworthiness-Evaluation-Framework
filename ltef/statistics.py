"""Case-clustered summaries: repeated trials are not independent cases."""

from collections import defaultdict, Counter
import random
import statistics


def interval(values, minimum=5, seed=1729, samples=1000):
    if len(values) < minimum:
        return None
    rng = random.Random(seed)
    boot = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(samples))
    return [boot[int(.025 * (samples - 1))], boot[int(.975 * (samples - 1))]]


def summarize(rows, minimum):
    counts = Counter(r["state"] for r in rows)
    grouped = defaultdict(list)
    for r in rows:
        if r["state"] == "scored":
            grouped[r["case_id"]].append(r["value"])
    case_means = {k: statistics.mean(v) for k, v in sorted(grouped.items())}
    values = list(case_means.values())
    eligible = len(rows) - counts["not_applicable"]
    return {
        "value": statistics.mean(values) if values else None,
        "status": "not_measured" if not values else "insufficient_cases" if len(values) < minimum else "descriptive",
        "cases_scored": len(values), "observations_scored": counts["scored"],
        "eligible_observations": eligible,
        "coverage": counts["scored"] / eligible if eligible else None,
        "states": {s: counts[s] for s in ("scored", "missing", "error", "not_applicable")},
        "ci95_case_bootstrap": interval(values, minimum),
        "case_means": case_means,
        "weighting": "equal case weight; within case equal weight among scored trials",
    }
