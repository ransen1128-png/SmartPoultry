# Executed poultry vision workflow

Status: 10 November 2026, Asia/Taipei. Experimental models, not established
independent-chicken accuracy.

## Data and annotations

The exhaustive dataset audit is in `../reports/dataset_audit/REPORT.md`.
15,205 dataset files represent 151 exact distinct photographs; extra identical
copies are not extra chickens. Existing user-verified age labels are preserved.
The actual number of independent chickens remains unresolved: recorded per-file
IDs conflict across duplicates and cannot establish animal identity.

Visual annotation produced 66 detailed review records. Of these, 43 photographs
with sufficiently resolved regions were exported: 71 leg boxes and 70 spur
polygons, spanning 40 conservative source families. The other 108 distinct
photographs remain intact, with exclusion reasons recorded; uncertain images
were not silently labeled negative. Assistant-drawn annotations are real visual
region annotations, but require independent expert review. Age labels were not
converted into boxes or masks. No hidden structures or physical scales were
invented.

Partitions: 27 training, 8 validation and 8 test photographs. Exact/near-copy
source families do not cross these splits. This is source-family separation,
not verified chicken-level separation. `annotation_manifest.json` preserves
image provenance, review notes and split membership.

## Executed training and results

Separate YOLO11 nano detection and segmentation models were trained on CPU.
`runs/*/args.yaml`, `results.csv`, evaluation JSON, plots and checkpoints preserve
executed parameters. The refined detector improved validation mAP50 from 0.419
to 0.591, although stricter localization remained weak. It is deployed as an
experimental candidate. Checkpoints were selected using validation, not test
performance; deployment thresholds use smoothed validation F1.

| Model | Validation mAP50 | Test mAP50 | Test mAP50-95 |
| --- | ---: | ---: | ---: |
| Leg/spur detector, boxes | 0.591 | 0.415 | 0.163 |
| Spur segmenter, masks | 0.463 | 0.239 | 0.144 |

These tiny holdouts and assistant annotations do not support a production
accuracy claim. Metrics above are model evaluation metrics, not confidence
for an uploaded photograph or the deployed two-model intersection pipeline.

Actual inference on all eight held-out originals completed and generated age
predictions. Five had spur boxes and two had accepted spur masks. Visual review
of `smoke/heldout_overlays.jpg` found genuine spur outlines on the two accepted
examples, but also missed spurs and inaccurate leg boxes, including a detached
spur classified as a leg. No claim of reliable negative-image rejection is made.

The original ResNet-18 remains active and unchanged, with its backup preserved.
The earlier age candidate was not promoted: validation MAE 5.07 months, test
MAE 6.93 months. The original historical MAE 1.03 months is compromised by
duplicate leakage and is not independent validation. See the age audit for
per-age metrics, bias/error tables and model comparison. Detection training does
not repair age-model generalization or change age preprocessing.

## Runtime integration

The existing Django upload page runs the original age estimator, actual local
OWL-ViT chicken detector, trained leg/spur detector and spur segmenter. It saves
actual boxes, masks, model hashes, outputs and errors in each estimate's analysis
JSON. Saved analysis can be reopened without rerunning inference. Image previews
remain owner-protected. Overlays display model coordinates, not invented regions.
No chicken body detection on a close-up is not proof of no chicken.

Only a segmentation polygon overlapping a detected spur box (IoU >= 0.15) is
accepted for measurement. Unmatched proposals remain recorded as unconfirmed.
Projected visible-mask centerline length is computed in pixels. Centimeters
require a finite positive known in-plane pixels-per-centimeter scale supplied
for one photograph; frame-truncated masks never receive a complete physical
length. Projection, occlusion and mask errors still affect this measurement.
No anatomical thickness, shape or curvature category is invented.

`smoke_django.py` exercises actual inference through upload, database saving,
saved-result reopening and protected image delivery. Its database writes are
rolled back and temporary media removed. `smoke/django_workflow.json` records
the result. Targeted tests cover failure handling, privacy, serialization,
calibration, geometry and unmatched masks. Original-source integrity is rechecked
with `tools/verify_spur_source_integrity.py`.

Verified: 22 targeted tests passed; real upload, saved-analysis and preview
requests each returned HTTP 200, anonymous preview access redirected to login.
The real 19-month source example produced an age estimate of 20.7 months,
one leg candidate, two spur boxes and two matching masks (257.02 and 165.72
visible centerline pixels). No centimeter scale was supplied or invented.
All 15,265 inventoried original workspace images and six metadata sources
remained unchanged; the original age checkpoint and its backup still match.
The running server health endpoint returned HTTP 200 and static assets were
collected for the updated overlay styles.

## Remaining information and review

### Saved-result follow-up

The browser was opening `?estimate=17`, which intentionally restored previously
saved raw predictions. Refreshing a saved analysis did not execute new models.
Saved-result pages now explain this and include an owner-only POST action to
analyze the stored photo again. The action creates a new result, records
`reanalysis_of`, and redirects to its own saved URL; the original analysis and
photo remain preserved. The updated suite passes 29 tests, including ownership
and original-result preservation checks. A local command for explicitly chosen
records is `python detection/reanalyze_saved_estimate.py <id>`.

### Whole-bird failure follow-up

The uploaded 415x739 `4months.jpg` exposed a body false negative and a
background leg false positive. A multi-query probe found a young-chicken body
candidate at approximately 0.269. Runtime queries now cover chicken, young
chicken, hen and rooster. Scores from 0.25 to 0.35 are shown explicitly as
possible body candidates, rather than a confirmed Yes. The original 0.35
stronger-detection threshold remains. This adjustment is not a calibrated
accuracy improvement across a representative negative-image set.

An anatomy-only result no longer implies the image is a close-up. When a body
box exists, leg proposals with centers outside all body boxes plus 5% margin
are suppressed from the displayed leg results, retained in
`out_of_body_leg_candidates`, and noted in the saved analysis. This heuristic
depends on body-box accuracy and can also suppress real legs when a body box
is inaccurate.

The actual 4-month source photo completed upload/save/reopen/preview with HTTP
200 and now reports a possible chicken body. Its age prediction remains 8.2
months; this detector fix does not correct age-model errors. The updated suite
contains 28 passing targeted tests.

The chicken assessment now combines body and anatomy evidence. When a body is
not detected but trained leg/spur models return candidates, the page reports a
possible chicken close-up, rather than relying exclusively on a whole-body box.
This is an experimental anatomy-based assessment, not independently validated
species identification. Raw detector states and boxes remain unchanged. The
updated targeted suite passed all 25 tests.

Independent reviewers should correct the marked contours and label the retained
ambiguous photographs, especially tiny, occluded and whole-bird spurs. Reviewed
negative photos are needed to measure false detections outside this collection.
A real chicken/capture register is needed to establish individual-level splits.
A photographed scale reference or known camera geometry is needed for defensible
physical measurements. None of these values can be recovered from age labels.
No additional image collection quota is assumed.
