# Account-storage investigation

Checked locally and against the supplied Render website on 2026-11-13.

## Confirmed evidence

- The live deployment's public health endpoint reports PostgreSQL, database `smartpoultry_db`, and the same configured database host previously supplied by the owner. This is configuration evidence; that endpoint does not query the user table.
- The requested account exists and is active in the desktop PostgreSQL database. It is also present in the original desktop SQLite file and its pre-migration backup. Its password hash is usable and was not reset or exposed.
- Desktop PostgreSQL and Render PostgreSQL are separate databases. Configuring PostgreSQL does not automatically transfer accounts between them.
- A subsequent direct, TLS-protected, read-only query successfully reached that exact live Render database using the owner's earlier connection details. It contains one account: the requested account, active, with a successful login recorded on 2026-11-13. No account was reset or recreated by the agent.
- The Render record was created on 2026-11-12 at 17:15 UTC, whereas the desktop record was created at 05:06 UTC that day. These are separate records, not a shared account table. This does not establish the complete history of any earlier Render SQLite deployment.
- It is not yet established why the reported older credentials failed, whether any earlier cloud record was deleted, or whether the current record survives a new deployment. Login failure alone does not prove account deletion.

## Local fixes

The account API previously allowed ordinary authenticated users to list/change/delete other users' records. It now scopes ordinary users to their own account; account creation/deletion and role changes require administrative permissions. Self-deletion and changes to superusers by non-superusers are blocked.

The profile's optional farm link previously used cascade deletion. It now uses SET_NULL so deleting a farm preserves member accounts and credentials. Neither finding has been established as the cause of the reported Render login failure.

A read-only management command reports the actual database backend, configuration fingerprint and matching account flags without exposing password hashes or credentials:

```text
python manage.py inspect_account_storage --email account@example.com
```

It never creates accounts, resets passwords, changes activation state or transfers data. Run it in the intended deployment after installing the command. The configuration fingerprint helps compare targets but is not proof that a database was never recreated.

## Verification and deployment status

Eleven account access/deletion, read-only inspection, registration and database-selection regression tests passed. A desktop backup was created and actually restored into an isolated temporary cluster before applying the migration; all 33 tables and 510 saved rows matched. The local account count remains ten, and the requested account remains active. The local server was restarted.

These account-safety changes have not been pushed or deployed to Render. Remote read access has now been established; no further connection-setup information is needed for this database. A private baseline of the existing live account was saved in `.postgres-migration/render-persistence-baseline.json`, including its ID, creation time and an opaque credential fingerprint. It contains no password hash or database password. `tools/check_account_persistence.py` can compare the same record after a real deployment without creating a test account or changing any rows. No redeploy has occurred during this investigation, so deployment persistence is not yet verified.

No remote accounts have been created, modified, deleted, imported or reset during this investigation. Do not replace the cloud database or recreate the account merely to conceal the unresolved discrepancy. If the cloud record is missing, migration/recovery can be planned from the preserved source after checking existing cloud usernames and related farm records.
