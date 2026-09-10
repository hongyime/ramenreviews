# Ramen Reviews maintenance

2026-09-10: Confirmed SQL interpolation, unauthenticated GET mutations, false
success on deletion failure and missing Flask templates with synthetic fixtures.
Diagnosis and implementation sequence are in README.md. The repair now has 29
passing synthetic SQLite/Flask tests in a fresh Python 3.12 dependency environment.
Both launchers share an app factory; writes require bearer authentication; reads
are paginated; missing pages and their incorrect ignore rule are repaired.
Desktop/mobile browser flows and no-JavaScript browsing pass with synthetic
records. Runtime dependency audit found no known vulnerabilities. Six Bandit SQL
construction warnings were reviewed against the identifier allowlists and bound
values; narrow B608 annotations retain those decisions beside the queries.

Next: finish browser/security review and hosted Gunicorn verification, then publish
the reviewed source and documentation. All three existing CSV/DB file hashes match
the starting checkout. GitHub Pages is documentation hosting; the retired Heroku API is not a
verified production runtime. Do not run imports or writes against existing data.
