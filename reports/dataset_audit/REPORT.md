# SmartPoultry dataset inspection and model evaluation

Inspection date: 9 November 2026 (Asia/Taipei). Target: 1–24 months. No breed fields or features.

## Scope and preservation

The user corrected the dataset count to 15,205. All files in the workspace dataset and source-image folders were inspected. Environment, cache, collected static files and generated reports were excluded. The workspace contains 15,265 image files overall: 15,205 dataset photographs, 46 source-folder images, 9 uploaded media images and 5 project diagrams. These counts must not be added together as independent training photographs. A named downloaded SmartPoultry system folder was also inventoried and contained no image dataset or CSV metadata. No originals, original labels or original model weights were modified or deleted.

The existing checkpoint was copied to `spur_age/models/backups/resnet18_caf542a63c69a003f85ddeddb6777480e61601f13f3f2d58a82ef0c9cd6ef2b7.pth`. Both files have SHA-256 `caf542a63c69a003f85ddeddb6777480e61601f13f3f2d58a82ef0c9cd6ef2b7`.

The post-training integrity pass rehashed all 15,265 inventoried original workspace images and all six CSV sources: no files changed or disappeared. The original and backup checkpoint hashes still match. Evidence: `source_integrity.json`.

## Exhaustive file and metadata checks

| Check | Measured result |
|---|---:|
| Dataset image files | 15,205 |
| Primary CSV rows | 15,354 |
| CSV references to missing image files | 149 |
| Images without a primary age-label row | 0 |
| Invalid numeric ages outside 1–24 months | 0 |
| Duplicate filename rows in primary CSV | 0 |
| Corrupted dataset images (verify and full decode) | 0 |
| Distinct file SHA-256 hashes | 151 |
| Distinct decoded RGB pixel hashes | 151 |
| Extra exact-duplicate files | 15,054 |
| Identical-image groups with multiple chicken IDs | 151 |
| Identical-image groups with conflicting age values | 0 |

Every image has a corresponding numeric age label. The primary CSV has 149 references to absent files: 140 at age 1 month and 9 at age 13 months. Detailed filenames and row numbers are in `metadata_issues.csv`. All primary age values are valid integer months; all rows say `age_verified=yes`. That flag is recorded metadata, not independent proof of capture age by itself. The user subsequently explicitly confirmed that the existing age labels are verified; that confirmation is accepted and all ages are preserved. No numeric ages have been inferred or repaired from filenames.

There are 151 distinct decoded photographs, not 15,205 independent photographic observations. Distinct photographs can still show the same chicken. Each of the 151 duplicate groups contains multiple per-image chicken IDs. Contact sheets also show visually similar or sequential views that require identity/source-family review. Exact duplicates are proven by file and pixel hashes; perceptual similarity is only a review aid.

The existing `make_metadata.py` derives ages from filenames and initially leaves verification unset. `update_metadata.py` derives ages from filenames, assigns a new ID to each image and writes `age_verified=yes`. `train_model.py` assumes unique IDs per image and has no separate validation split. These are observed provenance risks; they do not establish that the supplied ages are wrong. The user confirmed ages after this finding. A persistent bird mapping is still not established by unique per-file IDs; the labels themselves were not changed.

## Every available CSV metadata source

| File | Rows | Nonempty distinct IDs |
|---|---:|---:|
| `spur_age\metadataset.csv` | 5 | 4 |
| `spur_age\dataset\metadata.csv` | 15,354 | 15,354 |
| `spur_age\dataset\metadata_backup.csv` | 29 | 28 |
| `spur_age\dataset\metadata_backup_20261026_204449.csv` | 1,715 | 1,714 |
| `spur_age\dataset\metadata_backup_20261104_160240.csv` | 1,671 | 1,671 |
| `spur_age\dataset\metadata_backup_20261104_183216.csv` | 4,941 | 4,941 |

Every row from all six CSVs was read and exported to `all_metadata_rows.csv`; column inventories, verification values, source hashes and age distributions are in `summary.json`. Backup CSVs overlap with the current dataset and must not be counted as additional photographs. Cross-version changes to IDs/ages are in `historical_metadata_differences.csv`; they are not automatically resolved.

Embedded EXIF, nested EXIF and IPTC metadata were also read from all 157 distinct workspace image files (including the 151 dataset images); all image frames were decoded and no animated images were found. Some files have camera dates, authorship and descriptive captions, but no usable persistent bird-ID, age-register mapping, structured localization or scale annotation was found. `embedded_image_metadata.json` preserves those fields separately; they are not predictive inputs.

## Counts for every age

| Age (months) | CSV rows | Present files | Missing files | Distinct decoded images |
|---:|---:|---:|---:|---:|
| 1 | 180 | 40 | 140 | 3 |
| 2 | 216 | 216 | 0 | 5 |
| 3 | 72 | 72 | 0 | 2 |
| 4 | 1170 | 1170 | 0 | 15 |
| 5 | 828 | 828 | 0 | 28 |
| 6 | 540 | 540 | 0 | 6 |
| 7 | 792 | 792 | 0 | 11 |
| 8 | 1080 | 1080 | 0 | 1 |
| 9 | 756 | 756 | 0 | 9 |
| 10 | 936 | 936 | 0 | 2 |
| 11 | 873 | 873 | 0 | 32 |
| 12 | 468 | 468 | 0 | 5 |
| 13 | 900 | 891 | 9 | 4 |
| 14 | 612 | 612 | 0 | 4 |
| 15 | 468 | 468 | 0 | 3 |
| 16 | 468 | 468 | 0 | 2 |
| 17 | 468 | 468 | 0 | 2 |
| 18 | 468 | 468 | 0 | 2 |
| 19 | 324 | 324 | 0 | 1 |
| 20 | 468 | 468 | 0 | 2 |
| 21 | 936 | 936 | 0 | 2 |
| 22 | 792 | 792 | 0 | 3 |
| 23 | 792 | 792 | 0 | 3 |
| 24 | 747 | 747 | 0 | 4 |

Age 8 has 1,080 files representing one distinct photograph; age 19 has 324 files representing one distinct photograph. Those copies cannot populate both training and an independent per-age test. This is a consequence of the completed inspection, not an assumption based on file count.

## Visual content and shortcut risks

All 151 distinct-image thumbnails were reviewed across `all_unique_1.jpg` through `all_unique_3.jpg`, and all 46 source thumbnails were reviewed. The corpus mixes whole chickens, legs/feet with visible spurs, tight spur views, detached spur/foot examples, human handling, and images with watermarks, text or drawn circles. Some spurs are too small or obscured in full-bird views to assess from the thumbnail. This review establishes mixed content, not fine-grained segmentation or verified subject identity. Each image still needs the review queue fields completed before making a verified chicken-independent claim. Text, watermarks, backgrounds and capture sessions are possible visual shortcuts. Removing filename input alone does not remove them.

## Executed evaluation of the existing ResNet-18

The actual preserved checkpoint was executed on all 151 distinct files using its original resize/normalization; predictions were expanded to every one of the 15,205 labeled files using exact file hashes. This reuse of identical image predictions is exact, not simulated inference. Full precision errors and rounded-month confusion counts are exported under `reports/existing_model_evaluation/`.

**These are contaminated diagnostic results, not independent validation or test results.** The original checkpoint lacks a split manifest. Its script was reconstructed using the current metadata, GroupShuffleSplit, seed 42 and a 20% test split. Of 3,071 reconstructed test rows, 3,044 image files remain available. **All 3,044 have identical pixel content in reconstructed training.** The original stored MAE of 1.0306 months therefore cannot be presented as established generalization to unseen chickens.

| Evaluation scope | Images | MAE (months) | Mean signed error (months) |
|---|---:|---:|---:|
| All present files, duplicate-weighted | 15,205 | 1.0230 | +0.4433 |
| Distinct files, equal weight | 151 | 1.5522 | +0.6682 |
| Available reconstructed test, 100% exact-pixel leakage | 3,044 | 1.0103 | +0.4102 |

| Age group | Present files | Diagnostic MAE (months) | Signed bias (months) |
|---|---:|---:|---:|
| 1-6 | 2,866 | 1.9710 | +1.2707 |
| 7-12 | 4,905 | 0.7559 | +0.1018 |
| 13-18 | 3,375 | 0.6643 | +0.0573 |
| 19-24 | 4,059 | 0.9746 | +0.5929 |

Positive signed error means overestimation. The 1–6 month group has the largest aggregate error and positive bias in this diagnostic. Monthly results, under/overestimation and prediction errors are in `per_age.csv` and `predictions.csv`; `confusion_rounded_months.csv` contains the full 24×24 rounded-prediction matrix. Continuous MAE uses unrounded predictions. A constant training-median predictor has reconstructed-test MAE 5.6367 months; this comparison is diagnostic only.

## Detection, segmentation and measurement annotations

| Task | Available ground truth | Minimum additional work on existing photographs |
|---|---|---|
| Image-to-age regression | Numeric ages explicitly confirmed verified by user | Establish persistent bird identities for chicken-independent evaluation; no boxes required for reviewed spur close-ups |
| Chicken detection | No structured chicken boxes found | Box visible chickens on full-bird views; mark close-ups as truncated/unknown rather than negative |
| Leg detection | No structured leg boxes found | Box anatomical shanks on visible legs, including partial views and reviewed negatives |
| Spur detection/localization | No boxes or keypoints found | Tight spur boxes, visibility/occlusion, absent-vs-hidden review; link each spur to its leg |
| Spur segmentation | No masks/polygons found | Polygon/mask per visible spur, with explicit occlusion policy, only if segmentation is needed |
| Spur length | No calibrated scale, base/tip labels or measurement records found | Define straight/curved length; mark base/tip or centerline and use a known in-plane scale/calibration |

The full annotation-file inventory is in `annotation_file_inventory.csv`. Existing CSVs contain image, age, ID, verification and note fields only. Model/tokenizer configuration JSONs and the unpopulated detection YAML are not detection ground truth. Raster text/circles are not structured boxes or masks. No boxes, masks, physical lengths or detection successes were fabricated.

The immediate review queue has **151 rows, one per distinct existing image**, rather than asking for 15,205 repeated annotations or a new 30,000-image collection. Review similar frames into source families first; actual unique-chicken count is unknown. Annotate selected existing representatives for a pilot and separate validation/test families, then expand based on measured errors. A defensible minimum detector training count cannot be inferred from image count alone. Duplicate copies inherit an annotation only after exact identity is confirmed, using derived files and leaving originals intact.

## Executed candidate training and model selection

The 151 distinct images form 62 conservative visual families. Grouping used 281 automatic pair matches and 23 conservative contact-sheet review unions. Pixel hashes, pHash, structural similarity with a horizontal-flip check, and frozen ImageNet ResNet-18 features were used; age labels and filenames were not similarity inputs. The explicit thresholds and membership are in `visual_family_summary.json`, `near_duplicate_pairs.csv`, `reviewed_family_unions.csv` and `visual_family_manifest.csv`. Conservative merges may include different individuals; they prevent splitting visually indistinguishable examples but do not assert identity.

**Actual independent chicken count: unresolved.** The measured counts are 151 distinct photographs and 62 conservative visual families, not 62 verified chickens. Images alone and inconsistent per-copy IDs cannot establish that count. A persistent photo-to-bird mapping is the exact information still missing.

A separate ImageNet-initialized ResNet-18 regression candidate was actually trained for 100 epochs on frozen image features with an L1 regression head, Adam, seed 42 and inverse family-size weighting. Batch-normalization statistics stayed frozen. All 151 distinct photographs were retained across 130 training, 11 validation and 10 test photographs. The original 15,205 files stayed untouched; duplicate aliases remain in the exhaustive inventory. The 149 absent paths are reported, not silently filled. Validation selected the best epoch; the test set was not used for model selection.

No exact-pixel group, detected near-duplicate pair, reviewed source family or recorded ID crosses the splits. This is a **visual-family holdout experiment**, not a fully verified chicken-independent test. Unrecognized same-bird views remain a limitation until the persistent mapping is supplied. The split includes ages with no validation/test representative; those monthly rows have n=0 and blank metrics rather than invented scores. Single-distinct-image ages cannot appear in both train and independent test.

| Model | Validation MAE (months; n=11) | Test MAE (months; n=10) | Interpretation |
|---|---:|---:|---|
| New candidate | 5.0721 | 6.9276 | New visual-family holdout; identity unresolved |
| Existing ResNet-18 | 1.2582 | 2.0971 | May have seen these photographs in original training |
| Constant training-median baseline | 6.0909 | 8.2000 | Uses training ages only |

The candidate has substantial error and was **not promoted**. The existing checkpoint remains active only for estimates explicitly labeled experimental. The old model's lower scores are not an independent head-to-head victory because its prior training overlap is unknown. A new-versus-old verified chicken-independent comparison remains unavailable.

Candidate and all run artifacts: `spur_age\experiments\20261109T074813049131Z`. These include the checkpoint, full split manifest, configuration and library versions, 100-epoch validation history, per-image residuals, per-age/per-age-group MAE and bias, and 24×24 rounded-month confusion matrices for both models. Two full training runs with the same seed produced identical model tensors, split manifests and validation/test metrics; see `reproducibility.json`.

On the 10-image candidate test, the 1–6 month group (n=4) is overestimated by 5.395 months on average; the 19–24 month group (n=3) is underestimated by 11.071 months. Intermediate groups contain only one or two examples. This bias toward middle ages, missing monthly coverage and large errors are reasons to withhold promotion, not evidence of deployment readiness.

## Django integration and exact remaining work

The upload page executes the preserved model on readable uploads by default. Brightness, contrast and focus heuristics are warnings rather than inference blockers; unreadable files and model failures still report why no prediction was generated. The page never converts an estimate into a positive detection. Image quality, actual model output/hash, input mode, detector status/boxes and unavailable segmentation/measurement states are saved in a JSON analysis field. Uploaded photo previews use an owner-authenticated route that works with DEBUG disabled. The additive migration was applied. Historical MAE is labeled as contaminated and is not shown as calibrated confidence. Actual-image upload tests verified equal predictions when only the filename changes. The poor candidate is not substituted for the existing model.

The local launcher previously selected `venv`, which lacks PyTorch. It now prefers the tested `.venv` runtime. The local server was restarted in that environment; both the login page and `__health/` returned HTTP 200, and the health endpoint reported ok=true.

To complete verified chicken-level evaluation, supply the persistent mapping for the 151 distinct photos and review same-session/source relationships. Verified ages are already accepted and need not be re-created. To complete automatic spur assessment, fill real visibility/box annotations in the 151-row representative queue and follow `detection/README.md`. Segmentation and calibrated physical length require the additional annotations described above. No detector success or physical measurement is claimed. Nothing here requires collecting another 30,000 photographs.

Validation completed: 9 Django estimator/detector tests (including actual-image model inference), 5 audit/split safety tests, Django system checks, and a clean core migration check. The repository has pre-existing migration drift in unrelated apps; it was not altered. The additive core analysis migration applied successfully.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools/audit_spur_dataset.py
.\.venv\Scripts\python.exe tools/evaluate_existing_age_model.py
.\.venv\Scripts\python.exe tools/group_spur_image_families.py
.\.venv\Scripts\python.exe tools/train_verified_spur_age.py --content-family-experiment --epochs 100
.\.venv\Scripts\python.exe tools/write_spur_audit_report.py
```

The machine-readable CSVs contain every image/metadata row; this document summarizes them. The audit performs no deduplication, deletion, renaming or label edits.
