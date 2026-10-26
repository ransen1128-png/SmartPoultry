
from pathlib import Path
import random

import numpy as np
import pandas as pd
import torch
from PIL import Image, UnidentifiedImageError
from sklearn.model_selection import GroupShuffleSplit
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from torchvision.models import ResNet18_Weights


# ============================================================
# 1. CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent

IMAGE_DIR = ROOT / "spur_age" / "dataset" / "images"
CSV_PATH = ROOT / "spur_age" / "dataset" / "metadata.csv"
MODEL_DIR = ROOT / "spur_age" / "models"
MODEL_PATH = MODEL_DIR / "spur_age_model.pth"

BATCH_SIZE = 16
EPOCHS = 10
TEST_SIZE = 0.20
SEED = 42
MIN_AGE = 1
MAX_AGE = 24
IMAGE_SIZE = 224

# Keep the first experiment simple: train the regression head
# while the pretrained ResNet feature extractor stays frozen.

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)


# ============================================================
# 2. LOAD AND VALIDATE METADATA
# ============================================================

print("=" * 60)
print("SMARTPOULTRY CHICKEN SPUR AGE ESTIMATION")
print("=" * 60)

if not CSV_PATH.is_file():
    raise FileNotFoundError(
        f"Metadata CSV was not found: {CSV_PATH}"
    )

if not IMAGE_DIR.is_dir():
    raise FileNotFoundError(
        f"Image folder was not found: {IMAGE_DIR}"
    )

df = pd.read_csv(CSV_PATH)

required_columns = {
    "image",
    "age_months",
    "chicken_id",
    "age_verified",
}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    raise ValueError(
        f"metadata.csv is missing these columns: "
        f"{sorted(missing_columns)}"
    )

print("Metadata rows:", len(df))

if df.empty:
    raise ValueError("metadata.csv contains no records.")

# Required fields must be present.
for column in ["image", "chicken_id", "age_verified"]:
    df[column] = df[column].astype("string").str.strip()

if df[["image", "chicken_id", "age_verified"]].isna().any().any():
    raise ValueError(
        "Some records have missing image names, chicken IDs, "
        "or verification values. Fix metadata.csv first."
    )

if (df[["image", "chicken_id", "age_verified"]] == "").any().any():
    raise ValueError(
        "Some required metadata fields are blank."
    )

# Each image must have its own metadata row.
if df["image"].duplicated().any():
    duplicates = df.loc[
        df["image"].duplicated(keep=False), "image"
    ].tolist()

    raise ValueError(
        "Duplicate image filenames found in metadata.csv. "
        f"Examples: {duplicates[:10]}"
    )

# The user confirmed every image represents a different chicken.
if df["chicken_id"].duplicated().any():
    duplicates = df.loc[
        df["chicken_id"].duplicated(keep=False),
        ["image", "chicken_id"],
    ]

    print("\nRepeated chicken IDs detected:")
    print(duplicates.head(20).to_string(index=False))

    raise ValueError(
        "Every image must have a unique chicken_id for this "
        "dataset. Correct the IDs before training."
    )

# Only verified labels are accepted.
df["age_verified"] = df["age_verified"].str.lower()

unverified = df["age_verified"] != "yes"

if unverified.any():
    print(
        "Rows excluded because age_verified is not 'yes':",
        int(unverified.sum()),
    )
    df = df.loc[~unverified].copy()

# Check that ages are valid numbers between 1 and 24 months.
df["age_months"] = pd.to_numeric(
    df["age_months"], errors="coerce"
)

invalid_age = (
    df["age_months"].isna()
    | ~df["age_months"].between(MIN_AGE, MAX_AGE)
    | (df["age_months"] % 1 != 0)
)

if invalid_age.any():
    print("\nInvalid age records:")
    print(
        df.loc[invalid_age, ["image", "age_months"]]
        .head(20)
        .to_string(index=False)
    )

    raise ValueError(
        "Age labels must be verified whole months from "
        "1 through 24. Correct these records before training."
    )

df["age_months"] = df["age_months"].astype("float32")

# Check image files and report missing or unreadable files.
missing_files = []
unreadable_files = []

for filename in df["image"].tolist():
    image_path = IMAGE_DIR / str(filename)

    if not image_path.is_file():
        missing_files.append(str(filename))
        continue

    try:
        with Image.open(image_path) as image:
            image.verify()
    except (OSError, ValueError, UnidentifiedImageError):
        unreadable_files.append(str(filename))

print("Missing image files:", len(missing_files))
print("Unreadable image files:", len(unreadable_files))

if missing_files:
    print("\nExamples of missing images:")
    for filename in missing_files[:20]:
        print(" -", filename)

if unreadable_files:
    print("\nExamples of unreadable images:")
    for filename in unreadable_files[:20]:
        print(" -", filename)

if missing_files or unreadable_files:
    raise ValueError(
        "Some metadata images are missing or unreadable. "
        "Fix the filenames or image files before training."
    )

if len(df) < 10:
    raise ValueError(
        f"Only {len(df)} valid images remain. "
        "At least 10 are required for this training script."
    )

if df["chicken_id"].nunique() < 2:
    raise ValueError(
        "At least two different chickens are required."
    )

df = df.reset_index(drop=True)

print("\nValid verified images:", len(df))
print("Unique chickens:", df["chicken_id"].nunique())
print("Age range:", int(df["age_months"].min()),
      "to", int(df["age_months"].max()), "months")

print("\nImage counts by age:")
print(
    df["age_months"]
    .value_counts()
    .sort_index()
    .to_string()
)


# ============================================================
# 3. SPLIT BY CHICKEN ID
# ============================================================

# This prevents a chicken from appearing in both sets.
splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=TEST_SIZE,
    random_state=SEED,
)

train_indices, test_indices = next(
    splitter.split(df, groups=df["chicken_id"])
)

train_df = df.iloc[train_indices].reset_index(drop=True)
test_df = df.iloc[test_indices].reset_index(drop=True)

train_ids = set(train_df["chicken_id"])
test_ids = set(test_df["chicken_id"])

if train_ids.intersection(test_ids):
    raise RuntimeError(
        "Data leakage detected: a chicken appears in both sets."
    )

print("\n" + "=" * 60)
print("DATASET SPLIT")
print("=" * 60)

print("Training images:", len(train_df))
print("Testing images:", len(test_df))
print("Training chickens:", train_df["chicken_id"].nunique())
print("Testing chickens:", test_df["chicken_id"].nunique())

if train_df["age_months"].nunique() < 2:
    raise ValueError(
        "Training data must contain at least two different ages."
    )


# ============================================================
# 4. IMAGE PREPROCESSING
# ============================================================

train_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.ColorJitter(
        brightness=0.1,
        contrast=0.1,
    ),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

eval_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])


# ============================================================
# 5. DATASET CLASS
# ============================================================

class SpurDataset(Dataset):
    def __init__(self, frame, transform):
        self.frame = frame
        self.transform = transform

    def __len__(self):
        return len(self.frame)

    def __getitem__(self, index):
        row = self.frame.iloc[index]
        image_path = IMAGE_DIR / str(row["image"])

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image = self.transform(image)

        age = torch.tensor(
            float(row["age_months"]),
            dtype=torch.float32,
        )

        return image, age


train_loader = DataLoader(
    SpurDataset(train_df, train_transform),
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0,
)

test_loader = DataLoader(
    SpurDataset(test_df, eval_transform),
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0,
)


# ============================================================
# 6. BUILD THE RESNET-18 REGRESSION MODEL
# ============================================================

print("\nLoading pretrained ResNet-18...")

# The pretrained weights may need to download the first time.
weights = ResNet18_Weights.DEFAULT
model = models.resnet18(weights=weights)

# Predict one continuous value: age in months.
model.fc = nn.Linear(model.fc.in_features, 1)

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

model = model.to(device)

# Freeze the pretrained feature extractor.
# Only the final regression layer will be trained.
for parameter in model.parameters():
    parameter.requires_grad = False

for parameter in model.fc.parameters():
    parameter.requires_grad = True

criterion = nn.L1Loss()

optimizer = torch.optim.Adam(
    model.fc.parameters(),
    lr=0.001,
)

print("Device:", device)
print("Training images:", len(train_df))
print("Training epochs:", EPOCHS)
print("\nTraining model...")


# ============================================================
# 7. TRAINING LOOP
# ============================================================

for epoch in range(EPOCHS):
    model.train()
    total_absolute_error = 0.0

    for images, ages in train_loader:
        images = images.to(device)
        ages = ages.to(device).view(-1, 1)

        optimizer.zero_grad()

        predictions = model(images)
        loss = criterion(predictions, ages)

        loss.backward()
        optimizer.step()

        total_absolute_error += (
            torch.abs(predictions.detach() - ages)
            .sum()
            .item()
        )

    train_mae = total_absolute_error / len(train_df)

    print(
        f"Epoch {epoch + 1}/{EPOCHS} - "
        f"training MAE: {train_mae:.2f} months"
    )


# ============================================================
# 8. EVALUATE ON UNSEEN CHICKENS
# ============================================================

model.eval()

actual_ages = []
predicted_ages = []

with torch.no_grad():
    for images, ages in test_loader:
        images = images.to(device)

        predictions = model(images).flatten()

        # Limit predictions to the supported 1–24 month range.
        predictions = predictions.clamp(MIN_AGE, MAX_AGE)

        predicted_ages.extend(
            predictions.cpu().tolist()
        )
        actual_ages.extend(
            ages.tolist()
        )

if not actual_ages:
    raise RuntimeError("No test predictions were produced.")

actual = np.asarray(actual_ages, dtype=np.float32)
predicted = np.asarray(predicted_ages, dtype=np.float32)

absolute_errors = np.abs(predicted - actual)

test_mae = float(np.mean(absolute_errors))
test_median_error = float(np.median(absolute_errors))
within_one_month = float(
    np.mean(absolute_errors <= 1.0) * 100
)
within_three_months = float(
    np.mean(absolute_errors <= 3.0) * 100
)

print("\n" + "=" * 60)
print("TEST RESULTS")
print("=" * 60)

print(f"Test MAE: {test_mae:.2f} months")
print(f"Median absolute error: {test_median_error:.2f} months")
print(
    f"Predictions within 1 month: {within_one_month:.1f}%"
)
print(
    f"Predictions within 3 months: {within_three_months:.1f}%"
)

# Show errors for age groups represented in the test set.
test_results = pd.DataFrame({
    "actual_age": actual,
    "predicted_age": predicted,
    "absolute_error": absolute_errors,
})

age_groups = [
    (1, 6, "1–6 months"),
    (7, 12, "7–12 months"),
    (13, 18, "13–18 months"),
    (19, 24, "19–24 months"),
]

print("\nMAE by actual age group:")

for lower, upper, label in age_groups:
    group = test_results[
        test_results["actual_age"].between(lower, upper)
    ]

    if len(group) == 0:
        print(f"{label}: no test examples")
    else:
        group_mae = group["absolute_error"].mean()

        print(
            f"{label}: MAE = {group_mae:.2f} months "
            f"({len(group)} test images)"
        )

print(
    "\nEvaluation is preliminary; validate on independent "
    "chickens before deploying the model."
)


# ============================================================
# 9. SAVE THE TRAINED MODEL
# ============================================================

MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Save on CPU so the checkpoint can also be loaded on a CPU-only
# computer or server.
model = model.cpu()

checkpoint = {
    "model_state_dict": model.state_dict(),
    "architecture": "resnet18",
    "age_min": MIN_AGE,
    "age_max": MAX_AGE,
    "image_size": IMAGE_SIZE,
    "normalization_mean": [0.485, 0.456, 0.406],
    "normalization_std": [0.229, 0.224, 0.225],
    "test_mae_months": test_mae,
    "training_images": len(train_df),
    "testing_images": len(test_df),
    "seed": SEED,
}

torch.save(checkpoint, MODEL_PATH)

print("\n" + "=" * 60)
print("TRAINING COMPLETE")
print("=" * 60)
print("Saved model to:", MODEL_PATH)
