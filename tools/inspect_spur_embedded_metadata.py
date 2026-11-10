"""Read embedded metadata and all frames once per distinct original file."""
import csv
import json
from pathlib import Path

from PIL import ExifTags, Image, IptcImagePlugin


def export_metadata(audit):
    with (audit / 'image_inventory.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    unique = {r['sha256']: r for r in rows if not r['error']}
    records = []
    for file_hash, row in unique.items():
        with Image.open(row['path']) as image:
            raw = image.getexif()
            data = {ExifTags.TAGS.get(k, str(k)): str(v) for k, v in raw.items()}
            nested = {}
            for key in (34665, 34853):
                try:
                    tags = raw.get_ifd(key)
                    names = ExifTags.GPSTAGS if key == 34853 else ExifTags.TAGS
                    nested[str(key)] = {names.get(k, str(k)): str(v) for k, v in tags.items()}
                except (KeyError, TypeError, SyntaxError):
                    nested[str(key)] = {'read_error': 'Cannot decode this nested metadata directory'}
            frames = getattr(image, 'n_frames', 1)
            for frame in range(frames):
                image.seek(frame)
                image.load()
            records.append({'sha256': file_hash, 'path': row['path'], 'format': image.format,
                            'frames': frames, 'exif': data, 'nested_exif': nested,
                            'iptc': repr(IptcImagePlugin.getiptcinfo(image)),
                            'image_info': {k: repr(v) for k, v in image.info.items()}})
    (audit / 'embedded_image_metadata.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(f'Embedded metadata and all frames inspected in {len(records)} distinct workspace images.')


if __name__ == '__main__':
    export_metadata(Path(__file__).resolve().parents[1] / 'reports/dataset_audit')
