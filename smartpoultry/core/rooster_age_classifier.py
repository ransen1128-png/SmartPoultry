
"""ResNet-18 chicken spur age prediction."""

from functools import lru_cache
import hashlib
import math
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms


MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "spur_age"
    / "models"
    / "spur_age_model.pth"
)

DEVICE = torch.device("cpu")


@lru_cache(maxsize=2)
def _load_ready_model(model_variant='original'):
    path, candidate = MODEL_PATH, None
    if model_variant == 'finetuned':
        from core.age_model_registry import candidate_entry
        candidate = candidate_entry()
        if candidate is None:
            return None
        path = candidate['resolved_path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != candidate['sha256']:
            return None
    elif model_variant != 'original':
        return None
    if not path.is_file():
        return None

    try:
        from core.ml_runtime import configure_cpu_runtime
        configure_cpu_runtime()
        checkpoint = torch.load(
            path,
            map_location=DEVICE,
            weights_only=True,
        )

        if checkpoint.get("architecture") != "resnet18":
            return None

        image_size = int(checkpoint["image_size"])
        age_min = float(checkpoint["age_min"])
        age_max = float(checkpoint["age_max"])

        model = models.resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, 1)

        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(DEVICE)
        model.eval()

        image_transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=checkpoint["normalization_mean"],
                std=checkpoint["normalization_std"],
            ),
        ])

        return {
            "model": model,
            "transform": image_transform,
            "age_min": age_min,
            "age_max": age_max,
            "test_mae": float(
                checkpoint.get("test_mae_months", 0)
            ),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "model_variant": model_variant,
            "comparison_metrics": candidate.get('metrics') if candidate else None,
            "evaluation_status": checkpoint.get(
                "evaluation_status",
                "Independent validation pending; reconstructed historical split contains duplicate leakage.",
            ),
        }

    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return None


def model_is_ready(model_variant='original'):
    return _load_ready_model(model_variant) is not None


def model_test_mae():
    artifact = _load_ready_model()
    return artifact['test_mae'] if artifact else None


def predict_rooster_age(image_source, model_variant='original'):
    artifact = _load_ready_model(model_variant)

    if artifact is None:
        return None

    try:
        with Image.open(image_source) as image:
            image = image.convert("RGB")
            image_tensor = artifact["transform"](image).unsqueeze(0)

        with torch.no_grad():
            prediction = artifact["model"](
                image_tensor.to(DEVICE)
            ).item()

        if not math.isfinite(prediction):
            return None

        prediction = max(
            artifact["age_min"],
            min(artifact["age_max"], prediction),
        )

        return {
            "age_months": round(prediction, 1),
            "age_range": f"{round(prediction, 1)} months",
            "test_mae_months": artifact["test_mae"],
            "model_sha256": artifact["sha256"],
            "evaluation_status": artifact["evaluation_status"],
            "model_variant": artifact['model_variant'],
            "comparison_metrics": artifact['comparison_metrics'],
        }

    except (OSError, ValueError, RuntimeError):
        return None
