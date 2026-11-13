# Audited spur age pipeline

Run from the SmartPoultry project root with the existing `.venv` Python.

```
.venv\Scripts\python.exe tools/audit_spur_dataset.py
.venv\Scripts\python.exe tools/evaluate_existing_age_model.py
.venv\Scripts\python.exe tools/group_spur_image_families.py
.venv\Scripts\python.exe tools/train_verified_spur_age.py --content-family-experiment --epochs 100
.venv\Scripts\python.exe tools/write_spur_audit_report.py
.venv\Scripts\python.exe tools/verify_spur_source_integrity.py
```

The experiment flag explicitly permits a visual-family holdout with unresolved
bird identities. It does not claim verified chicken-independent evaluation.
Without that flag, training requires reviewed persistent IDs, existing verified
ages, source families and close-up content types. The user confirmed existing
ages on 9 November 2026. No labels are parsed from filenames. Model inputs are
image pixels only. Paths, ages and IDs are used to load targets and build splits,
never as predictive features.

The completed inspection found 151 distinct images among 15,205 files and 149
CSV references to missing files. Exact duplicates are represented once in the
candidate experiment, with every original retained in the inventory. The visual
family grouping applies automatic image similarity and additional conservative
review unions; these identifiers do not assert real chicken identity. The
review-union CSV stores pixel-hash pairs and reasons, not guessed animal IDs.

Training freezes ImageNet ResNet-18 features and batch normalization, learns a
linear L1 regression head on verified existing ages and uses inverse family-size
weights. Seeded group splitting and training produce reproducible artifacts.
Validation chooses the best epoch, and the fixed test set is used afterwards.
All examples, split hashes, versions, error/bias metrics and rounded-month
confusion matrices are saved in a new timestamped experiment directory.

The existing checkpoint is backed up by content hash and never overwritten.
Candidate checkpoints are not promoted automatically. Existing-model scores
on the new split may include its original training images and therefore cannot
establish an independent head-to-head advantage. Ages absent from a held-out
split are reported with n=0 and no metric, rather than a fabricated score.

Read `reports/dataset_audit/REPORT.md` for the executed results and
`detection/ANNOTATION_WORKFLOW.md` for the missing localization/measurement work.

For the latest production/mobile/evaluation review, read
`reports/PRODUCTION_MOBILE_AGE_REVIEW.md`. `evaluate_unseen_chickens.py` runs a
read-only readiness check by default. Use `--manifest path/to/verified.csv --provenance path/to/capture-register.csv` only
with independently verified ages, persistent identities and training-exclusion
records. It rejects known copies; it does not manufacture an independent test
set from the already-exposed corpus. `summarize_age_evaluation.py` describes
existing predictions without retraining. Neither tool promotes a model.

`backup_database.py --verify-restore` creates a PostgreSQL snapshot and restores
it into a separate temporary local cluster. It checks every public table's row
count and content checksum; it never restores over the live application database.
See `reports/SIX_IMPROVEMENTS.md` for the installed daily desktop schedule,
retention, verified results and remaining independent-evaluation requirements.
The legacy root `train_model.py` is not the audited runner; it writes directly
to the active model path and should not be used for this experiment.

Validation commands:

```
.venv\Scripts\python.exe -m unittest discover -s tools -p test_spur_pipeline.py -v
cd smartpoultry
..\.venv\Scripts\python.exe manage.py test core.tests.RoosterAgeEstimatorTests core.test_chicken_detection --noinput
..\.venv\Scripts\python.exe manage.py check
```
