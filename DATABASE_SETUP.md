# SmartPoultry PostgreSQL setup

Desktop migration completed and verified on 12 November 2026 (Asia/Taipei).

## Desktop

The running app uses PostgreSQL 18 on `127.0.0.1:5432`, database
`smartpoultry_desktop_20261112t053031z`. The dedicated app role is
`smartpoultry_app_20261112t053031z`. Credentials are in the ignored `.env` file.
The app role is not a PostgreSQL administrator. Other existing databases and
the PostgreSQL administrator password were not changed.

All 10 local accounts, their password hashes and related records were copied.
All managed-model row counts match. A full exported-content comparison also
matches, excluding `last_login`, which changes during ordinary sign-in.
Registration and login were verified against the actual PostgreSQL database;
the temporary verification account was rolled back. Twelve targeted tests
passed for settings, registration, financial signals and restore behavior.

The original `db.sqlite3` remains intact. Consistent SQLite backups, data exports
and the previous environment configuration are under `.database-backups/`.
The successful migration report is in
`.database-backups/20261112T053031Z/migration_report.json`.
A PostgreSQL custom-format backup is in
`.postgres-migration/desktop-verified.dump`. These locations contain private
data, are ignored by Git, and must not be committed.

PostgreSQL's Windows service is running with Automatic startup. The local app
was restarted and its health endpoint confirms PostgreSQL. Recheck with:

```powershell
.\.venv\Scripts\python.exe tools\verify_postgres_accounts.py
.\.venv\Scripts\python.exe smartpoultry\manage.py check
```

The one-time importer initially exposed fixture-save signals creating extra
expenses/transactions. Its failed import rolled back. Restore signals now skip
raw fixture loading, with regression coverage. The failed attempt's isolated
database contains migration-generated schema only and is not used by the app.

## Render: still requires a hosted database connection

Desktop PostgreSQL does not automatically become Render's database. Render's
`localhost` is the Render instance, not this Windows computer. This work did not
open database ports to the internet or change the live Render database.

Connect the Render integration to inspect the existing service/databases and
finish provisioning. Before any redeploy or database switch, preserve existing
online SQLite data. Local migration does not include accounts created only on
the deployed site. Do not assume the local and online account sets are identical.

Configure the web service's `DATABASE_URL` to the hosted PostgreSQL internal
connection URL, migrate its schema, restore/merge the preserved online records
without overwriting local or online account IDs, and verify authentication.
Changing the connection URL alone does not transfer existing records.

The prepared code intentionally refuses to start on Render without a PostgreSQL
`DATABASE_URL`, instead of silently creating another disposable SQLite database.
Do not push/deploy this change until the hosted database configuration and
online-data preservation are ready. The Blueprint declares `smartpoultry-db`,
but the current live service was independently observed to use SQLite.

Use storage with an appropriate retention plan: free Render PostgreSQL instances
expire after 30 days and do not provide indefinite account retention. Confirm
the plan/cost before creating or upgrading a paid service. Uploaded photos also
need persistent object storage or a persistent disk; PostgreSQL stores their
paths and analysis, not automatically the photo files.
