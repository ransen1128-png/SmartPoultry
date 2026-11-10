# Annotation work on the inspected existing corpus

No additional photograph collection is assumed. Start with the 151 distinct
existing photographs in `reports/dataset_audit/review_queue.csv`, not all 15,205
duplicate aliases. Existing age labels are user-confirmed and stay unchanged.
The 62 conservative visual families are split groups, not a verified count of
independent chickens. Never infer individual identity from the filename.

1. Complete content type (whole chicken, leg close-up, spur close-up, detached
   part, other), visibility (clear, partial, hidden, absent, unknown), source
   family and persistent bird mapping. Distinguish absence from occlusion.
   Preserve the supplied ages. Record uncertainty rather than inventing a box.
2. Annotate full visible chickens where present if a chicken detector is needed.
   A close-up with no full bird is truncated/unknown, not a reliable negative.
3. For the prepared leg/spur model, annotate anatomical shanks as class 0 and
   individual spurs as class 1. Box only visible regions under one documented
   occlusion policy. Include small buds and reviewed negatives. Keep a separate
   instance/leg association file; a spur on another chicken must not be used
   to explain the uploaded chicken's age.
4. Use polygons only if segmentation is actually needed. Age regression on
   reviewed close-ups does not require a segmentation mask. Curved physical
   length requires base/tip or centerline labels plus an in-plane known scale;
   a pixel length alone is not a centimeter measurement.
5. Have a second reviewer inspect ambiguity, tiny regions, visibility and bird
   mapping. Maintain the original labels/photographs; export derived annotation
   files to `detection/dataset`, retaining provenance and original hashes.
6. Export the train/validation/test source-family assignments from the audited
   manifests. Do not randomly split individual files or duplicate variants.
   Keep reviewed identities in one split even across dates and ages.
7. Pilot the annotation on representatives, train the separate detector with
   `python detection/train.py`, inspect precision/recall and small-spur errors
   on held-out families, then expand annotation based on failures. Do not tune
   on the final test set. There is no defensible fixed minimum count before
   measuring these failures; never multiply annotation counts with duplicates.

The supplied detector trainer uses the two-class YOLO format in `data.yaml`.
It deliberately refuses to train without real label files. Empty files are
allowed only for reviewed negatives. A future chicken-only detector needs its
own class configuration. Preserve boxes/masks and dimensions in structured
exports (for example COCO) as the authoritative annotations; raster circles,
watermarks and age strings do not substitute for these annotations.

Do not activate detector outputs in Django until the actual checkpoint has
been run on representative uploads and its failure/no-detection states tested.
Until then, the app reports localization, segmentation and measurements as
unavailable. The existing age model estimates from readable uploads by default,
with an experimental label and quality warnings. No positive detection is inferred
from generating an age estimate.
