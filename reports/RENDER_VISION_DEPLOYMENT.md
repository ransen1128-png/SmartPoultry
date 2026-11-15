# Full estimator deployment

The active free-plan implementation is now the lighter ONNX backend described
in [ONNX_FREE_PLAN.md](ONNX_FREE_PLAN.md). The PyTorch capacity notes below refer
to the original full-precision deployment and remain as historical context.

The deployed age model, body detector, leg/spur detector and spur segmenter are
separate artifacts. Publishing Django code alone did not publish the detectors.

## Historical PyTorch free-plan configuration

The user selected the free plan. The live service reports a 512 MiB cgroup limit.
The default `render.yaml` build therefore remains:
`pip install -r requirements.txt && python smartpoultry/manage.py collectstatic --noinput`.
Age estimation stays enabled. Full detection stays unavailable under the capacity
guard; billing and instance type are not changed. A desktop test of age plus the
smaller anatomy models, without OWL-ViT, still peaked around 439 MiB and does not
establish safe headroom on the 512 MiB hosted instance.

The full model bundle remains available for a separately resourced deployment;
its configuration below is optional and is not the selected free-plan default.

## Render settings

- Build command: `bash tools/render-build.sh`
- Start command: `cd smartpoultry && python manage.py migrate && gunicorn --config gunicorn.conf.py core.wsgi:application --bind 0.0.0.0:$PORT`
- Recommended web-service memory: at least **2 GB** for full analysis.

For a service created manually, set the build command in Render Settings; a Git
push alone does not necessarily apply `render.yaml`. This change does not modify
the PostgreSQL connection, accounts, original age checkpoints or source images.

The exact saved photo used for the user's desktop screenshot produced two leg
boxes, two spur boxes and one matched spur outline locally. Full-process peak
memory measured about 1,020 MB on Windows; this is not a measurement of Render.
The server avoids loading the full detector stack when an exposed cgroup limit
is below 1,536 MiB, and reports the capacity limitation rather than crashing.
The desktop's uncapped environment and a 2 GB instance pass this check.

## Assets and reproducibility

`ml_models/deployment.json` pins the size and SHA-256 of all eleven model/config
files. The two anatomy checkpoints and seven body processor/config files are
included in Git. The large body checkpoint is prepared during the build from
the public, revision-pinned `google/owlvit-base-patch32` safetensors checkpoint.
No model download happens during an estimation request.

Removing the two nonpersistent position-id buffers from that pinned source and
saving with safetensors 0.8.0 recreates the desktop checkpoint **byte for byte**:
`40b0fbb7b18a468417dd1786d035d993a8414706bb4b16098cfc1edbdba6031e`.
Preparation verifies the source and final hashes, fails on corrupted assets,
and refuses to overwrite a different existing model.

The hosted requirements pin the desktop's Transformers 4.57.6 and Ultralytics
8.3.221 inference libraries. The build installs the latter without dependencies
after explicitly installing its runtime dependencies, using OpenCV's headless
4.11.0.86 server wheel instead of the desktop GUI wheel. No inference code,
model thresholds, learned parameters or age labels are changed by that swap.

The public `/__health/` endpoint exposes lightweight `vision_deployment` checks
for file/package presence and cgroup memory capacity. These checks do not claim
that inference has run successfully. After the build is Live, use **Analyze
again with current models** in **full photo analysis** mode; existing saved
analyses retain their original results. Pixel measurements do not establish
centimeter lengths without an actual in-plane scale reference.

Source: https://huggingface.co/google/owlvit-base-patch32/tree/cbc355fb364588351c5d51c7f74465e8e7ec6f72
