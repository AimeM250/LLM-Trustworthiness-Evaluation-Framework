"""Python adapter boundary. No provider calls or external tool execution built in."""

import copy
import time

from .schema import digest, validate_bundle, validate_cases


def collect(cases, systems, adapter, trials=1):
    """adapter(system_metadata, messages, trial) -> response/usage dictionary.

    Receives messages only, never references, labels, canaries, or permission policies.
    The caller explicitly chooses a provider in their adapter. Calls are sequential;
    failed attempts are retained and not silently retried. External review/trace
    instrumentation must be attached separately before evaluation.
    """
    validate_cases(cases)
    bundle = {"schema_version": 1, "systems": systems, "trials": trials, "records": []}
    validate_bundle(bundle, cases)
    allowed = {"response", "input_tokens", "output_tokens", "cost_usd", "confidence"}
    for s in systems:
        for c in cases:
            for trial in range(trials):
                r = {"system_id": s["id"], "case_id": c["id"], "trial": trial,
                     "prompt_sha256": digest(c["messages"]), "provenance": "captured"}
                start = time.monotonic()
                try:
                    answer = adapter(copy.deepcopy(s), copy.deepcopy(c["messages"]), trial)
                    if not isinstance(answer, dict) or not isinstance(answer.get("response"), str):
                        raise ValueError("Adapter must return a response string")
                    if set(answer) - allowed:
                        raise ValueError("Adapter cannot supply evaluator annotations or traces")
                    r.update(answer)
                    r["status"] = "ok"
                except Exception as exc:
                    # Exception strings can contain provider keys/prompts. Record class only.
                    r.update(status="error", error_type=type(exc).__name__)
                r["latency_ms"] = (time.monotonic() - start) * 1000
                bundle["records"].append(r)
    validate_bundle(bundle, cases)
    return bundle
