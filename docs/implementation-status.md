# Implementation record — September 20, 2026

## Completed locally

- Python 3.9+ package and command-line evaluation/comparison tools, without third-party runtime dependencies.
- Eighteen defined metric scorers, plus delivery/intent-to-test outcomes, repeated-trial consistency, counterfactual agreement and group summaries.
- Finance, healthcare and public-sector research profile configurations.
- Dataset, observation, annotation and multi-agent trace validation.
- Case-weighted results; paired case/trial comparisons; deterministic case bootstrap intervals with a minimum-case reporting rule.
- Dataset, observation, profile and implementation hashes; explicit synthetic evidence labels and incomplete-measurement states.
- A provider-neutral Python collection boundary; no provider-specific live integration yet.
- Research traceability, measurement protocol, data contract and revised 36-month roadmap.

## Verification performed

`python3 -m unittest discover -s tests -v`: **31 tests passed**.

The CLI produced reports for all three profiles and a paired finance comparison. Report manifests were checked against the current implementation hash. Known fixture outcomes, the 18-metric inventory, eight selected cases per sector, and absent clinical adjudication were verified.

Tests cover missing evidence, failed systems, prompt mismatches, duplicate records/JSON keys, numeric/Unicode scoring, malformed or incomplete traces, permission attempts versus executions, handoff accounting, false-positive privacy scope, annotation provenance, case weighting, same-trial comparisons, resource costs on failures, output preservation and secret omission.

## Evidence boundary

The 24 cases and 93 observations are synthetic scoring fixtures, not a representative benchmark or actual model runs. Some expected observations intentionally fail or are missing to exercise the accounting. No live APIs, actual tool operations, external messages, paid calls, public releases, partners, or standards submissions occurred. This is a verified software starting point, not validated sector performance.

## Next concrete milestone

Choose the first sector/use case and model access method, implement its live adapter, freeze a small independently reviewed dataset, and produce the first actual model baseline with failure accounting. Then implement an isolated two-agent version of the same task and compare final outcomes, policy violations, coordination behavior and compute use. Domain validation and metric validity work should precede any substantive deployment claim.


## Reworked local web workspace (September 20, 2026)

The browser interface now separates the public introduction and sign-in flow from
the authenticated workspace. It uses a restrained layout, locally bundled fonts,
metric categories, evaluation history, separate result sections, paired comparisons,
case details, provenance, research resources, and an account/access page. JSON and
Markdown exports, synthetic runs, and validated file uploads use the existing
Python evaluation engine.

Local account roles are enforced on the server:

- **Viewer:** six performance/efficiency metrics; shared sample evaluations and the
  authorized subset of that account’s own reports. Cannot run, compare, or export.
- **Researcher:** all 18 metrics, evaluation execution, comparisons, and exports.
- **Administrator:** Researcher capabilities plus account listing and role changes.

The first account becomes Administrator atomically; subsequent registrations are
Viewers regardless of supplied role fields. Administrators cannot remove the last
administrator. These permissions are workspace product rules, not paper-derived
metric classifications or subscription plans.

Accounts use individually salted PBKDF2-SHA256 password hashes (600,000 iterations),
12-hour cookie sessions with HttpOnly and SameSite=Strict, session rotation on
sign-in, logout revocation, and bounded authentication attempts. Role changes apply
to subsequent API requests, including existing sessions. The loopback server also
enforces Host/Origin checks and session-specific request tokens. Public bootstrap
responses contain no evaluations or metric measurements.

SQLite stores reports, accounts, and sessions. Only the three original synthetic
examples are shared. New evaluations are owned by their creator; other accounts,
including administrators, cannot read them. Migration preserves older reports and
assigns private legacy reports to the first administrator. Viewer responses filter
metric definitions, profile metrics, system measurements, and observation metrics;
restricted supplementary measurements are also removed. Original uploaded response
text and raw traces are not retained in reports. Static files are explicitly
allowlisted; petition documents are not served.

Python verification: **50 tests pass**, including the original 38 engine/workspace
tests and 12 account/API/migration tests. Added checks cover concurrent initial
registration, password storage, login rotation, logout revocation, session expiry
and persistence, role changes, last-administrator protection, unauthorized direct
requests, Viewer response filtering, cross-account report access, migration, and
Host/Origin/request-token enforcement. The browser integration check in `scripts/check_webapp.py` also passes: public and authenticated navigation, Viewer restrictions, administrator role changes, keyboard sign-in and dialog focus, sample and uploaded evaluations, JSON exports, comparison error handling, and desktop/mobile layouts. No JavaScript errors were observed. All browser test accounts and reports use a temporary database, separate from the real workspace.

This remains a local research application on this device. It has no public hosting,
email verification, password-reset flow, external identity service, provider API
collection, or cloud synchronization. Sector datasets and metric extensions still
require research validation. Synthetic examples remain explicitly labeled.


## Guided requirements and design package (September 20, 2026)

Implemented a three-step Data requirements workflow: select sector/metrics, inspect exact prerequisites and download a synthetic starter ZIP, then check uploaded files before running. The requirements API covers all 18 scorers. Preflight shares input parsing, limits and core scoring with the evaluation engine; it saves no report. Metrics retain distinct scored, missing, error and inapplicable counts. Changing a selected file removes browser readiness, and actual evaluation revalidates all contents.

Final Python verification: **59 tests passed** (16.587 seconds). Both `scripts/check_webapp.py` and `scripts/check_data_workflow.py` passed, with desktop/mobile layouts and no JavaScript errors. New checks include missing clinical labels, prompt mismatch, readiness invalidation, no preflight persistence, selected-metric ZIP validity, Viewer denial and authenticated document allowlisting.

`docs/design` contains the BRD and technical design, 28-row evidence matrix, five-page native draw.io source, SVG previews, PDF/HTML and verification record. The draw.io MCP was configured in Codex and initialization/tool discovery verified. Diagrams were authored locally; private petition content was not sent to MCP. Production and scientific-validation gaps remain explicit.
