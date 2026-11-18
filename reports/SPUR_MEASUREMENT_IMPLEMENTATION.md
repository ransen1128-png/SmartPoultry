# Spur measurement implementation ? localhost, 16 November 2026

Implemented and tested a separate visible-spur measurement workflow. Open a saved analysis and click **Review outline, base and tip**. Trace the visible boundary and mark the attachment base and distal tip, or request a model/API draft and correct it. Confirm visibility before saving.

The app calculates a curved path inside the outlined spur from base to tip. It reports projected pixel arc length. Centimeters require a known pixels-per-centimeter reference in the same image plane. Hidden endpoints, absent outlines and missing scales do not produce invented geometry or physical measurements. Perspective, image detail and tracing accuracy still affect the result; this is not a guaranteed anatomical ground truth measurement.

Reviews are saved separately with owner, timestamp, source-image hash and history. Existing photos, raw model predictions and age remain intact. API/candidate provenance is signed and bound to the account and image. Saving requires explicit visibility confirmation. Reviews do not automatically become training labels.

## Dataset and preservation

The existing age dataset contains **15,205 files, representing 151 distinct photographs in the earlier duplicate audit**. All 151 are available in the generated offline review editor at `detection/annotation_review/measurement_editor.html`. No request to collect another dataset was made.

31 reference photographs received assistant visual endpoint review. The initial candidate export used 27 eligible images (16 training, 6 validation, 5 test), 49 spur instances and 43 complete visible endpoint pairs. Unresolved endpoints remain unlabelled. These are assistant-reviewed drafts, not independently verified annotations.

The consistency check found **26 endpoint/outline conflicts** against existing coarse polygons. Human review must correct these before a reviewed export is accepted. Excluded images are recorded; they were not deleted. Unreviewed photographs are not treated as negative examples. Negative annotations require an explicit human confirmation that no visible spur is present.

Exact duplicates and source families remain in the same split. These source-family holdouts are not verified independent-chicken holdouts: persistent real individual identities remain unresolved. No independent-chicken accuracy claim is supported.

A preservation check compared 15,265 anchored original image files across the workspace and six metadata sources: no changes. The original trained age checkpoint and backup matched their previous hashes. All five existing age checkpoints were also fingerprinted before/after candidate training and stayed unchanged. No age labels or breed fields were introduced or changed.

## Executed training and evaluation

Actually trained separate YOLO11n pose (base/tip) and outline candidates: pose 50 epochs; segmentation stopped after 20 of a requested 40 epochs. CPU, 512-pixel input, batch 2, seed 20261116, deterministic settings. Candidate checkpoints and training arguments remain under `detection/runs/measurement_pose_v1` and `measurement_segment_v1`; existing deployed checkpoints were preserved.

| Outline mAP at IoU 0.50 | Existing model | New candidate |
|---|---:|---:|
| Validation, 6 source images | 0.6831 | 0.5954 |
| Test, 5 source images | 0.4070 | 0.4032 |

The existing outline model remains active. The candidate did not improve it.

The direct endpoint evaluation includes missed detections: validation 8/21 visible endpoints and test 2/13 landed within 10% of the labelled spur-box diagonal. Matched endpoint error averaged 8.24 pixels in validation and 20.10 pixels in test. These draft-labelled results are inadequate for automatic exact measurement. Candidate suggestions are explicitly review-only, registered separately in `ml_models/spur_measurement/candidates.json`; the local neural suggestion button is disabled on Render.

The user's 300 ? 300 whole-chicken photograph did not yield complete usable geometry from the new local candidate. Its age estimate stayed 13.1 months. Gemini returned a coarse polygon and base/tip draft in an executed request after simplifying an initially rejected response schema. That draft has not been independently confirmed and is not automatically saved as a measurement. The API button explicitly sends the photograph to Gemini; timeout/failure leaves manual review available. There is no actual calibrated physical-length result for this photograph.

## Review and retraining

1. Open the offline editor, inspect each photograph, correct outlines and visible endpoints, and explicitly mark reviewed images. Leave obscured points unknown. Export `detection/endpoint_reviews.reviewed.json`.
2. Export a new reviewed dataset. The exporter rejects inconsistent geometry, split leakage and unreviewed labels by default.
3. Train into new version folders, compare against the existing model, and evaluate endpoint accuracy directly. No automatic promotion occurs.

From the workspace root:

```powershell
.venv/Scripts/python.exe detection/build_endpoint_review.py --labels detection/endpoint_reviews.reviewed.json
.venv/Scripts/python.exe detection/export_measurement_annotations.py --labels detection/endpoint_reviews.reviewed.json --output detection/derived/measurement_reviewed_v2
.venv/Scripts/python.exe detection/train_measurement.py pose --dataset detection/derived/measurement_reviewed_v2 --epochs 50 --run-name measurement_pose_reviewed_v2
.venv/Scripts/python.exe detection/train_measurement.py segment --dataset detection/derived/measurement_reviewed_v2 --epochs 40 --run-name measurement_segment_reviewed_v2
.venv/Scripts/python.exe detection/compare_measurement_outlines.py --dataset detection/derived/measurement_reviewed_v2 --segment-run detection/runs/measurement_segment_reviewed_v2
.venv/Scripts/python.exe detection/evaluate_measurement_candidates.py --dataset detection/derived/measurement_reviewed_v2 --pose-run detection/runs/measurement_pose_reviewed_v2 --segment-run detection/runs/measurement_segment_reviewed_v2 --comparison detection/runs/measurement_segment_reviewed_v2/baseline_comparison.json
```

## Verification and remaining work

76 targeted Django tests passed, covering geometry, saved review history, ownership, CSRF, stale images, signed draft provenance, invalid API output, duplicate/split guards, existing inference paths and failure handling. Browser checks passed for manual drawing, saving, reopening, overlay endpoints, and exporting the 151-image annotation review. Browser checks used an isolated temporary database; the synthetic scale fixture tested conversion only and is not a real spur measurement. The actual Gemini geometry browser check also passed on the existing 300 ? 300 whole-chicken photo: six draft vertices and both endpoints were editable, confirmation started unchecked, signed provenance was present, and no measurement or analysis changes were saved automatically. No JavaScript errors were observed.

Localhost health returns HTTP 200 with the existing desktop PostgreSQL database. This task did not deploy or push changes to Render.

Still required for reliable automatic exact geometry: correct the flagged draft annotation conflicts, independently review visible spur boundaries/endpoints, evaluate on confirmed unseen chickens, and supply a measured image scale for centimeters. More copies of the existing photographs would not resolve these requirements. Automatic exact measurement is not ready; assisted review and visible-curve measurement are working.
