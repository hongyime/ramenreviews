# Decisions

- 2026-09-10: Reproduced query injection, unauthenticated GET deletion, false-success errors and missing templates using synthetic records. Repair the API and browsing flow together; preserve existing SQLite/CSV records and distinguish documentation publication from backend deployment.
- 2026-09-10: Twenty-nine synthetic tests pass with the repaired API and pinned Flask/Gunicorn environment. Corrected the templates ignore rule so the restored UI reaches clean checkouts. Database/CSV bytes remain unchanged; backend hosting and measured platform savings are unverified.
- 2026-09-10: Published 98bdf91 after hosted synthetic Gunicorn verification; seven main checks passed and live Pages HTML/CSS matched. Kept existing data hashes and CodeQL configuration intact. API runtime, measured savings and automatic closure of older GitHub alerts remain unverified.
- 2026-09-10: A final compatibility review reproduced ID case merging and missed Unicode matches. The correction uses exact ID/rating filters and Unicode folding only for descriptive text/keywords, without rewriting records; all 31 local synthetic tests pass. Hosted verification is next.
