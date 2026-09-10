# Rave Ramen Reviews 🍜

[API documentation](https://hongyime.github.io/ramenreviews/) · Python 3.12 · Flask · SQLite

Browse ramen reviews by brand, country and flavour, or use the JSON API to manage
review records. The pages share the black-and-white Prawn style, work without
JavaScript and use local CSS. GitHub Pages hosts the documentation, not the API.
The former Heroku demo is retired; no current backend deployment is verified.

## Run locally

```sh
python -m venv .venv
# Activate the virtual environment for your shell, then:
python -m pip install -r requirements.txt
python main.py
```

Open http://127.0.0.1:5000/. Both `main:app` and `app:app` expose the same app.
The production launcher is `sh run.gunicorn.sh` on a Unix host. It runs one
Gunicorn worker with four threads and a 30-second worker timeout. Use persistent
storage and HTTPS for a separately hosted backend; this SQLite application must
not rely on an ephemeral Vercel filesystem for its records.

`RAMEN_DATABASE` selects the SQLite file; `RAMEN_CSV` selects the import file.
Defaults are the existing `ratings.db` and `ratings.csv` beside the application.
Startup performs no queries or imports. Reads do not create missing databases.
No maintenance command migrates, seeds, removes or rewrites the existing records.

## Browse and search

```sh
curl 'http://127.0.0.1:5000/api/selectall?limit=50&offset=0'
curl 'http://127.0.0.1:5000/api/searchsome?country=SG&sortby=Brand'
```

Responses are JSON objects with `items`, `limit`, `offset`, `has_more` and
`next_offset`. Default pages contain at most 50 records; the maximum is 200.
Offsets are limited to 100000. Fetch pages on demand; concurrent writes can move
records between pages. Filter by `ID`, `Country`, `Brand`, `Type`, `Package` or
`Rating`. ID and Rating values match exactly. Descriptive text and literal
`keyword` searches within Type use Unicode case-insensitive matching. Values
retain their original text. Sorting uses the stored text and row
order for ties. Unknown fields and ambiguous duplicate parameters are rejected.

## Administrative operations

Set `RAMEN_ADMIN_TOKEN` on the server to a random secret of at least 32 characters.
Send `Authorization: Bearer <token>` for every write. Missing or weak configuration
disables writes while public reads remain available. Never put the token in a URL,
browser storage or source control. No cookie-based write authentication or CORS
access is enabled.

| Endpoint | Method | Behavior |
|---|---|---|
| `/api/createone` | POST | Create missing storage without replacing records |
| `/api/addone` | POST / PUT | Add supplied review fields |
| `/api/addmany` | POST | Append the configured CSV atomically |
| `/api/searchsome` | GET / PUT | Search with at least one filter |
| `/api/selectall` | GET | Read one bounded page |
| `/api/editsome` | PUT | Require filters plus update fields, such as `updaterating` |
| `/api/deletesome` | DELETE / PUT | Delete matching reviews only |
| `/api/deleteall` | DELETE | Also require `X-Confirm-Delete: all-reviews` |

JSON objects and form fields are accepted for writes. Requests are limited to
32 KiB, field values to 4096 characters and CSV imports to 8 MiB / 10000 rows.
Imports append records, so an intentional repeat imports them again. Writes are
never automatically retried. If a response is lost, verify the outcome before
retrying. Successful writes report an affected-row count; errors never report
successful deletion. Malformed or invalid CSV rows roll back the entire import.

Compatibility changes: mutation GET requests return 405; callers must use the
documented authenticated methods. Read responses are structured JSON instead of
JSON embedded in a string. Callers needing more records must follow pagination.
Text is preserved instead of being automatically capitalized. Direct SQLite
helpers now raise validation/storage errors and return affected counts for writes.

## Verification and documentation

```sh
python -m unittest -v test_ramen
python render_docs.py --check
# Linux/Unix with Gunicorn:
python ci_smoke.py
```

Tests use temporary synthetic databases and CSVs. They exercise authentication,
SQL boundaries, actual rollback and locking, pagination, escaped HTML and both
entry points. The hosted workflow also launches Gunicorn on loopback with a
synthetic database; it never touches the checked-in records. After editing the
documentation template, run `python render_docs.py` and commit both generated
HTML files. Rendering documentation does not access review data.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Maintenance diagnosis — 2026-09-10

Confirmed against source `c651a81` using an isolated, synthetic SQLite database:
an injected search returned both fixture rows; unauthenticated GET deletion
removed the fixtures and returned 200 in both entry points; an injected database
failure also returned 200. Every referenced page template was missing. No existing
ratings database or CSV records were queried, imported, changed or deleted.

The root causes are SQL value interpolation, unrestricted mutation routes,
swallowed database errors, duplicated Flask applications and missing templates.
The repository ignored the entire `templates/` directory, preventing those pages
from reaching a clean checkout; that ignore rule is corrected with this repair.
The checked-in Python 3.8 runtime and launch commands also disagree with the
installed dependencies and actual application module. The public GitHub Pages
site hosts documentation; the former Heroku API is marked retired.

Implementation sequence: parameterize and validate database operations; require
explicit authenticated mutations and truthful errors; bound browse/search pages;
restore the missing pages with shared Prawn styling; align both entry points and
runtime dependencies; verify synthetic workflows and hosted checks, then publish
the source and documentation. Existing records must retain their file hashes.

Verification covers literal quotes and injection strings, rejected broad or
malformed writes, authentication and HTTP methods, rollback/connection closure,
pagination, HTML escaping, missing/locked databases and both entry points.
Browser checks use synthetic reviews only. A source or Pages release does not
prove that a separate backend has been deployed or that hosting usage fell.

Initial-release local verification: 29 synthetic SQLite/Flask tests passed in an isolated
dependency environment. Desktop/mobile browsing, filters, pagination, empty
states and no-JavaScript operation passed; the fixture and existing data-file
hashes were preserved. The pinned runtime dependency audit found no known
vulnerabilities. Six Bandit SQL-construction warnings were reviewed: table,
projection, sort and filter identifiers are allowlisted, and values are bound.
Narrow B608 annotations document that review; it is not a claim that static
analysis alone proves security.

Source `98bdf91` is published on main. All seven triggered main workflows passed,
including [Ramen API checks](https://github.com/hongyime/ramenreviews/actions/runs/34495920652).
The hosted checks ran all 29 tests and started Gunicorn against synthetic data.
The live GitHub Pages homepage, documentation path and CSS match the reviewed
files; desktop/mobile navigation passed. The API backend remains unverified.
Rollback: revert the reviewed source change without touching the database or CSVs.
Restoring an old API version would also restore its unsafe write routes, so
keep administrative access restricted during any rollback.

The GitHub dependency graph contains the new pinned runtime versions. The separate
alert-status snapshot at 15:31 UTC still listed 15 older requirements alerts; their
automatic closure remains a follow-up, not a claimed result. CodeQL was already
manually disabled with default setup unconfigured; this release did not change
that setting. Semgrep, Bandit and TruffleHog completed successfully.

Technical references: [SQLite parameter binding](https://docs.python.org/3.12/library/sqlite3.html),
[Flask security guidance](https://flask.palletsprojects.com/en/stable/web-security/),
and [Python runtime selection](https://devcenter.heroku.com/articles/python-runtimes).

### Compatibility follow-up

Two additional synthetic regressions exposed overly broad NOCASE matching:
searching ID `a` also matched ID `A`, and a Unicode brand/country/keyword search
missed a legacy-style capitalized record. The first release applied SQLite's
ASCII NOCASE comparison to every equality filter. The correction retains
exact ID/rating comparisons and Unicode case-insensitive descriptive text,
including literal keyword searches. Existing record text remains unchanged.
The full 31-test suite passes locally, including exact-ID search/edit/delete and
Unicode brand/country/keyword checks. Hosted verification precedes promotion.
