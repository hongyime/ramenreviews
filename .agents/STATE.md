# Ramen Reviews maintenance

Updated 2026-09-16 SGT. Baseline triage by Sisyphus-Junior.

## Current State
- HEAD: 0e17841 (chore: sync heartbeat)
- Branch: main, clean, synced with origin
- Stack: Python 3.12 / Flask 3.1.3 / Gunicorn 26.0.0 / SQLite
- Hosting: Render (Procfile), GitHub Pages for docs
- Open PRs: 0  |  Open Issues: 0
- Secrets scan: clean  |  npm audit: N/A

## Previous context (2026-09-10)
Code protects writes with bearer auth, parameterises values, validates identifiers
and paginates reads. All 31 synthetic tests and Gunicorn smoke check passed for
`dc1be37`. Security tab may still show older Dependabot alerts (15 noted 2026-09-10).

## Next
- Check GitHub Security tab for current Dependabot alert status
- Confirm Render deployment URL is still live
- No code changes needed from this triage pass

## Privacy maintenance - 2026-09-27

Remove the optional personal security contact while retaining private vulnerability-reporting guidance. The narrow documentation patch is prepared from the current default branch; staged whitespace and the inherited identity hook are publication checks. Application behavior is unchanged.
