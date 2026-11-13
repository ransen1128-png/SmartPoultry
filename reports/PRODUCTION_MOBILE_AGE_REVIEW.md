# Production, mobile and age-estimation review

Executed locally on 2026-11-13. No Render deployment was performed.

## Older production sales

Added **Revenue → Reconcile older sales with production**, also linked from Production Records. Each account sees only its own unlinked sales. Confirming a source batch links the existing sale, deducts available stock, preserves quantity/price/total and writes reconciliation details into the transaction audit. Produced quantities are retained. Repeated linking, cross-account access and overselling are rejected.

The desktop audit found **4 unlinked sales; none were changed automatically**. One has a compatible batch but lacks its original flock reference. Three have no compatible batch: missing production, insufficient eligible stock, or conflicting unit/date information. Selecting a candidate requires confirmation of the actual source. The system does not invent conversions or split sales across batches. Detailed private review: `.postgres-migration/legacy-stock-review.json`.

This work does not audit Render's separate database. Run `tools/audit_stock_reconciliation.py` against the intended database to inspect its legacy records.

## Smaller screens

Wrapped the Flocks, Inventory, Revenue, Expenses and Reports tables in horizontal scroll containers. Fixed dashboard chart/grid sizing and filter wrapping without changing desktop styling. Real Chrome checks passed for all **17 page/panel/dialog checks at each of 320, 390 and 768 pixels**. Checks included production/mortality add forms, inventory/revenue/expense dialogs, both Settings panels, reports and the age-estimator page. Separate desktop Settings verification passed, including password visibility controls. No settings were submitted during the review.

Reproduce: `python tools/audit_mobile_layout.py --width 390`. Browser reports/screenshots are under `.postgres-migration/`; this requires the local server and an existing test-owner session account (currently ID 3).

## Age evaluation

No age model was trained, replaced or promoted in this review. Original images and verified labels were preserved.

`tools/summarize_age_evaluation.py` reanalyses the existing saved predictions with per-age and grouped-age metrics, bias, largest errors, rounded-month confusion tables and reproducible source-family bootstrap intervals. Results: `reports/age_evaluation_review/`. Empty age groups have no fabricated metrics. These intervals describe the available sample; they do not correct training exposure or prove independent performance.

Existing source-family test diagnostics (10 photographs): original MAE **2.097 months**, fine-tuned MAE **2.025 months**. Within one month: original 40%, fine-tuned 30%. The MAE reduction therefore does not imply improvement on every measure. These are not unseen-chicken results because earlier checkpoint exposure and real bird identities remain unresolved.

Executed `tools/evaluate_unseen_chickens.py`: all **46** photographs in `spurs images` are already represented among the **151** known distinct photographs. No verified independent test set was available. The runner writes a manifest template, validates ages/provenance, blocks file/pixel duplicates and flags perceptually similar frames. It requires human-confirmed identity, age and training-membership references; hashes alone cannot prove animal identity. When a qualifying manifest exists, it evaluates the selected model and reports per-image errors, age metrics and chicken-balanced MAE without training.

Required missing information is a capture/register reference establishing which photographed individuals were excluded from **all prior training**, including the original checkpoint. Existing corpus labels remain unchanged. Merely giving a duplicate photo another chicken ID does not meet this requirement.

## API comparison

Credentials are configured; credentials themselves are never written into the report. Actual image generation/localization with the configured `gemini-3.8-flash` timed out. An alternate `gemini-2.5-flash` probe returned HTTP 404: the provider disallows that model for this account. The validation runner now stops after the first provider failure and writes incremental progress instead of repeatedly waiting for the entire batch. The latest attempt processed one of eleven validation inputs, failed, and used no API crops. **No API accuracy improvement was measured; no independent API test was run; live estimation was not switched to the API.**

API status and failure evidence: `reports/vision_api/readiness.json`, `validation.json`, `progress.json`. Retry-count control preserves the live API helper's existing default while allowing single-attempt offline benchmarking. Failed comparisons cannot unlock test evaluation.

## Verification

- 14 Django revenue/API contract tests passed, including reconciliation audit, ownership, incompatible units and repeat-link protection.
- 3 evaluation-gate tests passed, including duplicate-photo identity changes and unsupported provenance.
- 51 mobile checks and separate desktop Settings checks passed.
- The independent evaluation readiness command deliberately reports a blocked status; it is not a successful independent evaluation.
