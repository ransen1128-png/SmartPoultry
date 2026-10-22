# ML Models Placeholder

This directory contains machine learning models for SMARTPOULTRY predictions.

## Models

- **profit_prediction.pkl** - RandomForest model for profit forecasting
- **revenue_forecast.pkl** - RandomForest model for revenue prediction
- **rooster_spur_age.joblib** - Age-range image classifier, created only after held-out validation passes

## Rooster Spur Age Model

Place close-up, age-verified spur images under `spurs images/` using one folder per age range and one subfolder per chicken:

```text
spurs images/
	1-3months/
		bird-0001/image-01.jpg
	4-6months/
		bird-0101/image-01.jpg
	7-12months/
		bird-0201/image-01.jpg
	13-24months/
		bird-0301/image-01.jpg
```

The trainer requires at least 200 images from 50 distinct chickens in each class. It holds out entire chickens for validation and saves `rooster_spur_age.joblib` only when balanced accuracy is at least 0.75 and macro F1 is at least 0.70. A failed validation does not produce an active model.

```bash
python ml_models/train_rooster_age.py
```

The current four flat example files do not meet these requirements. The baseline classifies spur close-ups into age ranges; it does not independently detect chickens, spur visibility, or measure spur length.

## Training

To train the models:

```bash
cd ml_models
python train_model.py
```

## Usage

```python
from predictor import get_predictor

predictor = get_predictor()
profit_prediction = predictor.predict_profit([...features...])
```

## Files

- `train_model.py` - Model training script
- `predictor.py` - Prediction utilities
