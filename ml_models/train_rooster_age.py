"""Train and validate a spur-image age-range baseline from labeled folders."""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import balanced_accuracy_score, classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'smartpoultry'))

from core.rooster_age_classifier import (
    AGE_LABELS,
    MIN_BALANCED_ACCURACY,
    MIN_MACRO_F1,
    MODEL_PATH,
    image_features,
)


MIN_IMAGES_PER_CLASS = 200
MIN_BIRDS_PER_CLASS = 50
MIN_VALIDATION_BIRDS_PER_CLASS = 10
SUPPORTED_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp'}
LABEL_KEYS = {
    '13months': AGE_LABELS[0],
    '1to3months': AGE_LABELS[0],
    '46months': AGE_LABELS[1],
    '4to6months': AGE_LABELS[1],
    '712months': AGE_LABELS[2],
    '7to12months': AGE_LABELS[2],
    '1324months': AGE_LABELS[3],
    '13to24months': AGE_LABELS[3],
}


def label_from_name(value):
    return LABEL_KEYS.get(re.sub(r'[^a-z0-9]', '', value.lower()))


def collect_samples(dataset_dir):
    samples = []
    for path in sorted(Path(dataset_dir).rglob('*')):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        relative = path.relative_to(dataset_dir)
        folder_label = label_from_name(relative.parts[0]) if len(relative.parts) > 1 else None
        label = folder_label or label_from_name(path.stem)
        if label not in AGE_LABELS:
            continue

        if folder_label and len(relative.parts) > 2:
            bird_group = relative.parts[1]
        else:
            bird_group = None
        samples.append((path, label, bird_group))
    return samples


def split_by_bird(features, labels, groups):
    all_labels = set(AGE_LABELS)
    for seed in range(200):
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        train_indices, test_indices = next(splitter.split(features, labels, groups))
        train_labels = set(labels[train_indices])
        test_labels = set(labels[test_indices])
        if train_labels == all_labels and test_labels == all_labels:
            test_counts = Counter(labels[test_indices])
            if min(test_counts.values()) >= MIN_VALIDATION_BIRDS_PER_CLASS:
                return train_indices, test_indices
    raise ValueError(
        'Could not create a bird-separated holdout set with at least '
        f'{MIN_VALIDATION_BIRDS_PER_CLASS} validation images per age range. '
        'Add more distinct, age-verified chickens to each class.'
    )


def train(dataset_dir, model_path=MODEL_PATH):
    samples = collect_samples(dataset_dir)
    counts = Counter(label for _, label, _ in samples)
    groups_per_class = defaultdict(set)
    for _, label, group in samples:
        if group is not None:
            groups_per_class[label].add(group)

    print('Labeled image counts:')
    for label in AGE_LABELS:
        print(f'  {label}: {counts[label]} images, {len(groups_per_class[label])} bird groups')

    insufficient = [
        f'{label}: {counts[label]} images/{len(groups_per_class[label])} identified birds'
        for label in AGE_LABELS
        if counts[label] < MIN_IMAGES_PER_CLASS or len(groups_per_class[label]) < MIN_BIRDS_PER_CLASS
    ]
    if insufficient:
        raise ValueError(
            f'Need at least {MIN_IMAGES_PER_CLASS} spur images from {MIN_BIRDS_PER_CLASS} identified '
            'chickens in every age range. Organize images as <age-range>/<bird-id>/<image>. '
            'Insufficient classes: ' + '; '.join(insufficient)
        )

    features = np.stack([image_features(path) for path, _, _ in samples])
    labels = np.asarray([label for _, label, _ in samples])
    groups = np.asarray([group for _, _, group in samples])
    train_indices, test_indices = split_by_bird(features, labels, groups)

    classifier = make_pipeline(
        StandardScaler(),
        SVC(C=10, kernel='rbf', class_weight='balanced'),
    )
    classifier.fit(features[train_indices], labels[train_indices])
    predictions = classifier.predict(features[test_indices])
    balanced_accuracy = float(balanced_accuracy_score(labels[test_indices], predictions))
    macro_f1 = float(f1_score(labels[test_indices], predictions, average='macro', zero_division=0))
    report = classification_report(
        labels[test_indices], predictions, labels=AGE_LABELS, output_dict=True, zero_division=0,
    )

    print(f'Bird-separated holdout balanced accuracy: {balanced_accuracy:.3f}')
    print(f'Bird-separated holdout macro F1: {macro_f1:.3f}')
    print(classification_report(labels[test_indices], predictions, labels=AGE_LABELS, zero_division=0))

    if balanced_accuracy < MIN_BALANCED_ACCURACY or macro_f1 < MIN_MACRO_F1:
        raise ValueError(
            'Validation did not meet promotion thresholds '
            f'(balanced accuracy >= {MIN_BALANCED_ACCURACY:.2f}, macro F1 >= {MIN_MACRO_F1:.2f}). '
            'The candidate was not saved as an active model.'
        )

    classifier.fit(features, labels)
    artifact = {
        'classifier': classifier,
        'labels': AGE_LABELS,
        'validated': True,
        'metrics': {
            'balanced_accuracy': balanced_accuracy,
            'macro_f1': macro_f1,
            'class_report': report,
            'validation_images': len(test_indices),
            'validation_birds': len(set(groups[test_indices])),
        },
    }
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)
    print(f'Validated model saved: {model_path}')
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=Path(__file__).resolve().parents[1] / 'spurs images',
        help='Labeled image root (defaults to the attached spurs images folder).',
    )
    parser.add_argument('--output', type=Path, default=MODEL_PATH, help='Output model path.')
    args = parser.parse_args()

    try:
        train(args.data_dir, args.output)
    except (OSError, ValueError) as error:
        print(f'Training stopped: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())