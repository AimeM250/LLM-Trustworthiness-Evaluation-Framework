# LTEF product interface

## Journey

The public welcome page explains the evaluation framework and the roles available.
Sign-in and account creation are focused pages with no evaluation data visible.
After authentication, the workspace opens with metric categories and a short list
of recent evaluations. Results, comparisons, methodology, and access management
have separate destinations.

## Information hierarchy

- Workspace: metric access summary, four metric category tabs, recent evaluations.
- Evaluations: searchable list filtered by sector.
- Evaluation: Summary, Metrics, Observations, and Provenance sections.
- Comparison: paired differences between two systems from one evaluation.
- Resources: methodology and the proposed 36-month research sequence.
- Account & access: current permissions; administrators also manage account roles.

The summary deliberately avoids a composite trust score. Synthetic evidence is
identified on every results/comparison screen and in exported reports.

## Visual system

Manrope provides interface typography; Instrument Serif is reserved for the
welcome and research narrative. Fonts and their SIL Open Font Licenses are stored
locally, so the interface does not depend on external font services. The palette
uses white and cool neutral surfaces, dark text, and a single cobalt accent.
Generous page spacing, restrained borders, and simple rows replace stacked panels.
Detailed accounting appears only when a metric or observation is opened.

Native dialogs provide keyboard dismissal and focus containment. Category controls
are labeled toggle buttons with explicit selected states. Mobile navigation uses
an overlay, Escape dismissal, and closes on navigation. Reduced-motion preferences
are honored. Wide analytical tables scroll within their own containers.

## Product access policy

These categories and roles are product decisions, not metric classifications or
validation requirements established by the research papers.

| Role | Metrics | Actions |
|---|---|---|
| Viewer | Performance (3) and efficiency (3) | Read shared examples and permitted results; preview all metric definitions |
| Researcher | All 18 metrics | Run evaluations, inspect private results, compare systems, export reports |
| Administrator | All 18 metrics | Researcher actions plus assigning account roles |

The first account created on a fresh workspace becomes Administrator. Later
accounts begin as Viewer. Roles are checked on the server; restricted values are
removed from reports before transmission. Created evaluations belong to their
creator, including synthetic runs. Only the bundled seed examples are shared.

## Delivery boundary

This remains a loopback-hosted research application with local accounts. Public
hosting, external identity providers, email verification, password recovery,
payment tiers, and live provider collection are separate work. The new roles do
not change the research basis or evidentiary limits of the evaluation engine.


## Data preparation journey

A dedicated Data requirements page separates metric selection, data provision and readiness. Progressive disclosure keeps metric-specific fields behind readable expandable items. The preparation screen identifies the dataset owner, engineer/reviewer and evaluation lead responsible for the three input files. Server-generated synthetic starter packs match the chosen sector and metrics.

Readiness displays scored/eligible, missing, failed and inapplicable counts, combined across declared systems and trials. It distinguishes valid structure from scientific sufficiency. Only the exact checked file contents can be run from this workflow; replacing a file clears readiness. The profile in the uploaded file remains the authoritative measurement plan. Viewers can inspect requirements; template download, checking and execution are Researcher tools enforced by the API.

The Resources screen links to the technical design and editable diagrams. These are served through an authenticated explicit allowlist, without serving arbitrary project files.
