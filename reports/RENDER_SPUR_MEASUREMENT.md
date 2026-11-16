# Spur measurement on Render

Deployment marker: `smartpoultry-spur-api-failover-2026-11-16`.

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

## Confirmed provider overload and failover

The user supplied the actual Render error: `Gemini HTTP 503 (UNAVAILABLE): This model is currently experiencing high demand`, after two attempts on `gemini-3.1-flash-lite`. This establishes an upstream availability failure; the earlier deployment/model setting checks did not establish a successful account-specific API request.

Localization now tries `gemini-3-flash-preview` once after the primary's bounded attempts fail with temporary HTTP 500/502/503/504 or a network timeout. Maximum web localization requests: two primary attempts and one backup attempt, each with a 20-second timeout and bounded retry delay. No backup is tried for successful empty detections, malformed responses, credential errors or quota errors. Set `GEMINI_SPUR_BACKUP_MODEL` to override the backup, or an empty string to disable it. Both desktop and Render use this policy. Geometry drafts remain separately reviewed and are not inferred from boxes.

Actual model probes on the user's existing 300 ? 300 photo:

- `gemini-3-flash-preview`: completed in 5.64 seconds, returning one box `[163.2, 205.2, 183.3, 224.4]`.
- `gemini-3.1-flash-lite-preview`: initially returned actual HTTP 503; a later bounded request succeeded on its second attempt with `[148.5, 202.5, 183.0, 223.5]`. That later execution recovered on the primary and did not exercise backup routing.
- `gemini-3.5-flash-lite`: completed with no boxes; rejected as the default backup for this case.
- `gemini-3.8-flash`: timed out after 20 seconds; rejected as the default backup.

33 focused tests passed, including deterministic backup routing after overload, preserving errors when both models fail, and not choosing another model merely to get a positive detection. Backup model outputs may differ; external availability and identical coordinates cannot be guaranteed. API result history records each attempted model and the actual result source. The failure message is now visible directly on the result instead of only under collapsed model details. A unit test confirms that visibility.
