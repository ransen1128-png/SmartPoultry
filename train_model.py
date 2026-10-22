
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from sklearn.model_selection import GroupShuffleSplit
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from torchvision.models import ResNet18_Weights

ROOT = Path(__file__).resolve().parent
IMAGE_DIR = ROOT / "spur_age" / "dataset" / "images"
CSV_PATH = ROOT / "spur_age" / "dataset" / "metadata.csv"
MODEL_DIR = ROOT / "spur_age" / "models"
MODEL_PATH = MODEL_DIR / "spur_age_model.pth"

BATCH_SIZE = 4
EPOCHS = 10
SEED = 42

torch.manual_seed(SEED)

# Load and validate metadata
df = pd.read_csv(CSV_PATH)
required = {"image", "age_months", "chicken_id", "age_verified"}
if not required.issubset(df.columns):
    raise ValueError(f"CSV must contain columns: {required}")

df["age_months"] = pd.to_numeric(df["age_months"], errors="coerce")
df = df.dropna(subset=["age_months", "chicken_id"]).copy()
df = df[df["age_months"].between(1, 24)]
df = df[df["age_verified"].astype(str).str.lower() == "yes"]

df = df[
    df["image"].apply(lambda name: (IMAGE_DIR / str(name)).is_file())
].reset_index(drop=True)

if len(df) < 10:
    raise ValueError("Too few valid images to create a training split.")

if df["chicken_id"].nunique() < 2:
    raise ValueError("At least two distinct chicken IDs are needed.")

# Split by chicken ID so a chicken cannot appear in both sets
splitter = GroupShuffleSplit(
    n_splits=1, test_size=0.2, random_state=SEED
)
train_idx, test_idx = next(
    splitter.split(df, groups=df["chicken_id"])
)
train_df = df.iloc[train_idx].reset_index(drop=True)
test_df = df.iloc[test_idx].reset_index(drop=True)

print("Training images:", len(train_df))
print("Testing images:", len(test_df))
print("Training chickens:", train_df["chicken_id"].nunique())
print("Testing chickens:", test_df["chicken_id"].nunique())

# Image preprocessing
train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.1, contrast=0.1),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

eval_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])


class SpurDataset(Dataset):
    def __init__(self, frame, transform):
        self.frame = frame
        self.transform = transform

    def __len__(self):
        return len(self.frame)

    def __getitem__(self, index):
        row = self.frame.iloc[index]
        path = IMAGE_DIR / row["image"]

        with Image.open(path) as image:
            image = image.convert("RGB")
            image = self.transform(image)

        age = torch.tensor(
            [float(row["age_months"])], dtype=torch.float32
        )
        return image, age


train_loader = DataLoader(
    SpurDataset(train_df, train_transform),
    batch_size=BATCH_SIZE,
    shuffle=True,
)
test_loader = DataLoader(
    SpurDataset(test_df, eval_transform),
    batch_size=BATCH_SIZE,
    shuffle=False,
)

# Load pretrained ResNet-18 and replace its final layer for age regression
weights = ResNet18_Weights.DEFAULT
model = models.resnet18(weights=weights)
model.fc = nn.Linear(model.fc.in_features, 1)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)

# Initially train the final regression layer only
for name, parameter in model.named_parameters():
    parameter.requires_grad = name.startswith("fc.")

criterion = nn.L1Loss()
optimizer = torch.optim.Adam(
    filter(lambda p: p.requires_grad, model.parameters()),
    lr=0.001,
)

print("Device:", device)
print("Training model...")

for epoch in range(EPOCHS):
    model.train()
    total_loss = 0.0

    for images, ages in train_loader:
        images = images.to(device)
        ages = ages.to(device)

        optimizer.zero_grad()
        predictions = model(images)
        loss = criterion(predictions, ages)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * len(images)

    average_loss = total_loss / len(train_df)
    print(
        f"Epoch {epoch + 1}/{EPOCHS} - "
        f"training MAE: {average_loss:.2f} months"
    )

# Evaluate on the held-out chickens
model.eval()
absolute_errors = []

with torch.no_grad():
    for images, ages in test_loader:
        images = images.to(device)
        ages = ages.to(device)

        predictions = model(images).clamp(1, 24)
        absolute_errors.extend(
            torch.abs(predictions - ages).cpu().flatten().tolist()
        )

test_mae = sum(absolute_errors) / len(absolute_errors)
print(f"Test MAE: {test_mae:.2f} months")
print("This estimate is preliminary because the dataset is very small.")

# Save model weights and preprocessing details
MODEL_DIR.mkdir(parents=True, exist_ok=True)
torch.save(
    {
        "model_state_dict": model.cpu().state_dict(),
        "architecture": "resnet18",
        "age_min": 1,
        "age_max": 24,
        "image_size": 224,
        "normalization_mean": [0.485, 0.456, 0.406],
        "normalization_std": [0.229, 0.224, 0.225],
    },
    MODEL_PATH,
)

print("Saved model to:", MODEL_PATH)
