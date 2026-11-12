#!/usr/bin/env python3
"""Optional Gemini spur-localization benchmark for SmartPoultry.

This tool never changes the Django application, training data, labels, or model.
It reconstructs the exact GroupShuffleSplit used by train_model.py, then
subdivides the original held-out test partition into disjoint validation/test
subsets. The checkpoint's stored split counts/seed must match before running.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from PIL import Image, ImageOps
from sklearn.model_selection import GroupShuffleSplit
from torch import nn
from torchvision import models, transforms

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "spur_age" / "dataset" / "images"
CSV_PATH = ROOT / "spur_age" / "dataset" / "metadata.csv"
MODEL_PATH = ROOT / "spur_age" / "models" / "spur_age_model.pth"
REPORT_DIR = ROOT / "reports" / "vision_api"
CACHE_PATH = REPORT_DIR / "detection_cache.json"
VALIDATION_REPORT = REPORT_DIR / "validation.json"
TEST_REPORT = REPORT_DIR / "test.json"
API_HOST = "https://generativelanguage.googleapis.com"
PROMPT_VERSION = "spur-box-v1"
SEED = 42
ORIGINAL_TEST_SIZE = 0.20
MAX_API_IMAGES = 11
DEVICE = torch.device("cpu")

PROMPT = """Inspect this photograph only to locate a visible chicken leg spur.
Do not estimate or mention the chicken's age. Do not infer age from image text,
filename, metadata, or appearance. Return JSON only, matching the schema.
If a spur is clearly visible, return one or more boxes in normalized 0..1000
coordinates as [y_min, x_min, y_max, x_max]. Coordinates must tightly enclose
the spur itself, not the whole leg or foot. If no spur is clearly visible,
return an empty detections array. Never invent a box."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "detections": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["box_2d"],
            },
        }
    },
    "required": ["detections"],
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_env_file(path: Path) -> None:
    """Read only the two needed keys without replacing or printing .env."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key in {"GEMINI_API_KEY", "GEMINI_VISION_MODEL"} and value:
            os.environ.setdefault(key, value)


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def prepare_api_image(image_path: Path) -> tuple[bytes, str, tuple[int, int]]:
    """Compress a copy for API transfer; original file remains untouched."""
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        original_size = image.size
        image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
        from io import BytesIO
        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue(), "image/jpeg", original_size


def parse_detection_response(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    payload = json.loads(cleaned)
    detections = payload.get("detections", []) if isinstance(payload, dict) else []
    if not isinstance(detections, list):
        raise ValueError("Gemini response 'detections' must be a list")
    valid = []
    for item in detections:
        if not isinstance(item, dict):
            continue
        box = item.get("box_2d")
        if not isinstance(box, list) or len(box) != 4:
            continue
        try:
            y1, x1, y2, x2 = [int(v) for v in box]
        except (TypeError, ValueError):
            continue
        if not (0 <= y1 < y2 <= 1000 and 0 <= x1 < x2 <= 1000):
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        valid.append({"box_2d": [y1, x1, y2, x2], "confidence": confidence})
    return valid


def call_gemini(image_bytes: bytes, mime_type: str, api_key: str, model_id: str) -> list[dict[str, Any]]:
    if len(image_bytes) > 19 * 1024 * 1024:
        raise ValueError("Compressed image exceeds the safe inline request size")
    url = f"{API_HOST}/v1beta/models/{model_id}:generateContent"
    body = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": mime_type,
                              "data": base64.b64encode(image_bytes).decode("ascii")}},
        ]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(1200).decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini network error: {exc.reason}") from exc

    parts = response_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    response_text = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not response_text:
        raise ValueError("Gemini returned no text content")
    return parse_detection_response(response_text)


def choose_box(detections: list[dict[str, Any]]) -> list[int] | None:
    if not detections:
        return None
    best = max(detections, key=lambda item: item.get("confidence", 0.0))
    return best["box_2d"]


def padded_crop(image: Image.Image, box: list[int], padding_fraction: float = 0.25) -> Image.Image:
    """Crop normalized y1,x1,y2,x2 box with proportional padding."""
    width, height = image.size
    y1, x1, y2, x2 = box
    left, top = x1 / 1000 * width, y1 / 1000 * height
    right, bottom = x2 / 1000 * width, y2 / 1000 * height
    pad_x = (right - left) * padding_fraction
    pad_y = (bottom - top) * padding_fraction
    bounds = (
        max(0, int(math.floor(left - pad_x))),
        max(0, int(math.floor(top - pad_y))),
        min(width, int(math.ceil(right + pad_x))),
        min(height, int(math.ceil(bottom + pad_y))),
    )
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise ValueError("Bounding box produced an empty crop")
    return image.crop(bounds)


def load_age_model(checkpoint_path: Path) -> tuple[torch.nn.Module, transforms.Compose, dict[str, Any], str]:
    checkpoint = torch.load(checkpoint_path, map_location=DEVICE, weights_only=True)
    if checkpoint.get("architecture") != "resnet18":
        raise ValueError("Checkpoint architecture is not resnet18")
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 1)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(DEVICE).eval()
    image_transform = transforms.Compose([
        transforms.Resize((int(checkpoint["image_size"]), int(checkpoint["image_size"]))),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=checkpoint["normalization_mean"],
            std=checkpoint["normalization_std"],
        ),
    ])
    return model, image_transform, checkpoint, sha256_file(checkpoint_path)


def predict_image(model: torch.nn.Module, image_transform: transforms.Compose,
                  image: Image.Image, age_min: float, age_max: float) -> float:
    tensor = image.convert("RGB")
    tensor = image_transform(tensor).unsqueeze(0).to(DEVICE)
    with torch.inference_mode():
        value = float(model(tensor).item())
    if not math.isfinite(value):
        raise ValueError("Age model produced a non-finite prediction")
    return max(age_min, min(age_max, value))


def load_and_validate_dataset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    if not CSV_PATH.is_file() or not IMAGE_DIR.is_dir():
        raise FileNotFoundError(f"Expected dataset paths: {CSV_PATH} and {IMAGE_DIR}")
    df = pd.read_csv(CSV_PATH)
    required = {"image", "age_months", "chicken_id", "age_verified"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"metadata.csv missing columns: {sorted(missing)}")
    df = df.copy()
    for col in ("image", "chicken_id", "age_verified"):
        df[col] = df[col].astype("string").str.strip()
    df["age_months"] = pd.to_numeric(df["age_months"], errors="coerce")
    if df[list(required)].isna().any().any():
        raise ValueError("Metadata contains missing required values")
    if df["image"].duplicated().any() or df["chicken_id"].duplicated().any():
        raise ValueError("This benchmark requires one unique image and chicken_id per row")
    if (df["age_verified"].str.lower() != "yes").any():
        raise ValueError("All benchmark labels must have age_verified=yes")
    if not df["age_months"].between(1, 24).all() or (df["age_months"] % 1 != 0).any():
        raise ValueError("All ages must be verified whole months from 1 through 24")
    # Match train_model.py exactly: one GroupShuffleSplit, 20% test, seed 42.
    train_idx, heldout_idx = next(GroupShuffleSplit(
        n_splits=1, test_size=ORIGINAL_TEST_SIZE, random_state=SEED
    ).split(df, groups=df["chicken_id"]))
    train_df = df.iloc[train_idx].copy()
    heldout_df = df.iloc[heldout_idx].copy()
    # Stable ordering lets validation/test be disjoint and reproducible.
    heldout_df = heldout_df.sort_values("image", kind="stable").reset_index(drop=True)
    if len(heldout_df) <= MAX_API_IMAGES:
        raise ValueError("Held-out split is too small to create disjoint validation and test samples")
    # First 11 held-out rows are validation; the next rows are reserved for test.
    validation_df = heldout_df.iloc[:MAX_API_IMAGES].copy()
    test_df = heldout_df.iloc[MAX_API_IMAGES:].copy()
    return train_df, validation_df, test_df, sha256_file(CSV_PATH)


def check_checkpoint_matches_split(checkpoint: dict[str, Any], train_df: pd.DataFrame,
                                  validation_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    expected_train = int(checkpoint.get("training_images", -1))
    expected_heldout = int(checkpoint.get("testing_images", -1))
    expected_seed = int(checkpoint.get("seed", -1))
    reconstructed_heldout = len(validation_df) + len(test_df)
    if expected_train != len(train_df) or expected_heldout != reconstructed_heldout or expected_seed != SEED:
        raise RuntimeError(
            "Checkpoint does not match the supplied train_model.py split. "
            f"Expected checkpoint counts train={len(train_df)}, heldout={reconstructed_heldout}, seed={SEED}; "
            f"found train={expected_train}, heldout={expected_heldout}, seed={expected_seed}. "
            "Refusing to benchmark potentially overlapping data."
        )


def get_detection(image_path: Path, model_id: str, api_key: str,
                  cache: dict[str, Any]) -> tuple[list[int] | None, str]:
    image_hash = sha256_file(image_path)
    cache_key = sha256_bytes(f"{image_hash}|{model_id}|{PROMPT_VERSION}".encode())
    cached = cache.get(cache_key)
    if isinstance(cached, dict) and cached.get("status") == "success":
        return cached.get("box_2d"), "cache"
    image_bytes, mime_type, _ = prepare_api_image(image_path)
    detections = call_gemini(image_bytes, mime_type, api_key, model_id)
    box = choose_box(detections)
    cache[cache_key] = {
        "status": "success", "image_sha256": image_hash,
        "model": model_id, "prompt_version": PROMPT_VERSION,
        "box_2d": box, "detections": detections,
    }
    return box, "api"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    paired = [r for r in rows if r.get("full_prediction") is not None and r.get("crop_prediction") is not None]
    full_only = [r for r in rows if r.get("full_prediction") is not None]
    if not full_only:
        full_mae = None
    else:
        full_mae = sum(abs(r["full_prediction"] - r["actual_age_months"]) for r in full_only) / len(full_only)
    crop_mae = (sum(abs(r["crop_prediction"] - r["actual_age_months"]) for r in paired) / len(paired)) if paired else None
    paired_full_mae = (sum(abs(r["full_prediction"] - r["actual_age_months"]) for r in paired) / len(paired)) if paired else None
    return {
        "images_attempted": len(rows),
        "crop_count": len(paired),
        "api_failures": sum(bool(r.get("api_error")) for r in rows),
        "full_prediction_count": len(full_only),
        "paired_prediction_count": len(paired),
        "full_image_mae_months": round(full_mae, 4) if full_mae is not None else None,
        "paired_full_image_mae_months": round(paired_full_mae, 4) if paired_full_mae is not None else None,
        "spur_crop_mae_months": round(crop_mae, 4) if crop_mae is not None else None,
    }


def run_benchmark(split: str, limit: int) -> int:
    load_env_file(ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model_id = os.environ.get("GEMINI_VISION_MODEL", "").strip()
    if not api_key or not model_id:
        raise RuntimeError("Set GEMINI_API_KEY and GEMINI_VISION_MODEL in the existing ignored .env file")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model_id):
        raise ValueError("GEMINI_VISION_MODEL must be a model identifier, not a URL")
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Age-model checkpoint not found: {MODEL_PATH}")

    train_df, validation_df, test_df, metadata_hash = load_and_validate_dataset()
    model, image_transform, checkpoint, checkpoint_hash = load_age_model(MODEL_PATH)
    check_checkpoint_matches_split(checkpoint, train_df, validation_df, test_df)

    if split == "validation":
        selected = validation_df.iloc[:limit].copy()
        report_path = VALIDATION_REPORT
    else:
        if not VALIDATION_REPORT.is_file():
            raise RuntimeError("Run validation first; validation.json is missing")
        validation_report = json.loads(VALIDATION_REPORT.read_text(encoding="utf-8"))
        gate = validation_report.get("gate", {})
        if (validation_report.get("checkpoint_sha256") != checkpoint_hash
                or validation_report.get("metadata_sha256") != metadata_hash
                or validation_report.get("gemini_model") != model_id
                or validation_report.get("prompt_version") != PROMPT_VERSION):
            raise RuntimeError("Validation report does not match the current checkpoint, metadata, model, or prompt")
        if not gate.get("passed"):
            raise RuntimeError("Validation gate failed: at least one paired crop and lower crop MAE are required")
        selected = test_df.iloc[:limit].copy()
        report_path = TEST_REPORT

    cache = load_cache()
    results: list[dict[str, Any]] = []
    age_min = float(checkpoint["age_min"])
    age_max = float(checkpoint["age_max"])
    for _, row in selected.iterrows():
        filename = str(row["image"])
        image_path = IMAGE_DIR / filename
        record: dict[str, Any] = {
            "image": filename,
            "chicken_id": str(row["chicken_id"]),
            "actual_age_months": float(row["age_months"]),
            "full_prediction": None,
            "crop_prediction": None,
            "predicted_box_2d": None,
            "detection_source": None,
            "api_error": None,
            "prediction_error": None,
        }
        try:
            with Image.open(image_path) as source:
                original = ImageOps.exif_transpose(source).convert("RGB")
                record["full_prediction"] = round(predict_image(
                    model, image_transform, original, age_min, age_max
                ), 4)
            try:
                box, source_name = get_detection(image_path, model_id, api_key, cache)
                record["predicted_box_2d"] = box
                record["detection_source"] = source_name
                if box is not None:
                    with Image.open(image_path) as source:
                        original = ImageOps.exif_transpose(source).convert("RGB")
                        crop = padded_crop(original, box)
                    record["crop_prediction"] = round(predict_image(
                        model, image_transform, crop, age_min, age_max
                    ), 4)
            except Exception as exc:  # preserve full-image baseline if API/crop fails
                record["api_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        except Exception as exc:
            record["prediction_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        results.append(record)
        print(f"[{len(results)}/{len(selected)}] {filename}: full={record['full_prediction']} crop={record['crop_prediction']} source={record['detection_source']}")

    metrics = summarize(results)
    gate_passed = bool(
        split == "validation"
        and metrics["crop_count"] >= 1
        and metrics["spur_crop_mae_months"] is not None
        and metrics["paired_full_image_mae_months"] is not None
        and metrics["spur_crop_mae_months"] < metrics["paired_full_image_mae_months"]
    )
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "limit": limit,
        "gemini_model": model_id,
        "prompt_version": PROMPT_VERSION,
        "checkpoint_sha256": checkpoint_hash,
        "metadata_sha256": metadata_hash,
        "split_definition": "Reconstructed GroupShuffleSplit(test_size=0.20, random_state=42); first 11 sorted held-out images reserved for validation, subsequent held-out images reserved for test. The checkpoint counts/seed are checked.",
        "metrics": metrics,
        "gate": {
            "passed": gate_passed,
            "rule": "Validation only: at least one paired spur crop and lower crop MAE than full-image MAE on the same paired images.",
        },
        "limitations": [
            "Gemini localizes a visible spur only; it does not estimate age or create labels.",
            "A box is not a calibrated physical-length measurement.",
            "This compares the same whole-image-trained age model on whole images and spur crops; crop performance may be worse.",
            "The held-out partition is reconstructed from the supplied training script and metadata. Checkpoint count/seed consistency is checked, but historical animal identity correctness cannot be independently audited by this tool.",
            "At most 11 distinct photographs are processed per command; successful detections are cached by image, model, and prompt version.",
        ],
        "results": results,
    }
    save_json(CACHE_PATH, cache)
    save_json(report_path, report)
    print("\nMetrics:")
    print(json.dumps(metrics, indent=2))
    print("Report:", report_path)
    if split == "validation":
        print("Validation gate:", "PASSED" if gate_passed else "FAILED")
        return 0 if gate_passed else 2
    print("Test benchmark complete. This does not deploy the API or change the application.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("validation", "test"), required=True)
    parser.add_argument("--limit", type=int, default=MAX_API_IMAGES,
                        help="Maximum distinct images to process (hard maximum: 11)")
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_API_IMAGES:
        parser.error("--limit must be between 1 and 11")
    try:
        return run_benchmark(args.split, args.limit)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
