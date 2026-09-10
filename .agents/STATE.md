# Ramen Reviews maintenance

Updated 2026-09-10 SGT. Current code protects writes with bearer authentication,
parameterizes values, validates identifiers and paginates reads. Both entry points
share one Flask app. Prawn-style browse/help/documentation pages work without
JavaScript. GitHub Pages hosts documentation; it does not run the API.

The final compatibility correction keeps ID/rating filters exact and restores
Unicode case-insensitive descriptive-text and keyword matching without rewriting
records. All 31 synthetic tests and the real Gunicorn smoke check passed for
`dc1be37` in [hosted CI](https://github.com/hongyime/ramenreviews/actions/runs/34498771355). Earlier desktop/mobile
flows also passed. All three existing SQLite/CSV files retain their original hashes.

The pinned runtime audit found no known vulnerabilities. GitHub's dependency graph
lists the new versions; its initial alert-status snapshot still contained 15 old
alerts, so consult the Security tab for current status. Existing manually disabled
CodeQL/default-unconfigured settings were unchanged; Semgrep, Bandit and TruffleHog
ran on the initial implementation. Narrow B608 annotations explain reviewed
identifier construction and parameter binding.

Next: identify any API backend before claiming a backend deployment or measured
hosting savings. The former Heroku demo is retired. Preserve the SQLite/CSV data;
do not run imports or real mutations as smoke tests. README.md records API
compatibility changes, verification links and rollback limitations.
