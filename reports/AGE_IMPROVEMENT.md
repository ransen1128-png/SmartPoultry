# Age-improvement experiments

Executed 12 November 2026 using the existing verified labels and image pixels.
The original checkpoint, images and labels remain unchanged.

## Method and limits

The original fixed source-family split was reused: 130 training, 11 validation
and 10 test photographs. Exact/near-copy families do not cross those boundaries.
Actual chicken identity remains unresolved. The original checkpoint had already
been trained with corpus overlap, so these comparisons do not establish accuracy
on independent chickens. The test partitions were evaluated in prior work;
they are not a newly blinded external test.

The first experiment fitted regularized residual regressions to actual frozen
ResNet image embeddings. Hyperparameters were selected by validation MAE.
Its selected bias correction worsened held-out MAE and was rejected.

The second experiment fine-tuned the original ResNet-18's last residual block
and regression head. Earlier layers and batch-normalization statistics stayed
frozen. Training used the verified labels, inverse-family sampling, horizontal
flips, SmoothL1 loss, gradient clipping and a small prediction-anchoring term.
The random seed was 2026. Validation selected epoch 1; early stopping ended the
run at epoch 9. No filename or ID entered the network as a feature.

| Measurement | Original | Fine-tuned candidate |
| --- | ---: | ---: |
| Validation MAE, 11 images | 1.258 months | 1.249 months |
| Held-out source-family MAE, 10 images | 2.097 months | 2.025 months |
| Held-out within 1 month | 40% | 30% |
| Held-out within 3 months | 80% | 80% |

The mean change is small, and the within-one-month fraction worsened. The
candidate did not meet the predeclared automatic-release improvement threshold.
It is available only as an explicit comparison option; the original model
remains the default. The UI exposes both predictions when comparing models.

## Specific uploaded photo

The exact image uploaded as `4months.jpg` matches the verified 3-month record
`3months (10).jpg`. Original prediction: 8.167 months; selected candidate:
2.479 months, displayed as 2.5. This image belongs to the training partition,
so its improved prediction is not evidence of held-out generalization.

## Artifacts and reproduction

`latest_age_improvement.json` and `latest_age_finetuning.json` point to the
executed experiment directories, checkpoint hashes, validation histories,
per-age metrics and prediction/error CSVs. `spur_age/models/age_candidates.json`
registers the checksum-verified comparison checkpoint without replacing the
original weights. New photos can be analyzed with either explicitly selected
model. Stored estimates retain the chosen model and both predictions.

```powershell
.\.venv\Scripts\python.exe tools\improve_spur_age.py
.\.venv\Scripts\python.exe tools\finetune_spur_age.py
```

Re-running creates new experiment directories; it does not promote a model or
change the active/default checkpoint. Thirty-one targeted estimator and vision
tests pass, including checking that a renamed copy of the known photo receives
the same image-based candidate result and preserves the original checkpoint.
