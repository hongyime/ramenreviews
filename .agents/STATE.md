# Ramen Reviews maintenance

Compatibility correction prepared: the full 31-test suite passes with exact
ID/rating comparisons and Unicode descriptive-text/keyword matching. Two new
regressions first reproduced case-distinct IDs being merged and legacy Unicode
matches being missed. Records are not rewritten. Verify the hosted runtime before
promoting this follow-up; the earlier release evidence below remains historical.

2026-09-10: Source `98bdf91` is published on main. The repaired API has 29 passing
synthetic SQLite/Flask tests, a verified hosted Gunicorn startup and seven passing
main workflows. Writes require bearer authentication; reads are paginated; both
entry points share one application. Restored Prawn-style pages work on desktop,
mobile and without JavaScript. GitHub Pages serves the reviewed documentation/CSS.
All three existing DB/CSV files retain their original hashes.

The runtime dependency audit found no known vulnerabilities; GitHub's dependency
graph lists the new versions. Its 15 older open alert statuses still need a fresh
check. Existing manually disabled CodeQL/default-unconfigured state was unchanged;
Semgrep, Bandit and TruffleHog ran. Six B608 annotations document reviewed fixed
identifiers and parameter binding, not a blanket security guarantee.

Next: identify any current API backend before claiming a backend deployment or
hosting savings. The former Heroku demo is retired and GitHub Pages hosts only
documentation. Preserve the SQLite/CSV records; do not run imports, migrations or
real mutations as smoke tests. See README.md for API compatibility changes,
verification links and rollback limitations.
