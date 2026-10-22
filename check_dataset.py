
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent
image_dir = root / "spur_age" / "dataset" / "images"
csv_path = root / "spur_age" / "dataset" / "metadata.csv"

print("Checking SmartPoultry dataset...")

if not csv_path.exists():
    print("ERROR: metadata.csv not found!")
    raise SystemExit(1)

df = pd.read_csv(csv_path)

print("Metadata rows:", len(df))
print("Image files:", len(list(image_dir.glob("*"))))
print("Missing images:", sum(
    not (image_dir / str(name)).is_file()
    for name in df["image"]
))
print("Missing ages:", df["age_months"].isna().sum())
print("Unique chicken IDs:", df["chicken_id"].nunique())
print("Verified yes:", (
    df["age_verified"].astype(str).str.lower() == "yes"
).sum())

print("\nDataset check finished.")
