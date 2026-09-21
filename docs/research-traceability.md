# Research-to-implementation traceability

The four supplied manuscripts are design inputs. Their review counts, submission status, bibliographies, and broad gap claims are not independently validated by this implementation. In particular, we use the final NIST AI RMF 1.0 mapping rather than P-4's incorrect category numbering.

| Manuscript | Useful design requirement | Implemented now | Still needs research / implementation |
|---|---|---|---|
| P-4: NIST MEASURE evaluation landscape | Reproducibility, multiple dimensions, comparable inputs, temporal tracking, sector reporting | Versioned data/profile/code hashes, metrics catalog, same-report paired comparison, repeated trials, sector filters | Semantic evaluators, longitudinal snapshot service, validated differentiators against existing tools |
| P-5: Clinical LLM evaluation | Grounding, privacy, clinical error severity, deployment-specific context, human interaction | Annotation-based claim/error metrics, synthetic canary tests, escalation proxy, healthcare research profile | Clinician-adjudicated datasets, clinical validation, actual human–AI outcome studies |
| P-6: Linguistic/demographic bias | Disaggregated results, controlled pairs, sufficient subgroup samples | Group summaries, missing-group accounting, paired exact response agreement | Valid multilingual/demographic datasets, semantic outcome comparisons, intersectional and causal analyses |
| P-7: Adversarial robustness | Explicit threat models, attack outcome definitions, utility retention, agentic threats | Attack/benign scopes, supplied attack labels, canary tests, recorded tool-policy analysis | Adaptive attack campaigns, separate indirect/multi-turn suites, executable isolated test environments |

## Corrected NIST alignment

The metadata labels are relevance mappings authored for LTEF, not NIST endorsement or a finding that a subcategory has been fully satisfied. MEASURE 2.5 concerns validity/reliability; 2.6 safety; 2.7 security/resilience; 2.10 privacy; 2.11 fairness/bias. MEASURE 2.13 concerns the effectiveness of evaluation methods themselves. LTEF's tests and future metric-validation studies are relevant to that last category; it is not a synonym for human–AI interaction. [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/).

## Multi-agent extension

The multi-agent metrics extend the papers' scope. They are not described as already validated by those reviews. We distinguish task outcomes, communication delivery, tool authority, trace-level disclosure, externally adjudicated error propagation, and resource usage. The distinction responds to failures of coordination and task verification discussed in [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657).

Repeated-trial reliability is motivated by agent benchmark practice, including [τ-bench](https://github.com/sierra-research/tau-bench). Our `all_trials_reference_success` is explicitly an empirical all-declared-trials statistic. It is not presented as a faithful implementation of every benchmark's pass^k estimator or as a τ-bench result.

## Position relative to existing frameworks

LTEF should reuse and compare against appropriate existing work rather than claim the absence of evaluation tooling. The supplied P-4 text itself discusses HELM, TrustLLM, DecodingTrust, and MLCommons AIS/AILuminate. The earlier correction about omitting AILuminate applied to the petition's comparison section; it does not mean P-4 omitted it. Any novelty claim requires an up-to-date capability comparison and experimental evidence.

## Truthful evidence statement for today's implementation

As of September 16, 2026, a local LTEF v0.1 prototype exists with executable scoring, schema validation, synthetic fixtures, reports, and automated tests. It has not been publicly released, tested against real models in this session, deployed at a partner, validated for clinical use, or accepted by a standards organization. The demo observations and improvements are deliberately constructed fixtures, not measured provider performance. Retain these boundaries in research and petition descriptions.
