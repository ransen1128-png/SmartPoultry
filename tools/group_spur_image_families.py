"""Conservative grouping from actual pixels, not filenames or age labels.

Family identifiers are technical split groups, NOT invented chicken identities.
User confirmed the existing age labels on 9 November 2026.
"""
import csv
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from scipy.fft import dctn
from skimage.metrics import structural_similarity
from torchvision import models, transforms

from audit_spur_dataset import write_csv

ROOT = Path(__file__).resolve().parents[1]


def main():
    torch.set_num_threads(4)
    audit = ROOT / 'reports/dataset_audit'
    rows = list(csv.DictReader((audit / 'image_inventory.csv').open(encoding='utf-8', newline='')))
    by_hash = {}
    for row in rows:
        if row.get('metadata_rows') == '1' and not row['error']:
            by_hash.setdefault(row['pixel_sha256'], row)
    unique = sorted(by_hash.values(), key=lambda r: r['pixel_sha256'])
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model.fc = torch.nn.Identity()
    model.eval()
    prep = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
                               transforms.Normalize([.485, .456, .406], [.229, .224, .225])])
    grays, hashes, features = [], [], []
    with torch.inference_mode():
        for row in unique:
            with Image.open(row['path']) as image:
                rgb = ImageOps.exif_transpose(image).convert('RGB')
                grays.append(np.array(rgb.convert('L').resize((64, 64)), dtype=np.float32))
                dct = dctn(np.array(rgb.convert('L').resize((32, 32)), dtype=float), norm='ortho')[:8, :8]
                hashes.append((dct > np.median(dct.flatten()[1:])).flatten())
                features.append(model(prep(rgb).unsqueeze(0)).flatten().numpy())
    features = np.stack(features)
    features /= np.linalg.norm(features, axis=1, keepdims=True)
    cosine = features @ features.T
    parents = list(range(len(unique)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    pairs, edges = [], []
    for i in range(len(unique)):
        for j in range(i):
            distance = int(np.count_nonzero(hashes[i] != hashes[j]))
            sim = structural_similarity(grays[i], grays[j], data_range=255)
            flip_sim = structural_similarity(grays[i], np.fliplr(grays[j]), data_range=255)
            similarity = float(max(sim, flip_sim))
            # Deliberately conservative: appearance-similar birds may be merged.
            match = (similarity >= .90 or (distance <= 10 and similarity >= .65)
                     or float(cosine[i, j]) >= .94)
            if match:
                parents[find(i)] = find(j)
                edges.append((i, j))
            if match or cosine[i, j] >= .85 or distance <= 16:
                pairs.append({'image_a': unique[i]['path'], 'image_b': unique[j]['path'],
                              'hash_a': unique[i]['pixel_sha256'], 'hash_b': unique[j]['pixel_sha256'],
                              'phash_hamming': distance, 'ssim_max_with_flip': similarity,
                              'imagenet_feature_cosine': float(cosine[i, j]), 'grouped': match})
    # Human-reviewed unions can only make groups more conservative, never split
    # algorithmic matches. Input uses pixel hashes, never filename/age rules.
    reviewed = audit / 'reviewed_family_unions.csv'
    by_pixel = {r['pixel_sha256']: i for i, r in enumerate(unique)}
    manual_count = 0
    if reviewed.is_file():
        for row in csv.DictReader(reviewed.open(encoding='utf-8', newline='')):
            i, j = by_pixel[row['hash_a']], by_pixel[row['hash_b']]
            if not row.get('reason', '').strip():
                raise ValueError('Human family union needs a review reason')
            parents[find(i)] = find(j)
            manual_count += 1
    names = {}
    manifest = []
    for i, row in enumerate(unique):
        family = names.setdefault(find(i), f'visual_family_{len(names) + 1:03}')
        manifest.append({
            'image': row['path'], 'sha256': row['sha256'], 'pixel_sha256': row['pixel_sha256'],
            'age_months': row['age_months'], 'recorded_chicken_id': row['chicken_id'],
            'chicken_id': row['chicken_id'], 'identity_verified': 'unresolved',
            'age_verified': 'yes', 'record_reference': 'User explicitly confirmed existing ages on 2026-11-09',
            'source_family': family, 'content_type': 'mixed_unlocalized',
        })
    write_csv(audit / 'visual_family_manifest.csv', manifest)
    write_csv(audit / 'near_duplicate_pairs.csv', sorted(pairs, key=lambda r: r['imagenet_feature_cosine'], reverse=True))
    write_csv(audit / 'visual_family_members.csv', manifest)
    stats = {'distinct_photographs': len(unique), 'conservative_visual_families': len(names),
             'automatically_grouped_pairs': len(edges), 'human_reviewed_unions': manual_count,
             'actual_independent_chicken_count': None,
             'identity_limit': 'Visual families are split groups, not verified bird identities; viewpoint changes may hide identity.',
             'age_verification': 'Existing labels preserved as user-confirmed; never inferred from filenames.',
             'thresholds': {'ssim_max_with_flip': .90, 'phash_hamming_max': 10,
                            'ssim_with_phash_min': .65, 'imagenet_feature_cosine': .94},
             'features': 'Frozen ImageNet ResNet-18, independent of age labels; original age checkpoint not used.',
             'members_by_family': {name: sum(r['source_family'] == name for r in manifest) for name in names.values()}}
    (audit / 'visual_family_summary.json').write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
