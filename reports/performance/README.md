# Estimator performance checks

Measured locally on 12 November 2026. PostgreSQL remains the active database.

Public local HTTP checks returned login in 0.016 seconds and the health endpoint
in 0.000–0.015 seconds. The reported slowdown was specific to opening the
estimator and analyzing photos, rather than general database latency.

The estimator previously imported the age runtime and loaded all four model
checkpoints on GET, even for saved results. It now imports/loads inference
runtimes only on POST. GET explains that availability is checked on submission;
it does not pretend that untested models are ready. Actual rendering checks
returned the form in 0.486 seconds and a saved result in 0.126 seconds, with
torch, transformers and ultralytics absent from the process's imported modules.
These are server-side timings, not complete browser page-load measurements.

CPU inference defaults to four Torch threads, adjustable with
`SMARTPOULTRY_ML_THREADS`. Ultralytics uses the same limit so its backend does
not reset it to eight. No model weights, input preprocessing or score thresholds
were changed. Saved-photo thumbnails now load lazily to avoid fetching all full
image files immediately when opening the page.

An initial real-photo profile measured chicken inference at 6.274 seconds,
followed by a four-thread pass at 2.130 seconds. Warm-up differs between these
passes, so that comparison alone does not isolate the threading effect.
The final profile with the configured runtime is in `estimator_profile.json`.
It measures actual model imports, loads and predictions without writing user
results. The first photo after process restart still incurs model startup;
later photos reuse the loaded models.

Thirty targeted estimator/anatomy tests pass, including a regression check that
opening the estimator does not import heavy ML runtimes. The original age
checkpoint hash remains unchanged.
