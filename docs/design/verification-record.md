# Verification record — September 20, 2026

This record concerns local implementation behavior, not validated model or sector performance. Browser tests use isolated temporary databases and synthetic evidence. No test account or evaluation was created in the real workspace database.

| Check | Executed command / inspection | Observed result |
|---|---|---|
| Python engine, auth, workspace and readiness regression | `python3 -m unittest discover -s tests -q` | 59 tests, 16.587 seconds, OK. Includes authenticated design downloads and explicit path allowlisting. |
| Existing browser journeys | `python3 scripts/check_webapp.py` | PASS: public/auth, roles, direct API restrictions, role changes, sample/upload runs, export, comparison, metric/case dialogs, keyboard and desktop/mobile; no JavaScript errors. |
| New guided data journey | `python3 scripts/check_data_workflow.py` | PASS: metric selection, exact guidance, ZIP download, valid/invalid preflight, no persistence, file replacement invalidates readiness, run/save, missing clinical review, Viewer restrictions, desktop/mobile; no JavaScript errors. |
| JavaScript parsing | `node --check ltef/ltef/web/app.js`; `node --check ltef/ltef/web/data.js` from parent workspace | Both succeeded. |
| Evidence matrix integrity | CSV row count; extract named test functions and check against test source | 28 rows; named test functions exist. This structural check is separate from execution above. |
| Editable diagram structure | Parse native draw.io XML; verify per-page cell uniqueness and source/target references | Five pages; connected edges reference existing shapes. |
| Design content rendering | Chromium opens generated local HTML | Five inline SVG figures and 28 requirement cards; PDF generated. |
| Visual inspection | Desktop/mobile intake screenshots; HTML design preview; five SVG diagram previews | Reviewed typography, text fit, flow and boundaries. Short connector labels and ownership route adjusted where needed. |

The diagrams were created locally as editable draw.io XML.

Current design limitations: loopback-only deployment, no live provider adapter, no independent reviewer/sector validation, no formal accessibility audit, no production load/recovery evidence. Passing fixture tests supports the specified code behavior only.

Screenshot evidence in the project: `runs/web/data-{choose,requirements,mobile,check,check-mobile}.png`. The packaged evidence directory contains selected copies. Re-run scripts after relevant changes and replace this record with actual observed results.


## Folder name update — September 20, 2026

The outer project folder is now `LLM-Trustworthiness-Evaluation-Framework`, expanded from LLM Trustworthiness Evaluation Framework. Documentation paths, PDFs and the design ZIP were refreshed. The Python import name remains `ltef`.

Targeted verification after moving: the workspace database matched its pre-move SHA-256 byte for byte (one existing user and three reports), all 18 metric definitions imported, a selected-metric starter ZIP generated, the macOS launcher passed shell syntax checking, and the restarted local app served its assets and recognized the existing account. No scoring or authorization behavior changed; the 59-test and browser-suite records above belong to the preceding implementation verification.

## Documentation cleanup — November 3, 2026

Removed notes about local editor tooling (draw.io connector setup) and a local folder path, which did not concern LTEF behavior. Added an author credit and source link to the public site footer. No scoring, metric, schema or authorization code changed.

Re-run after the change: `python3 -m unittest discover -s tests -q` ran 80 tests, OK. `python3 scripts/check_webapp.py` and `python3 scripts/check_data_workflow.py` both passed with no JavaScript errors.
