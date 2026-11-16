# Spur measurement on Render

Deployment marker: `smartpoultry-spur-api-parity-2026-11-16`.

This release keeps the existing free-plan ONNX inference models and adds the same visible-outline/base/tip review editor as localhost. Reviewed measurements and history are stored in the existing analysis JSON in PostgreSQL. No database reset or new model training is part of deployment. Original age/anatomy checkpoints are unchanged.

The weak, review-only PyTorch endpoint candidates remain local. Render uses the manual review editor and optional Gemini geometry drafts. Every API draft requires explicit review and visibility confirmation before a measurement is saved. Pixel arc length is available without a scale; centimeters require a known image scale. Automatic exact geometry is not claimed.

## Optional Gemini configuration

In Render ? this existing web service ? Environment, set:

- `GEMINI_API_KEY`: your existing Gemini API key, entered privately in the Render dashboard.
- `GEMINI_SPUR_FALLBACK_MODEL`: `gemini-3.1-flash-lite` (the model used in the executed local API checks).

Save and deploy. Local `.env` secrets are not committed or copied to GitHub. `render.yaml` includes the model name for Blueprint-managed deployments; an existing manually configured service may still need that environment variable entered in the dashboard. Manual geometry review works without Gemini credentials. API availability/quota depends on the configured Gemini account; this change does not purchase a service or change Render billing.

## Verification

`/__health/` reports the marker above plus `spur_measurement.review_editor`, `curved_pixel_measurement`, `physical_length_requires_known_scale`, and the configuration-only `gemini_configured` flag. The flag does not prove an API call succeeded and exposes no credential.

The Render-environment browser check used the ONNX runtime with Torch, Torchvision, Transformers and Ultralytics imports blocked. It uploaded and analyzed the actual 300 ? 300 test photo, then opened the editor, saved a software geometry fixture in an isolated database, and reopened the result. The age stayed 13.1 months, raw model measurements stayed intact, no centimeter value was invented, and no JavaScript errors occurred. Peak web-process memory was 264.85 MB on Windows during this check; this is evidence of headroom, not a guarantee of Linux production usage.

The live health and authentication-protected routes must also be checked after the GitHub-triggered deployment. No test account or synthetic geometry is written into the live database by these browser checks.

## API parity correction

Web spur localization and geometry review now share `gemini-3.1-flash-lite` as a code default. A legacy `GEMINI_VISION_MODEL` setting for offline comparisons no longer silently changes web spur assistance. `GEMINI_SPUR_FALLBACK_MODEL` remains an explicit override, and the selected web model is exposed in the non-secret health diagnostics. Existing screenshots already matched for body, leg and age; their discrepancy was a failed API request on Render.

Web localization allows two attempts for temporary provider/network failures. Permanent key/model errors are preserved; successful detections are never fabricated from failures. Stored results identify the selected model, attempts and provider error message. Reanalyze an older saved result to make a fresh API request; deploying does not rewrite historical analysis records.

29 focused tests passed. An actual API request with Render-style configuration and no fallback environment variable returned one accepted spur box `[148.5, 202.5, 183.0, 223.5]` on the existing full-chicken photo, exactly matching the successful localhost box. No mask or physical length was invented. This verifies the corrected configuration path locally; live account-specific API success still depends on Render credentials and provider availability.
