# Six farm-management improvements

Implemented and checked locally on 2026-11-13. The local application is running with the database migrations applied. No GitHub push or Render deployment was performed.

## 1. Correct a distribution

Open **Feed & Inventory → History → Reverse**. Enter a reason. Reversal restores the distributed quantity, transfers the assigned expense back to the remaining purchase balance, and keeps the original distribution in history with its original cost, reversal time, responsible account and reason. A repeated request cannot restore stock twice. Reversed deliveries are excluded from feed totals. Their expense remains visible with zero assigned cost and a reversal audit entry.

To correct a receiving branch, flock or quantity, reverse the mistaken delivery and create its replacement. Existing financial/purchase dates and farm-wide total costs are preserved. Items with distribution history cannot be deleted through the inventory API.

## 2. Low-stock warnings

Use **Minimum stock** beside an inventory item, or enter a threshold while adding it. The value uses the item's recorded unit. A blank threshold disables warnings. At or below the threshold, the item is highlighted and the account receives an in-app warning, subject to its notification preference. Further saves while stock remains low do not repeat that warning. Restoring stock above the threshold rearms the warning for the next low-stock episode.

Dashboard notifications now show actual notifications belonging to the current account instead of placeholder alerts. No email or push delivery was enabled.

## 3. Branch expenses

Open **Reports → Branch expenses and feed distribution**. Select dates and a branch, then Apply. The expense table groups actual expense records by branch and expense type. **Export expenses CSV** downloads matching detailed entries, including their financial date and distribution date. All branches includes the remaining unassigned purchase cost once. A branch selection includes only that branch's assigned costs. Historical inactive branches remain available for reporting.

Expense filtering uses the original financial/purchase date. This preserves monthly purchase/cash-flow totals while allowing the separate distribution date to describe physical deliveries. Exported user-entered text is protected against spreadsheet formula execution.

## 4. Flock-level feed tracking

The distribution form now offers the active flocks in the selected receiving branch. The server rejects flocks belonging to another branch/account, or inactive flocks. A flock is optional because some inventory goes to branch stock before a flock is known. Existing deliveries were not assigned guessed flock identities.

The report shows feed delivered, recorded cost and eggs produced for each recorded flock in the selected delivery/production period. Quantities remain separated by unit. Distributed feed cost per egg is calculated only when the flock, cost and individual egg counts are known; trays are not silently converted. A delivery is not proof that all feed was consumed, so the report does not claim biological feed-conversion efficiency.

## 5. Backups and actual restore verification

`tools/backup_database.py --verify-restore` creates a consistent PostgreSQL custom-format dump using an exported transaction snapshot. It restores that dump into a separate, temporary PostgreSQL cluster bound to localhost and compares every public table's row count and content checksum. The live application's database is never a restore target. Temporary restore clusters are shut down and removed after verification.

Two real restore checks succeeded. The final post-migration snapshot verified **33 tables and 510 rows**. Backups and private verification manifests are stored in `.database-backups/scheduled/`. `last_run.json` records the latest result. Credentials are passed through the subprocess environment and are not printed into reports. Automatic retention preserves at least seven verified snapshots and prunes older verified pairs beyond 30 days. Manual backups outside this subfolder are untouched.

Windows rejected Task Scheduler registration with **Access is denied**. The installer therefore created a current-user Startup shortcut, **SmartPoultry Database Backup**, and started `tools/database_backup_scheduler.py` without a visible window. Its target is **02:00 local time daily**, with catch-up after login or a missed run. This fallback requires this Windows account to be logged in and the computer to be running. `.database-backups/scheduled/scheduler_status.json` contains its heartbeat. A lock prevents duplicate schedulers/backups.

This is a desktop database backup schedule. It is not a scheduled backup of Render's separate database. Database dumps also do not archive uploaded media, model weights or environment secrets; those remain separate workspace files.

Reinstall the preferred scheduler/fallback using:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/install_database_backup_task.ps1
```

## 6. Independent age-model evaluation

The evaluation runner now binds results to the exact checkpoint, manifest and supporting register by checksum. It rejects known byte/pixel duplicates, blocks visually similar frames pending provenance review, requires verified ages and identities, and checks that input images and the model remain unchanged during evaluation. Image bytes are passed to prediction without filenames. The selected model is evaluated without training or replacement.

With qualifying inputs it writes MAE and bias, per-age and age-group performance, per-image errors, a rounded-month confusion matrix, chicken-balanced MAE and a reproducible bird-level bootstrap interval. Small samples are flagged. The Reports page displays whether an evaluation exists for the current checkpoint. Verification flags and the register still require honest human review; software cannot infer real bird identities from generated filenames.

Readiness inspection was executed again: the corpus still has **151 known distinct photographs**, and all **46** source photographs in `spurs images` are already represented in it. A verified unseen-chicken evaluation was therefore **not executed**. The missing input is an age/identity/capture register establishing that the selected photographed individuals were excluded from **all** previous training, including the original checkpoint. Existing verified age labels and original photographs were preserved. No claim of improved accuracy or zero error is made.

The existing manifest template is `reports/unseen_evaluation/manifest_template.csv`. Once supported by actual records, run:

```text
.venv\Scripts\python.exe tools/evaluate_unseen_chickens.py --manifest path/to/verified-unseen.csv --provenance path/to/capture-register.csv --output reports/unseen_evaluation
```

No API accuracy improvement was claimed or deployed. Earlier provider timeouts remain recorded separately under `reports/vision_api/`.

## Executed checks

- **29 Django tests passed**, covering reversals, repeat requests, monetary conservation, branch/account isolation, flock matching, low-stock episodes/preferences, report date filters, CSV, production units and existing financial behavior.
- **3 evaluation-gate tests passed**, including duplicate photographs with different identity strings and missing provenance.
- Actual **PostgreSQL API checks passed** for thresholds, flock assignments, warnings, branch totals/CSV, cost per egg, repeated reversal and unchanged farm cost. Temporary verification data was rolled back.
- Real **Chrome checks passed at 1440 and 390 pixels** for threshold dialogs, flock selection, reversal dialogs, branch reports and CSV links, with no page overflow or JavaScript exceptions. Browser checks did not reverse any real distributions or change stock thresholds.
- The original ResNet-18 checkpoint checksum remains unchanged. Migrations/checks passed and the local server was restarted with the new code.
