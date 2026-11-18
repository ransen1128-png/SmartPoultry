# Localhost API-assisted spur localization

16 November 2026. Original age and anatomy checkpoints remain unchanged.

The local detector still misses the spur in the reported whole-rooster image.
An actual Gemini request returned a useful location for that photograph. The
estimator now offers **combined analysis**, selected on the form when credentials
are configured following the user's request to combine the models. Local models
run first. Gemini checks leg regions without local spur evidence, including when
another leg already has a local result. Uncheck the option for local-only analysis.
Quick age mode never uses it. The form explains that the option sends the photo
to Gemini when assistance is needed.

## Executed evidence

- Gemini 3.8 Flash returned `[161.1, 204.6, 183.9, 224.4]` in one successful
  request, but subsequent requests repeatedly timed out. Older 2.5 Flash returned
  a real HTTP 404 for this account; no successful result is claimed for it.
- Gemini 3.1 Flash-Lite returned `[148.5, 202.5, 183.0, 223.5]` in about 1.9 seconds.
  It is configured separately as `GEMINI_SPUR_FALLBACK_MODEL` in the ignored local
  `.env`; the existing `GEMINI_VISION_MODEL` and age model selection are preserved.
- Real browser uploads, database saving and private image previews passed using
  both the ONNX backend and the desktop PyTorch backend, with an actual API call.
  Each reported one leg, one API spur box and the unchanged 13.1-month estimate.
  Neither produced a usable spur outline or a length measurement.
- All 54 targeted tests passed, covering API contracts, invalid/off-leg regions,
  failure handling, explicit opt-in, quick-mode exclusion, saved provenance,
  unchanged age output, partial-leg coverage, duplicate suppression, real-polygon
  recovery/calibration and the existing estimator/geometry behavior. Polygon
  recovery tests use synthetic unit fixtures; the reported photograph still has
  no accepted local outline and therefore no measured length.
- API outline requests and local segmentation on crops around the API box failed
  to provide an accepted outline. Boxes are never converted to pretend masks or
  spur lengths. No physical length is inferred from a bounding-box dimension.

## Initial fallback evaluation and current combined policy

Existing annotations are assistant-drawn and require expert review. At box IoU
0.5, the existing eight-image validation split produced identical local/assisted
totals: 8 true-positive, 4 false-positive and 5 missed spur instances. Assistance
was not triggered on those validation cases, so this is not evidence of API
accuracy improvement.

A subsequent fixed-policy evaluation on the existing eight-image source-family
test split produced:

| Result | Local | API-assisted |
|---|---:|---:|
| True-positive spur boxes | 3 | 3 |
| False-positive spur boxes | 2 | 3 |
| Missed spur instances | 7 | 7 |

One API request in that evaluation failed. The added proposal did not satisfy
the IoU criterion. These results do not justify automatic API promotion or a
general accuracy-improvement claim. The initial fallback option was off by
default. The user subsequently requested combined analysis, which now remains
selected on the form with a local-only opt-out. Its additional per-leg completion
and outline-association behavior has passed regression tests but has not received
a new independent accuracy evaluation. The reported whole-rooster case demonstrates
functionality, not general accuracy.
Both evaluation reports are retained alongside this document as JSON. These are
not independent-chicken age evaluations; no age-accuracy percentage is claimed.

## Runtime behavior

- The request checkbox is required. Opening the page makes no API call. The
  combined option is visible and selected when configured; it can be unchecked.
- Existing local spur detections/masks are retained. The API checks missing leg
  regions, rather than replacing successful local results. No call occurs when
  every detected leg has local spur evidence.
- Overlapping/nested API boxes are merged with local results or suppressed.
  Agreement is recorded without averaging or boosting confidence scores.
- A local segmentation polygon previously lacking a spur box can be associated
  with an accepted API region (IoU >= 0.15). Its original coordinates and score
  are retained, its source is labeled `local_segmenter_api_localization`, and
  pixel length is computed from that actual polygon. Centimeters still require
  the user's valid in-plane scale. Unmatched outlines remain unconfirmed.
- API calls have one attempt and a 20-second timeout. Errors preserve local outputs
  and age prediction, and are displayed separately from a completed negative result.
- Invalid coordinates and regions whose centers are remote from all detected legs
  are excluded. The spatial gate is a heuristic, not anatomical verification.
- Accepted boxes retain `source=gemini_api`, the API model identifier and a null
  confidence score. The overlay labels them as API predictions without inventing
  a score. API provenance and diagnostics are saved with the analysis.
- Saving/reopening results does not repeat the API request. Reanalysis creates a
  fresh record. Successful request reuse in one process uses the existing cache.
- API assistance never changes the age model, its pixel input, training labels
  or physical calibration. It does not invent a polygon from an API box.

The request policy uses low thinking on Gemini 3 models, as documented in the
[Gemini thinking guide](https://ai.google.dev/gemini-api/docs/generate-content/thinking).
The prompt/transport policy hashes are included in results and the separate
offline benchmark's cache/report keys for reproducibility. No age-crop benchmark
was run as part of this change.

This change is local; Render has not been redeployed or reconfigured for API use.
