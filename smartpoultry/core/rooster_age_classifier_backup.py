"""Image features and validated rooster spur age predictions."""

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from PIL import Image, ImageOps
from skimage.feature import hog


AGE_LABELS = ('1-3 months', '4-6 months', '7-12 months', '13-24 months')
MODEL_PATH = Path(__file__).resolve().parents[2] / 'ml_models' / 'rooster_spur_age.joblib'
MIN_BALANCED_ACCURACY = 0.75
MIN_MACRO_F1 = 0.70


def image_features(image_source):
    with Image.open(image_source) as image:
        image = ImageOps.fit(image.convert('RGB'), (128, 128))
        pixels = np.asarray(image)
    return hog(
        pixels,
        orientations=9,
        pixels_per_cell=(8, 8),
        cells_per_block=(2, 2),
        channel_axis=-1,
    )


@lru_cache(maxsize=1)
def _load_ready_model():
    if not MODEL_PATH.is_file():
        return None
    try:
        artifact = joblib.load(MODEL_PATH)
    except (OSError, ValueError, EOFError):
        return None
    metrics = artifact.get('metrics', {})
    if not artifact.get('validated'):
        return None
    if metrics.get('balanced_accuracy', 0) < MIN_BALANCED_ACCURACY:
        return None
    if metrics.get('macro_f1', 0) < MIN_MACRO_F1:
        return None
    return artifact


def model_is_ready():
    return _load_ready_model() is not None


def predict_rooster_age(image_source):
    artifact = _load_ready_model()
    if artifact is None:
        return None

    features = image_features(image_source)
    predicted_label = artifact['classifier'].predict([features])[0]
    balanced_accuracy = artifact['metrics']['balanced_accuracy']
    if balanced_accuracy >= 0.90:
        confidence = 'High'
    elif balanced_accuracy >= 0.80:
        confidence = 'Moderate'
    else:
        confidence = 'Low'

    return {
        'age_range': predicted_label,
        'confidence': confidence,
        'balanced_accuracy': balanced_accuracy,
        'macro_f1': artifact['metrics']['macro_f1'],
    }