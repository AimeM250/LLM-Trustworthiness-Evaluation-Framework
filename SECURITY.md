# Security Policy

## Scope

LTEF ships two very different surfaces — treat them differently when thinking about risk:

1. **The local web workspace** (`python3 -m ltef.webapp`, or the `ltef` Docker image). It has
   real accounts, PBKDF2-hashed passwords, and session cookies (see `ltef/auth.py`). It is
   designed to run on a **trusted machine or network** that you control — it has no email
   verification, no password-reset flow, and no external identity provider. By default it binds
   only to `127.0.0.1`. If you run it with `--host 0.0.0.0` (or the Docker default) so it's
   reachable from your network, you are responsible for putting it behind your own TLS
   termination and access control (a reverse proxy, VPN, firewall rules, etc.) — the app's own
   auth model was not designed to be an internet-facing perimeter.
2. **The public demo site** (`handler.py` / `_demo.py`, deployed on Vercel). It is intentionally
   stateless and read-only/compute-only: there are no real accounts, no persisted secrets, and
   no database. Anything a visitor can "sign in" to on the demo is cosmetic, not a security
   boundary — don't report the absence of real authentication there as a vulnerability; it's by
   design (see `_demo.py` and the README's "Public demo" section).

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security vulnerability. Instead, use
GitHub's private vulnerability reporting for this repository (Security tab → "Report a
vulnerability"), or email the maintainer directly. Include:

- The affected surface (local workspace vs. public demo) and version/commit.
- Steps to reproduce, and the impact you believe it has.
- Whether the issue is in LTEF's own code (`ltef/auth.py`, `ltef/webapp.py`, `handler.py`)
  versus a third-party dependency — LTEF has zero runtime dependencies, so most reports will be
  about first-party code.

We aim to acknowledge reports within a few days. Since this is a research-stage, unfunded
project, response time isn't guaranteed on a fixed SLA, but genuine authentication, session, or
data-isolation issues in the local workspace are treated as high priority.
