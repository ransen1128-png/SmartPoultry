
import csv
import re
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
IMAGE_DIR = PROJECT / "spur_age" / "dataset" / "images"
CSV_PATH = PROJECT / "spur_age" / "dataset" / "metadata.csv"
BACKUP_PATH = CSV_PATH.with_name("metadata_backup.csv")

REQUIRED_COLUMNS = [
    "image",
    "age_months",
    "chicken_id",
    "age_verified",
    "notes",
]

if not IMAGE_DIR.is_dir():
    raise FileNotFoundError(f"Image folder not found: {IMAGE_DIR}")

if not CSV_PATH.is_file():
    raise FileNotFoundError(f"Metadata CSV not found: {CSV_PATH}")

with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    if not reader.fieldnames or not all(
        column in reader.fieldnames for column in REQUIRED_COLUMNS
    ):
        raise ValueError(
            f"metadata.csv must contain these columns: {REQUIRED_COLUMNS}"
        )

    fieldnames = reader.fieldnames
    rows = list(reader)

existing_images = {
    row["image"].strip().lower()
    for row in rows
    if row.get("image", "").strip()
}

# Back up the original metadata before making changes.
if not BACKUP_PATH.exists():
    shutil.copy2(CSV_PATH, BACKUP_PATH)

added = []

for image_path in sorted(IMAGE_DIR.iterdir()):
    if not image_path.is_file():
        continue

    if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        continue

    filename = image_path.name

    if filename.lower() in existing_images:
        continue

    match = re.match(r"^(\d+)", image_path.stem)
    if not match:
        print(f"SKIPPED (age not found in filename): {filename}")
        continue

    age = int(match.group(1))

    if not 1 <= age <= 24:
        print(f"SKIPPED (age outside 1-24 months): {filename}")
        continue

    # Each newly added image represents a different chicken.
    chicken_id = f"new_{image_path.stem}_{image_path.suffix[1:].lower()}"

    added.append({
        "image": filename,
        "age_months": age,
        "chicken_id": chicken_id,
        "age_verified": "yes",
        "notes": "Age confirmed; new chicken",
    })

if added:
    rows.extend(added)

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

print(f"Existing metadata rows: {len(rows) - len(added)}")
print(f"New rows added: {len(added)}")
print(f"Total metadata rows: {len(rows)}")
print(f"Backup saved to: {BACKUP_PATH}")

if added:
    print("\nAdded images:")
    for row in added:
        print(
            f'{row["image"]} | Age: {row["age_months"]} months '
            f'| ID: {row["chicken_id"]}'
        )
else:
    print("No new images needed to be added.")
