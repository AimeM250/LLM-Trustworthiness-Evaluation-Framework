# Contributing to LTEF

Thanks for considering a contribution. LTEF is a research-stage project: precision and
honesty about what is and isn't measured matter more here than feature velocity.

## Ground rules

- **Zero runtime dependencies.** The CLI, engine, and web workspace run on the Python
  standard library only. Don't add a third-party package to `dependencies` in
  `pyproject.toml` without discussing it in an issue first.
- **No invented scores.** Every metric has an explicit scope, direction, and missing-data
  state. Don't add aggregate "trustworthiness scores" or silently coerce missing data to
  zero — that's a deliberate design constraint, not an oversight.
- **Synthetic data stays labeled synthetic.** Example cases, observations, and reports
  under `examples/` must remain clearly synthetic (`evidence_class: synthetic_demo`).
  Don't add real model outputs or real user data to the repository.

## Getting set up

```sh
git clone https://github.com/AimeM250/LLM-Trustworthiness-Evaluation-Framework.git
cd LLM-Trustworthiness-Evaluation-Framework
python3 -m unittest discover -s tests -v
```

No virtualenv or `pip install` is required to run the tests or CLI — everything is stdlib.
`pip install -e .` is only needed if you want the `ltef` console script on your `PATH`.

## Before opening a pull request

1. Run the full test suite: `python3 -m unittest discover -s tests -v`.
2. If you touched the web workspace, also run the Playwright end-to-end check:
   `python3 scripts/check_webapp.py` (requires Playwright: `pip install playwright && playwright install chromium`).
3. Keep documentation in sync: `docs/measurement-protocol.md` for metric semantics,
   `docs/data-contract.md` for schema changes, and the README for anything user-facing.
4. Describe *why* a change is needed, not just what it does — especially for new metrics
   or changed thresholds, since those carry research and policy implications.

## Proposing a new metric or sector profile

Open an issue first describing: the measurement, its evidence source, its missing-data
behavior, and why it needs its own scope rather than reusing an existing metric. Sector
profiles (`examples/profiles/*.json`) are configuration starting points, not validated
products — a new profile should say plainly what it has and hasn't been validated against.

## Reporting security issues

Please don't open a public issue for a security vulnerability — see [SECURITY.md](SECURITY.md).
