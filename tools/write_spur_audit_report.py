"""Render measured audit/evaluation artifacts into a human-readable report."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
audit = ROOT / 'reports/dataset_audit'
s = json.loads((audit / 'summary.json').read_text())
e = json.loads((ROOT / 'reports/existing_model_evaluation/metrics.json').read_text())
family = json.loads((audit / 'visual_family_summary.json').read_text())
readiness = json.loads((audit / 'training_readiness.json').read_text())
run = Path(readiness['run'])
comparison = json.loads((run / 'comparison.json').read_text())
lines = [
    '# SmartPoultry dataset inspection and model evaluation', '',
    'Inspection date: 9 November 2026 (Asia/Taipei). Target: 1–24 months. No breed fields or features.', '',
    '## Scope and preservation', '',
    'The user corrected the dataset count to 15,205. All files in the workspace dataset and source-image folders were inspected. '
    'Environment, cache, collected static files and generated reports were excluded. The workspace contains 15,265 image files overall: '
    '15,205 dataset photographs, 46 source-folder images, 9 uploaded media images and 5 project diagrams. '
    'These counts must not be added together as independent training photographs. '
    'A named downloaded SmartPoultry system folder was also inventoried and contained no image dataset or CSV metadata. '
    'No originals, original labels or original model weights were modified or deleted.', '',
    'The existing checkpoint was copied to `spur_age/models/backups/resnet18_' + e['checkpoint_sha256'] + '.pth`. '
    'Both files have SHA-256 `' + e['checkpoint_sha256'] + '`.', '',
    'The post-training integrity pass rehashed all 15,265 inventoried original workspace images and all six '
    'CSV sources: no files changed or disappeared. The original and backup checkpoint hashes still match. '
    'Evidence: `source_integrity.json`.', '',
    '## Exhaustive file and metadata checks', '',
    '| Check | Measured result |', '|---|---:|',
]
for title, key in [
    ('Dataset image files', 'dataset_image_files'), ('Primary CSV rows', 'primary_metadata_rows'),
    ('CSV references to missing image files', 'primary_missing_files'),
    ('Images without a primary age-label row', 'dataset_images_without_primary_label'),
    ('Invalid numeric ages outside 1–24 months', 'primary_invalid_ages'),
    ('Duplicate filename rows in primary CSV', 'primary_duplicate_image_references'),
    ('Corrupted dataset images (verify and full decode)', 'corrupt_dataset_images'),
    ('Distinct file SHA-256 hashes', 'dataset_unique_file_hashes'),
    ('Distinct decoded RGB pixel hashes', 'dataset_unique_decoded_pixel_hashes'),
    ('Extra exact-duplicate files', 'dataset_duplicate_decoded_pixel_excess'),
    ('Identical-image groups with multiple chicken IDs', 'identical_pixel_groups_with_multiple_ids'),
    ('Identical-image groups with conflicting age values', 'identical_pixel_groups_with_conflicting_ages'),
]:
    lines.append(f'| {title} | {s[key]:,} |')
lines += ['',
    'Every image has a corresponding numeric age label. The primary CSV has 149 references to absent files: '
    '140 at age 1 month and 9 at age 13 months. Detailed filenames and row numbers are in `metadata_issues.csv`. '
    'All primary age values are valid integer months; all rows say `age_verified=yes`. That flag is recorded metadata, '
    'not independent proof of capture age by itself. The user subsequently explicitly confirmed that the existing '
    'age labels are verified; that confirmation is accepted and all ages are preserved. '
    'No numeric ages have been inferred or repaired from filenames.', '',
    'There are 151 distinct decoded photographs, not 15,205 independent photographic observations. '
    'Distinct photographs can still show the same chicken. Each of the 151 duplicate groups contains multiple '
    'per-image chicken IDs. Contact sheets also show visually similar or sequential views that require identity/source-family review. '
    'Exact duplicates are proven by file and pixel hashes; perceptual similarity is only a review aid.', '',
    'The existing `make_metadata.py` derives ages from filenames and initially leaves verification unset. '
    '`update_metadata.py` derives ages from filenames, assigns a new ID to each image and writes `age_verified=yes`. '
    '`train_model.py` assumes unique IDs per image and has no separate validation split. '
    'These are observed provenance risks; they do not establish that the supplied ages are wrong. '
    'The user confirmed ages after this finding. A persistent bird mapping is still not established by '
    'unique per-file IDs; the labels themselves were not changed.', '',
    '## Every available CSV metadata source', '',
    '| File | Rows | Nonempty distinct IDs |', '|---|---:|---:|',
]
for source in s['metadata_sources']:
    lines.append(f"| `{source['path']}` | {source['rows']:,} | {source['unique_nonempty_ids']:,} |")
lines += ['',
    'Every row from all six CSVs was read and exported to `all_metadata_rows.csv`; column inventories, '
    'verification values, source hashes and age distributions are in `summary.json`. Backup CSVs overlap '
    'with the current dataset and must not be counted as additional photographs. Cross-version changes '
    'to IDs/ages are in `historical_metadata_differences.csv`; they are not automatically resolved.', '',
    'Embedded EXIF, nested EXIF and IPTC metadata were also read from all 157 distinct workspace image files '
    '(including the 151 dataset images); all image frames were decoded and no animated images were found. '
    'Some files have camera dates, authorship and descriptive captions, but no usable persistent bird-ID, '
    'age-register mapping, structured localization or scale annotation was found. '
    '`embedded_image_metadata.json` preserves those fields separately; they are not predictive inputs.', '',
    '## Counts for every age', '',
    '| Age (months) | CSV rows | Present files | Missing files | Distinct decoded images |',
    '|---:|---:|---:|---:|---:|',
]
for r in s['age_distribution']:
    lines.append(f"| {r['age_months']} | {r['metadata_rows']} | {r['present_images']} | {r['missing_images']} | {r['decoded_pixel_unique']} |")
lines += ['',
    'Age 8 has 1,080 files representing one distinct photograph; age 19 has 324 files representing one distinct photograph. '
    'Those copies cannot populate both training and an independent per-age test. This is a consequence of the '
    'completed inspection, not an assumption based on file count.', '',
    '## Visual content and shortcut risks', '',
    'All 151 distinct-image thumbnails were reviewed across `all_unique_1.jpg` through `all_unique_3.jpg`, '
    'and all 46 source thumbnails were reviewed. The corpus mixes whole chickens, legs/feet with visible spurs, '
    'tight spur views, detached spur/foot examples, human handling, and images with watermarks, text or drawn circles. '
    'Some spurs are too small or obscured in full-bird views to assess from the thumbnail. This review establishes '
    'mixed content, not fine-grained segmentation or verified subject identity. Each image still needs the review '
    'queue fields completed before making a verified chicken-independent claim. Text, watermarks, backgrounds '
    'and capture sessions are possible visual shortcuts. Removing filename input alone does not remove them.', '',
    '## Executed evaluation of the existing ResNet-18', '',
    'The actual preserved checkpoint was executed on all 151 distinct files using its original resize/normalization; '
    'predictions were expanded to every one of the 15,205 labeled files using exact file hashes. '
    'This reuse of identical image predictions is exact, not simulated inference. Full precision errors and '
    'rounded-month confusion counts are exported under `reports/existing_model_evaluation/`.', '',
    '**These are contaminated diagnostic results, not independent validation or test results.** '
    'The original checkpoint lacks a split manifest. Its script was reconstructed using the current metadata, '
    'GroupShuffleSplit, seed 42 and a 20% test split. Of 3,071 reconstructed test rows, 3,044 image files remain '
    'available. **All 3,044 have identical pixel content in reconstructed training.** The original stored MAE '
    'of 1.0306 months therefore cannot be presented as established generalization to unseen chickens.', '',
    '| Evaluation scope | Images | MAE (months) | Mean signed error (months) |',
    '|---|---:|---:|---:|',
]
for label, key in [('All present files, duplicate-weighted', 'full_corpus'),
                   ('Distinct files, equal weight', 'distinct_files'),
                   ('Available reconstructed test, 100% exact-pixel leakage', 'reconstructed_test')]:
    m = e[key]
    lines.append(f"| {label} | {m['n']:,} | {m['mae_months']:.4f} | {m['bias_months']:+.4f} |")
lines += ['',
    '| Age group | Present files | Diagnostic MAE (months) | Signed bias (months) |',
    '|---|---:|---:|---:|',
]
for m in e['per_age_group']:
    lines.append(f"| {m['age_group']} | {m['n']:,} | {m['mae_months']:.4f} | {m['bias_months']:+.4f} |")
lines += ['',
    'Positive signed error means overestimation. The 1–6 month group has the largest aggregate error '
    'and positive bias in this diagnostic. Monthly results, under/overestimation and prediction errors '
    'are in `per_age.csv` and `predictions.csv`; `confusion_rounded_months.csv` contains the full 24×24 '
    'rounded-prediction matrix. Continuous MAE uses unrounded predictions. '
    'A constant training-median predictor has reconstructed-test MAE '
    f"{e['constant_median_reconstructed_test']['mae_months']:.4f} months; this comparison is diagnostic only.", '',
    '## Detection, segmentation and measurement annotations', '',
    '| Task | Available ground truth | Minimum additional work on existing photographs |',
    '|---|---|---|',
    '| Image-to-age regression | Numeric ages explicitly confirmed verified by user | Establish persistent bird identities for chicken-independent evaluation; no boxes required for reviewed spur close-ups |',
    '| Chicken detection | No structured chicken boxes found | Box visible chickens on full-bird views; mark close-ups as truncated/unknown rather than negative |',
    '| Leg detection | No structured leg boxes found | Box anatomical shanks on visible legs, including partial views and reviewed negatives |',
    '| Spur detection/localization | No boxes or keypoints found | Tight spur boxes, visibility/occlusion, absent-vs-hidden review; link each spur to its leg |',
    '| Spur segmentation | No masks/polygons found | Polygon/mask per visible spur, with explicit occlusion policy, only if segmentation is needed |',
    '| Spur length | No calibrated scale, base/tip labels or measurement records found | Define straight/curved length; mark base/tip or centerline and use a known in-plane scale/calibration |', '',
    'The full annotation-file inventory is in `annotation_file_inventory.csv`. Existing CSVs contain '
    'image, age, ID, verification and note fields only. Model/tokenizer configuration JSONs and the '
    'unpopulated detection YAML are not detection ground truth. Raster text/circles are not structured '
    'boxes or masks. No boxes, masks, physical lengths or detection successes were fabricated.', '',
    'The immediate review queue has **151 rows, one per distinct existing image**, rather than asking '
    'for 15,205 repeated annotations or a new 30,000-image collection. Review similar frames into source '
    'families first; actual unique-chicken count is unknown. Annotate selected existing representatives '
    'for a pilot and separate validation/test families, then expand based on measured errors. A defensible '
    'minimum detector training count cannot be inferred from image count alone. Duplicate copies inherit '
    'an annotation only after exact identity is confirmed, using derived files and leaving originals intact.', '',
    '## Executed candidate training and model selection', '',
    f"The 151 distinct images form {family['conservative_visual_families']} conservative visual families. "
    f"Grouping used {family['automatically_grouped_pairs']} automatic pair matches and {family['human_reviewed_unions']} conservative "
    'contact-sheet review unions. Pixel hashes, pHash, structural similarity with a horizontal-flip check, '
    'and frozen ImageNet ResNet-18 features were used; age labels and filenames were not similarity inputs. '
    'The explicit thresholds and membership are in `visual_family_summary.json`, `near_duplicate_pairs.csv`, '
    '`reviewed_family_unions.csv` and `visual_family_manifest.csv`. Conservative merges may include different '
    'individuals; they prevent splitting visually indistinguishable examples but do not assert identity.', '',
    '**Actual independent chicken count: unresolved.** The measured counts are 151 distinct photographs and '
    '62 conservative visual families, not 62 verified chickens. Images alone and inconsistent per-copy IDs '
    'cannot establish that count. A persistent photo-to-bird mapping is the exact information still missing.', '',
    'A separate ImageNet-initialized ResNet-18 regression candidate was actually trained for 100 epochs '
    'on frozen image features with an L1 regression head, Adam, seed 42 and inverse family-size weighting. '
    'Batch-normalization statistics stayed frozen. All 151 distinct photographs were retained across '
    '130 training, 11 validation and 10 test photographs. The original 15,205 files stayed untouched; '
    'duplicate aliases remain in the exhaustive inventory. The 149 absent paths are reported, not silently filled. '
    'Validation selected the best epoch; the test set was not used for model selection.', '',
    'No exact-pixel group, detected near-duplicate pair, reviewed source family or recorded ID crosses '
    'the splits. This is a **visual-family holdout experiment**, not a fully verified chicken-independent '
    'test. Unrecognized same-bird views remain a limitation until the persistent mapping is supplied. '
    'The split includes ages with no validation/test representative; those monthly rows have n=0 and '
    'blank metrics rather than invented scores. Single-distinct-image ages cannot appear in both train '
    'and independent test.', '',
    '| Model | Validation MAE (months; n=11) | Test MAE (months; n=10) | Interpretation |',
    '|---|---:|---:|---|',
    f"| New candidate | {comparison['candidate_validation']['mae_months']:.4f} | {comparison['candidate_test']['mae_months']:.4f} | New visual-family holdout; identity unresolved |",
    f"| Existing ResNet-18 | {comparison['existing_validation']['mae_months']:.4f} | {comparison['existing_test']['mae_months']:.4f} | May have seen these photographs in original training |",
    f"| Constant training-median baseline | {comparison['constant_median_validation']['mae_months']:.4f} | {comparison['constant_median_test']['mae_months']:.4f} | Uses training ages only |", '',
    'The candidate has substantial error and was **not promoted**. The existing checkpoint remains '
    'active only for estimates explicitly labeled experimental. The old model\'s lower scores are not an '
    'independent head-to-head victory because its prior training overlap is unknown. A new-versus-old '
    'verified chicken-independent comparison remains unavailable.', '',
    f"Candidate and all run artifacts: `{run.relative_to(ROOT)}`. These include the checkpoint, full split "
    'manifest, configuration and library versions, 100-epoch validation history, per-image residuals, '
    'per-age/per-age-group MAE and bias, and 24×24 rounded-month confusion matrices for both models. '
    'Two full training runs with the same seed produced identical model tensors, split manifests and '
    'validation/test metrics; see `reproducibility.json`.', '',
    'On the 10-image candidate test, the 1–6 month group (n=4) is overestimated by 5.395 months on average; '
    'the 19–24 month group (n=3) is underestimated by 11.071 months. Intermediate groups contain only '
    'one or two examples. This bias toward middle ages, missing monthly coverage and large errors are '
    'reasons to withhold promotion, not evidence of deployment readiness.', '',
    '## Django integration and exact remaining work', '',
    'The upload page executes the preserved model on readable uploads by default. Brightness, contrast '
    'and focus heuristics are warnings rather than inference blockers; unreadable files and model failures '
    'still report why no prediction was generated. The page never converts an estimate into a positive '
    'detection. Image quality, actual '
    'model output/hash, input mode, detector status/boxes and unavailable segmentation/measurement states '
    'are saved in a JSON analysis field. Uploaded photo previews use an owner-authenticated route that '
    'works with DEBUG disabled. The additive migration was applied. Historical MAE is labeled '
    'as contaminated and is not shown as calibrated confidence. Actual-image upload tests verified equal '
    'predictions when only the filename changes. The poor candidate is not substituted for the existing model.', '',
    'The local launcher previously selected `venv`, which lacks PyTorch. It now prefers the tested `.venv` '
    'runtime. The local server was restarted in that environment; both the login page and `__health/` '
    'returned HTTP 200, and the health endpoint reported ok=true.', '',
    'To complete verified chicken-level evaluation, supply the persistent mapping for the 151 distinct photos '
    'and review same-session/source relationships. Verified ages are already accepted and need not be '
    're-created. To complete automatic spur assessment, fill real visibility/box annotations in the '
    '151-row representative queue and follow `detection/README.md`. Segmentation and calibrated physical '
    'length require the additional annotations described above. No detector success or physical measurement '
    'is claimed. Nothing here requires collecting another 30,000 photographs.', '',
    'Validation completed: 9 Django estimator/detector tests (including actual-image model inference), '
    '5 audit/split safety tests, Django system checks, and a clean core migration check. '
    'The repository has pre-existing migration drift in unrelated apps; it was not altered. '
    'The additive core analysis migration applied successfully.', '',
    '## Reproduce', '',
    '```powershell',
    '.\\.venv\\Scripts\\python.exe tools/audit_spur_dataset.py',
    '.\\.venv\\Scripts\\python.exe tools/evaluate_existing_age_model.py',
    '.\\.venv\\Scripts\\python.exe tools/group_spur_image_families.py',
    '.\\.venv\\Scripts\\python.exe tools/train_verified_spur_age.py --content-family-experiment --epochs 100',
    '.\\.venv\\Scripts\\python.exe tools/write_spur_audit_report.py',
    '```', '',
    'The machine-readable CSVs contain every image/metadata row; this document summarizes them. '
    'The audit performs no deduplication, deletion, renaming or label edits.', '',
]
(audit / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
print(audit / 'REPORT.md')
