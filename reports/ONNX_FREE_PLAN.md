# Free-plan full estimator

The original PyTorch deployment exceeded the available budget for full vision.
The free-plan runtime now uses ONNX Runtime, not a higher-priced server or a
third-party inference API. Original training images, verified age labels, model
checkpoints and backups are unchanged. No retraining took place.

## Model artifacts

- Age: FP32 ResNet-18 exported from the selected fine-tuned checkpoint.
- Leg/spur detection and spur segmentation: FP32 exports of the existing YOLO
  checkpoints, with the same confidence thresholds and dynamic image shapes.
- Chicken body: OWL-ViT with its four fixed text-query embeddings precomputed.
  The FP32 graph is split after encoder layers 2, 5, 8 and 11 into five stages.
  Each stage releases its weights before the next is loaded. Weights, queries
  and score thresholds are unchanged; no body-weight quantization is used.

The first free-plan version quantized body weights and missed the user's
300 x 300 whole-rooster photograph, despite the desktop score being 0.9174.
The staged replacement restores that detection with the same rounded box
`[64.5, 46.9, 216.3, 246.7]` and score. Age remains 13.1 months, with one leg
region and no detected spur. The previous compressed export is retained locally
and in Git history but is no longer deployed.

`ml_models/free_runtime/manifest.json` pins the size and SHA-256 of every export.
Git preserves the bytes across Windows/Linux. A corrupt/missing asset is not
reported ready. The free runtime imports no PyTorch, torchvision, Transformers
or Ultralytics libraries. Sessions run one at a time and release weights after
each model; concurrent estimation submissions receive a retry message.

## Executed checks

On the screenshot's saved photograph, the converted pipeline generated the same
2 leg regions, 2 spur regions, 1 spur outline, 158.4-pixel centerline and displayed
13.0-month age estimate. An isolated staged body run on the whole-rooster
photograph peaked at about 233 MiB.
An isolated Django browser upload, database save and private image display also
passed with heavy-runtime imports blocked; the web-process tree peaked at about
266 MiB on Windows. These are local measurements, not Render measurements.
A separate 4600 x 3450-pixel input check completed all four models at a peak
of about 355 MiB. The combined estimator, geometry, deployment and ONNX test
suite passed all 39 tests, including the whole-rooster regression case.

A regression comparison ran on all 46 existing example photographs:

| Check | Result |
|---|---|
| Displayed age prediction (1 decimal) | 46/46 matched |
| Leg/spur/outline counts | 46/46 matched |
| Largest compared anatomy-box coordinate difference | 1.5 pixels |
| Exact projected-length lists | 45/46 matched |

The age/anatomy exports are unchanged by the staged-body fix. In one example,
projected length differed by up to 3.34 pixels. These checks measure runtime compatibility
on existing examples, not accuracy on independent chickens or expert validation
of anatomical measurements. The model's original evaluation limitations remain.

## Deployment

The normal Render build remains:
`pip install -r requirements.txt && python smartpoultry/manage.py collectstatic --noinput`.
Linux installs ONNX Runtime and headless OpenCV rather than PyTorch. All exports
are in the repository; no large model download occurs during uploads or startup.
Render automatically selects ONNX. The desktop keeps its original PyTorch
backend by default. `SMARTPOULTRY_INFERENCE_RUNTIME=onnx` can test the free runtime
locally; `pytorch` selects the original backend on a sufficiently sized server.

The health endpoint reports the runtime and export-file presence without loading
models or hashing large files. Full and quick modes both use the exported age
model. Saved results retain their original analysis; reanalysis is required to
generate fresh output with the deployed runtime.

Free-host uploads are limited to 16 megapixels with no side above 8000 pixels.
Physical centimeter measurements still require a real in-plane scale reference.
Live Render inference must be verified after deploying this change. No instance
type or billing setting is changed by this implementation.

## Re-export

Install the desktop inference dependencies plus `onnx==1.19.1` and
`onnxruntime==1.23.2`. Run `python tools/export_free_models.py TASK` for `age`,
`detect`, `segment`, `chicken`, then `manifest`. `chicken-stages` can split an
existing full-precision export without re-exporting the original checkpoint.
Exports are separate from the
original checkpoints. Verify predictions and memory before publishing new ones.

Postprocessing follows the Ultralytics 8.3.221 NMS, contour and native-mask
scaling conventions (AGPL-3.0), implemented with NumPy/OpenCV for the free runtime.
