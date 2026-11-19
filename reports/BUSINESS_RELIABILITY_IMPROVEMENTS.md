# Business reliability improvements

## Stock and expenses

Inventory now shows each branch's distributed lots, received quantity, recorded
use, and remaining balance. Record use in the original lot's stock units: e.g.
1 sack of 25 kg, not 25 sacks. Packaging snapshots remain unchanged.
Consumption is not inferred from distribution. Recording use does not create a
second expense. Usage corrections are reversals with a reason. A distribution
with un-reversed usage cannot be reversed. All branch and usage queries are
owner-scoped; balances are protected under the inventory row lock.

## Retried financial operations

The website sends a persistent `Idempotency-Key` on sales, orders, distributions,
usage and usage reversals. Successful results are retained in PostgreSQL with
the owner, path, key and request digest. Matching retries replay the response;
different data with the same key returns 409. A PostgreSQL owner row lock
serializes simultaneous retries across workers. Failed transactions roll back.
The browser retains uncertain request keys through reloads. API integrations
must also supply a key; legacy calls without one retain their prior behavior.

## Receipts and audit history

Revenue has an owner-scoped printable receipt. New multi-item orders share an
internal UUID; separately entered orders never merge because a typed order
number happens to match. Older sales without this UUID print individually.
These are sales receipts, not tax-invoice certification.

Change History captures selected business fields before/after a change, the
authenticated actor, time and supplied reason. Passwords, photos, tokens and
API keys are excluded. Direct system updates are labelled System. Correction
notes append new events; the web UI does not overwrite earlier events. History
starts on installation; historical actors and reasons are not invented. This
is an application audit, not protection against a database administrator.

## Broiler readiness

Notifications use the configured 25-day minimum and 60-day expected window.
Opening Dashboard, Flocks or Notifications checks readiness. A unique key per
owner/flock/placement date prevents repeated alerts, including concurrent visits.
Inactive/empty flocks and disabled in-app preferences are excluded. Hosting that
sleeps cannot guarantee a notification at midnight. A scheduled deployment can
also run `python smartpoultry/manage.py notify_broiler_readiness`.

## Backups

The desktop backup tool exports a consistent PostgreSQL snapshot, restores it
to an isolated temporary cluster, and compares every table's row count and
content checksum. Existing Windows scheduling targets 02:00 while the desktop
session is logged in and catches up after login. Backups remain in ignored
`.database-backups/`; copy them to a private off-machine destination as well.

To include Render, store its **external** database URL privately in the desktop
`.env` as `RENDER_BACKUP_DATABASE_URL`. Do not commit it or paste it in chat.
The desktop scheduler uses a separate `.database-backups/render/` destination.
A one-time verified remote backup can be run without exposing the URL:

```
.venv/Scripts/python.exe tools/backup_database.py --verify-restore --database-url-env RENDER_BACKUP_DATABASE_URL --destination .database-backups/render
```

Render backup was subsequently verified using the privately configured external
database URL: 36 tables and 333 rows matched in an isolated restoration. The
desktop scheduler was reloaded to include Render. These backups reside on this
desktop; no additional off-machine storage destination has been configured.
The hosted status page cannot read desktop verification files.

## Age estimation

The source-data gate was rerun: 151 distinct corpus photos; all 46 current
source files already occur in that corpus. No qualifying independent manifest
or identity/capture register is available, so no independent accuracy or tested
range is claimed.

Use `tools/evaluate_unseen_chickens.py --manifest ... --provenance ...` with real
verified ages, chicken IDs and exclusion records. Then run
`tools/calibrate_age_ranges.py`. It requires at least 40 unseen chickens, splits
by chicken into at least 20 calibration and 20 separate test birds, calibrates
a 90% target range from bird-wise maximum absolute errors, and reports observed
coverage only on the untouched test birds. All photos of a bird stay together.
The displayed range is tied to the exact model checkpoint and evaluation report
digests. Missing/mismatched reports show an explicit unavailable message; MAE
is never converted into a claimed confidence range. No weights or age labels
were changed.

## Verification

- Backend stock, revenue, flock and production regression tests.
- An isolated PostgreSQL instance verifies concurrent identical requests create
  only one distribution; no production database privileges are changed.
- Desktop/mobile browser checks use an isolated temporary database.
- Real desktop PostgreSQL backup and isolated restore verification.
- Synthetic calibration protocol tests validate disjoint splits and that test
  errors do not choose the interval width; they make no accuracy claim.
