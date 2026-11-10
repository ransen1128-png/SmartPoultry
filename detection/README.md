# Detection workflow

## Executed implementation (10 November 2026)

The local app now loads real OWL-ViT chicken weights and separately trained
leg/spur YOLO11 detection and spur segmentation checkpoints. See
`IMPLEMENTATION_REPORT.md` for measured performance and limitations. These
outputs remain experimental; missed regions and incorrect boxes are expected.

Reproduce the annotation export and training from the workspace root:

```powershell
.\.venv\Scripts\python.exe detection\export_reviewed_annotations.py
.\.venv\Scripts\python.exe detection\train_anatomy.py detect --epochs 60
.\.venv\Scripts\python.exe detection\train_anatomy.py segment --epochs 45 --freeze 0 --initial-optimizer-settings
.\.venv\Scripts\python.exe detection\deploy_anatomy.py
.\.venv\Scripts\python.exe detection\smoke_anatomy.py
.\.venv\Scripts\python.exe detection\smoke_django.py
```

The deployment manifest records checkpoint hashes, validation-selected thresholds
and evaluation results. Derived data and annotation previews are separate from
original photographs. Human review should correct `manual_annotations.json`,
then rerun export and training. The older sections below describe annotation
guidance and initial investigation; they are not current deployment status.

The age checkpoint at `spur_age/models/spur_age_model.pth` is independent and is
never written by these tools. No breed labels are collected.

## Chicken detector

Install `requirements-detection.txt`, then run `python setup_chicken_detector.py`
and restart Django. We use OWL-ViT with the query `a photo of a chicken`, not
COCO's generic bird class. Web requests load only local files and report
unavailable or failed detection distinctly from no detection above threshold.
Boxes use EXIF-oriented original-image pixel coordinates (left, top, right,
bottom). Body queries cover chicken, young chicken, hen and rooster. Scores
0.25 to 0.35 are reported as lower-score possible body candidates; scores >=0.35
retain the detector's experimental detection status. These thresholds require
broader local validation and do not establish species certainty.
Scores are not calibrated probabilities. Multiple boxes are reported; they are
not interpreted as a reliable bird count. Age inference runs separately on readable
uploads as an experimental estimate; it does not imply verified localization.

Source: https://huggingface.co/google/owlvit-base-patch32

## Leg detector investigation

OWL-ViT supports text queries and is a candidate for an offline experiment with
`a chicken leg` and `a chicken shank`. It has no published validation here for
this task, so leg detection is deliberately not enabled. Generic COCO bird boxes
and human pose leg keypoints are not chicken-leg detectors. A study on thermal
chicken head/leg detection used its own labeled regions; those results do not
establish performance on our RGB uploads:
https://www.mdpi.com/2076-2615/15/8/1114

Evaluate on separately labeled RGB images: close-up legs, whole birds, occluded
legs, multiple birds and non-chicken negatives. Report box precision/recall and
misses by lighting and age. If unsuitable, train the leg class below. Do not
infer a leg box by selecting the bottom of a chicken box.

## Separate leg and spur annotations

Copy images into a NEW dataset; do not relabel or move the age dataset. Record
bird/session IDs and split by bird before annotation/export to prevent leakage.
Annotate tight boxes for visible anatomical shanks (`leg`, class 0) and spurs
(`spur`, class 1) in CVAT or Label Studio. Do not box toes as spurs. Include tiny,
partially occluded and absent spurs, plus difficult negative images. An invisible
spur is unknown, not proof of absence. Store visibility/occlusion and bird IDs
in annotation metadata; YOLO text exports do not preserve those attributes.
Have a second reviewer resolve ambiguous labels.

Export YOLO boxes: one `class x_center y_center width height` row per region,
with coordinates normalized to [0,1]. Use matching filenames for images and
labels; reviewed negative images need empty label files. Layout:

```
detection/dataset/images/train/
detection/dataset/images/val/
detection/dataset/images/test/
detection/dataset/labels/train/
detection/dataset/labels/val/
detection/dataset/labels/test/
```

Install `ultralytics` in a separate training environment. Train with
`python detection/train.py`; use validation only for model/threshold selection.
The script evaluates the held-out test split after training. Report per-class
precision/recall, mAP50-95 and small-spur misses. Review failures against source
images. Never use age labels as localization ground truth or report physical
spur length without a scale reference.

Training saves a separate candidate under `detection/runs/`; it does not activate
the model. Only integrate after validation, with explicit no-detection/error
handling and a tested association of chicken, leg and spur boxes. Keep the
existing age preprocessing unless a new crop policy has been validated against
the age model's held-out set.

Training API references: https://docs.ultralytics.com/modes/train/ and
https://docs.ultralytics.com/modes/val/.
