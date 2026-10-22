from pathlib import Path
import csv
import re

folder = Path("spur_age/dataset/images")
output = Path("spur_age/dataset/metadata.csv")
output.parent.mkdir(parents=True, exist_ok=True)

rows = []

for image in sorted(folder.iterdir()):
    if not image.is_file() or image.suffix.lower() not in {
        ".jpg", ".jpeg", ".png", ".webp"
    }:
        continue

    name = image.stem.lower()
    age = ""
    notes = ""

    # Exact month, including filenames such as 2monthss.jpg
    match = re.fullmatch(r"(\d+)months*", name)
    if match:
        age = int(match.group(1))
        if not 1 <= age <= 24:
            raise ValueError(f"Age outside 1-24 months: {image.name}")
        notes = "Month parsed from filename; verify against records."
    else:
        notes = "Age range or unrecognized name; exact age needed."

    rows.append({
        "image": image.name,
        "age_months": age,
        "chicken_id": "",
        "age_verified": "no",
        "notes": notes,
    })

with output.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["image", "age_months", "chicken_id", "age_verified", "notes"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"Found {len(rows)} images.")
print(f"Created: {output}")
print("Review the ages and fill chicken_id before training.")
