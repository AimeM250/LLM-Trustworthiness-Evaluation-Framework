"""Strict boundary validation for auditable offline evaluations."""

import hashlib
import json
import math
from pathlib import Path


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=lambda v: (_ for _ in ()).throw(ValidationError("Non-finite JSON number")))
    except (ValueError, OSError) as exc:
        raise ValidationError(f"Cannot read JSON {path}: {exc}") from exc


def read_cases(path):
    cases = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(json.loads(line, object_pairs_hook=_unique_object))
        except ValueError as exc:
            raise ValidationError(f"Invalid case JSON at line {line_no}: {exc}") from exc
    validate_cases(cases)
    return cases


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_cases(cases):
    require(isinstance(cases, list) and cases, "Dataset must be a nonempty list")
    ids, pairs = set(), {}
    for c in cases:
        require(isinstance(c, dict), "Each case must be an object")
        require(c.get("schema_version") == 1, "Case schema_version must be 1")
        require(text(c.get("id")) and c["id"] not in ids, "Case IDs must be nonempty and unique")
        ids.add(c["id"])
        require(c.get("sector") in {"healthcare", "finance", "public_sector"}, "Unknown sector")
        require(text(c.get("source")), "Case needs source/provenance")
        require(type(c.get("synthetic")) is bool, "Case needs explicit synthetic boolean")
        messages = c.get("messages")
        require(isinstance(messages, list) and messages, "Case needs messages")
        for m in messages:
            require(isinstance(m, dict) and m.get("role") in {"system", "user", "assistant"}
                    and text(m.get("content")), "Invalid message")
            require(set(m) == {"role", "content"}, "Message supports role/content only")
        ref = c.get("reference")
        if ref is not None:
            require(isinstance(ref, dict), "reference must be an object")
            require(ref.get("type") in {"exact", "numeric"}, "Unsupported reference type")
            if ref["type"] == "exact":
                require(isinstance(ref.get("answers"), list) and ref["answers"]
                        and all(text(v) for v in ref["answers"]), "Exact reference needs nonempty answers")
            else:
                require(number(ref.get("value")), "Numeric reference value must be finite")
                for key in ("absolute_tolerance", "relative_tolerance"):
                    require(number(ref.get(key, 0)) and ref.get(key, 0) >= 0, "Invalid numeric tolerance")
        require(isinstance(c.get("groups", {}), dict)
                and all(text(k) and text(v) for k, v in c.get("groups", {}).items()), "Invalid groups")
        require(isinstance(c.get("canaries", []), list)
                and all(text(v) and len(v) >= 8 for v in c.get("canaries", [])), "Canaries must have >=8 characters")
        for flag in ("attack", "benign", "requires_escalation"):
            require(type(c.get(flag, False)) is bool, f"{flag} must be boolean")
        require(not (c.get("attack") and c.get("benign")), "Case cannot be both attack and benign")
        if "pair_id" in c:
            require(text(c["pair_id"]) and text(c.get("pair_variant")), "Counterfactual pair needs ID and variant")
            pairs.setdefault(c["pair_id"], []).append(c)
        policy = c.get("agent_policy")
        if policy is not None:
            require(isinstance(policy, dict) and isinstance(policy.get("allowed_tools"), dict)
                    and policy["allowed_tools"], "agent_policy needs allowed_tools by agent")
            for agent, tools in policy["allowed_tools"].items():
                require(text(agent) and isinstance(tools, list) and all(text(t) for t in tools), "Invalid allowed tools")
            require(type(policy.get("max_steps")) is int and policy["max_steps"] > 0, "Invalid max_steps")
    for pid, members in pairs.items():
        require(len(members) == 2 and len({c["pair_variant"] for c in members}) == 2,
                f"Pair {pid} must have exactly two variants")
        require(members[0]["sector"] == members[1]["sector"] and members[0].get("reference") is not None
                and members[0].get("reference") == members[1].get("reference"),
                f"Pair {pid} must have same sector and nonempty reference")


def validate_trace(trace, case):
    require(isinstance(trace, dict) and type(trace.get("complete")) is bool,
            "Trace must declare complete boolean")
    events = trace.get("events")
    require(isinstance(events, list), "Trace events must be a list")
    policy = case.get("agent_policy")
    require(policy is not None, "Trace requires evaluator-defined agent_policy")
    agents = set(policy["allowed_tools"])
    ids, handoffs, received = set(), {}, set()
    last_time = -1
    for i, e in enumerate(events):
        require(isinstance(e, dict) and text(e.get("id")) and e["id"] not in ids,
                "Unique event ID required")
        require(type(e.get("step")) is int and e["step"] == i, "Trace steps must be contiguous from 0")
        require(number(e.get("time_ms")) and e["time_ms"] >= last_time, "Trace time must be finite and monotonic")
        last_time = e["time_ms"]
        require(e.get("agent") in agents, "Unknown trace agent")
        require(e.get("kind") in {"message", "handoff", "receive", "tool", "finish"}, "Unknown event kind")
        if "parent_id" in e:
            require(e["parent_id"] in ids, "Trace parent must precede child")
        require(isinstance(e.get("content", ""), str), "Event content must be text")
        if e["kind"] == "tool":
            require(text(e.get("tool")) and type(e.get("executed")) is bool,
                    "Tool event needs tool and executed flag")
        if e["kind"] == "handoff":
            require(e.get("to") in agents and e["to"] != e["agent"], "Invalid handoff target")
            handoffs[e["id"]] = e
        if e["kind"] == "receive":
            hid = e.get("handoff_id")
            require(hid in handoffs and hid not in received, "Receive needs unique preceding handoff")
            require(e["agent"] == handoffs[hid]["to"], "Wrong handoff recipient")
            received.add(hid)
        ids.add(e["id"])


def validate_bundle(bundle, cases):
    require(isinstance(bundle, dict) and bundle.get("schema_version") == 1, "Bundle schema_version must be 1")
    require(type(bundle.get("trials")) is int and 1 <= bundle["trials"] <= 1000, "trials must be 1..1000")
    systems = bundle.get("systems")
    require(isinstance(systems, list) and systems, "Declare systems even if their runs failed")
    system_ids = set()
    for s in systems:
        require(isinstance(s, dict) and all(text(s.get(k)) for k in ("id", "provider", "model", "version")),
                "System needs id/provider/model/version")
        require(s["id"] not in system_ids, "Duplicate system ID")
        require(isinstance(s.get("generation"), dict), "System needs recorded generation settings")
        require(s.get("kind") in {"llm", "multi_agent"}, "System kind must be llm or multi_agent")
        system_ids.add(s["id"])
    require(isinstance(bundle.get("records"), list), "Bundle records must be a list")
    by_id = {c["id"]: c for c in cases}
    seen = set()
    for r in bundle["records"]:
        require(isinstance(r, dict), "Observation must be an object")
        require(r.get("case_id") in by_id and r.get("system_id") in system_ids, "Unknown case/system ID")
        require(type(r.get("trial")) is int and 0 <= r["trial"] < bundle["trials"], "Invalid trial")
        key = (r["system_id"], r["case_id"], r["trial"])
        require(key not in seen, "Duplicate system/case/trial observation")
        seen.add(key)
        c = by_id[r["case_id"]]
        require(r.get("prompt_sha256") == digest(c["messages"]), "Observation prompt hash does not match case")
        require(r.get("status") in {"ok", "error"}, "Observation status must be ok/error")
        require(r.get("provenance") in {"synthetic", "captured"}, "Observation provenance required")
        if r["status"] == "ok":
            require(isinstance(r.get("response"), str), "Successful observation needs response")
        else:
            require(text(r.get("error_type")), "Failed observation needs error_type")
            require(not r.get("annotations") and not r.get("trace"), "Failed observations cannot carry scored annotations/traces")
        for k in ("latency_ms", "cost_usd", "input_tokens", "output_tokens", "confidence"):
            if k in r:
                require(number(r[k]) and r[k] >= 0, f"Invalid {k}")
        for k in ("input_tokens", "output_tokens"):
            if k in r:
                require(type(r[k]) is int, "Token counts must be integers")
        require(r.get("confidence", 0) <= 1, "confidence must be <=1")
        ann = r.get("annotations")
        if ann is not None:
            require(isinstance(ann, dict), "Annotations must be an object")
            require(ann.get("method") in {"human", "programmatic", "model_judge", "synthetic"}
                    and text(ann.get("evaluator")) and text(ann.get("rubric_version")),
                    "Annotations need method, evaluator and rubric_version")
            for k in ("unsafe", "refused", "escalated", "task_success", "propagated_error"):
                if k in ann:
                    require(type(ann[k]) is bool, f"Annotation {k} must be boolean")
            if "claims" in ann:
                require(isinstance(ann["claims"], list), "claims must be a list")
                for claim in ann["claims"]:
                    require(isinstance(claim, dict) and text(claim.get("text"))
                            and claim.get("label") in {"supported", "contradicted", "unverifiable"}
                            and text(claim.get("evidence")), "Claim needs text, label and evidence reference")
            if "clinical_errors" in ann:
                require(isinstance(ann["clinical_errors"], list)
                        and all(e in {"minor", "major"} for e in ann["clinical_errors"]), "Invalid clinical error labels")
        if "trace" in r:
            validate_trace(r["trace"], c)


def validate_profile(profile, metric_ids):
    require(isinstance(profile, dict) and profile.get("schema_version") == 1, "Profile schema_version must be 1")
    require(text(profile.get("id")) and text(profile.get("version")), "Profile ID/version required")
    require(profile.get("sector") in {"healthcare", "finance", "public_sector"}, "Unknown profile sector")
    require(isinstance(profile.get("metrics"), list) and profile["metrics"]
            and all(m in metric_ids for m in profile["metrics"]), "Unknown or empty profile metrics")
    require(len(profile["metrics"]) == len(set(profile["metrics"])), "Duplicate profile metrics")
    require(type(profile.get("minimum_cases")) is int and profile["minimum_cases"] >= 2, "minimum_cases must be >=2")
    require(profile.get("thresholds") == {}, "v0.1 profiles must have empty thresholds; validation gates are not calibrated")
    require(isinstance(profile.get("group_dimensions"), list)
            and all(text(k) for k in profile["group_dimensions"]), "group_dimensions required")
