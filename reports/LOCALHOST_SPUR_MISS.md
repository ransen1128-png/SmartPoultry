# Localhost spur miss: 16 November 2026

The uploaded 300 x 300 whole-rooster photograph is available as the unchanged
regression fixture `smartpoultry/core/testdata/full_chicken.jpg`. Its curved pale
protrusion near the visible lower leg is missed by the installed spur models.
No successful local-model spur detection, segmentation or measurement is claimed
by this diagnostic. The later optional API integration is documented separately
in `LOCALHOST_SPUR_API.md`.

## Executed investigation

- Reproduced the active 512-pixel pipeline: one leg, zero accepted spur boxes,
  zero masks and zero length measurements.
- Tested three crops around the real detected leg, at 1.5, 2 and 2.5 times its
  longest box side. All retained the original model thresholds; none produced
  an accepted spur box or mask.
- Inspected low-threshold raw outputs. The full-image detector proposed a spur
  on the head at score 0.7482. Lowering the active 0.75 threshold would admit that
  incorrect region. The enlarged leg crop's best relevant detector and segmenter
  proposals were about 0.032 and 0.098 respectively.
- Tested 640/1024-pixel inputs and horizontal reflection. A 1024-pixel full-image
  pass produced a more relevant box near the spur at score 0.3725; reflection
  raised it to 0.4911. These probe scores do not establish correctness or justify
  choosing thresholds on this photograph.
- An offline OWL-ViT spur-query probe also proposed the whole body as a spur;
  it was not integrated as a replacement.

## Validation of the higher-resolution hypothesis

Both installed models were evaluated at 512 and 1024 pixels on the existing
eight-image validation split. Neither the test split nor this uploaded photograph
was used to select a replacement operating threshold. Details are in
`SPUR_RESOLUTION_VALIDATION.json` and `detection/runs/localhost_spur_diagnostic_*`.

| Validation measure | 512 pixels | 1024 pixels |
|---|---:|---:|
| Leg/spur detector box mAP50 | 0.5743 | 0.2286 |
| Spur segmenter mask mAP50 | 0.5159 | 0.2058 |

Higher resolution was rejected as a general runtime change. These small,
assistant-annotated holdouts do not establish accuracy on independent chickens.
Batch/rectangle preprocessing differs from historical evaluation, so these fresh
metrics are compared within this experiment, not substituted for the old report.

## What is missing

The existing anatomy export contains 43 eligible annotated photographs, split
27 train / 8 validation / 8 test, with 71 leg boxes and 70 spur polygons overall.
Its provenance explicitly requires human review. The verified age labels remain
separate from these anatomical annotations.

The required next work is review of small visible spur boxes and outlines in
existing full-body photographs, visibility/occlusion flags, and reviewed negative
examples that cover heads, feathers, feet and backgrounds. The current validation
export contains no background-only images. Age labels do not supply those regions.
No additional photograph collection is assumed or requested.

`detection/review_tasks/full_chicken_spur_miss.json` records a pending review task
with the real image hash and **null annotations**, not guessed training labels.
Keep this reported regression image out of training when claiming independent
performance on it. Correct existing visual annotations, retain source-family
separation, export via `detection/export_reviewed_annotations.py`, then train
separate candidates via `detection/train_anatomy.py`. Select thresholds/checkpoints
using validation and evaluate the held-out test split before promotion. Compare
missed-spur and false-positive rates as well as aggregate mAP.

This diagnostic did not change source photographs, verified ages, trained
checkpoints or saved customer analyses. No retraining was performed. The later
localhost API changes preserve those artifacts as well. The age estimate does
not imply a detected or measured spur.
