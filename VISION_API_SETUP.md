# Optional API comparison — not deployed

This experiment sends image pixels to Gemini to locate spur boxes, then compares
the current age model on a padded spur crop against the same model on the full
image. It does not ask Gemini to guess an age, infer ages from filenames, create
training labels, or turn a bounding box into a physical length.

The current application is unchanged. No API accuracy improvement has been
measured: this machine has no configured API key or model identifier.

## Configure privately

Create a Gemini API key in Google AI Studio and add these entries to the existing
ignored `.env` file. Do not replace the file or share it; it also holds database
credentials. Choose an image-capable model available to that API project.

```dotenv
GEMINI_API_KEY=your_private_key
GEMINI_VISION_MODEL=your_image_capable_model_id
```

Keys stay in request headers, never in the browser, URLs or benchmark reports.
Requests go only to Google's fixed API host. API usage can incur provider charges.
The validation run sends at most 11 distinct photographs; cached successful
responses avoid repeating those requests. Original images remain unmodified.

```powershell
.\.venv\Scripts\python.exe tools\benchmark_vision_api.py --split validation
```

Review `reports/vision_api/validation.json`, especially the predicted regions,
MAE, API failures, crop count and per-image errors. Cropping a model trained on
whole photographs can worsen its predictions. No improvement is assumed.

Only a completed validation run with at least one crop and lower MAE enables:

```powershell
.\.venv\Scripts\python.exe tools\benchmark_vision_api.py --split test
```

The test command checks model/prompt/checkpoint consistency. It does not deploy
anything. Compare test error, per-image bias and failures before adopting the API.
The existing source-family partitions contain no detected family leakage, but
prior age-model training overlap and unresolved animal IDs remain: the result
cannot establish independent-chicken accuracy.

The engineering tests use explicitly mocked API responses; they establish request
and response handling, not real provider accuracy. The actual benchmark requires
working credentials. Existing local predictions remain available throughout.

Official references:
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/image-understanding
- https://ai.google.dev/gemini-api/docs/api-key
