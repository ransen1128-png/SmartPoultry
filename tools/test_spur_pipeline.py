"""Safety/partition tests; these tests never train on synthetic examples."""
import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from audit_spur_dataset import inspect
from train_verified_spur_age import create_splits, group_components, load_review


class AuditTests(unittest.TestCase):
    def test_hashes_prove_copies_without_interpreting_filename_ages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / '1months.png', root / '24months.png'
            Image.new('RGB', (32, 30), (70, 80, 90)).save(first)
            second.write_bytes(first.read_bytes())
            a, b = inspect(first), inspect(second)
            self.assertEqual(a['sha256'], b['sha256'])
            self.assertEqual(a['pixel_sha256'], b['pixel_sha256'])
            self.assertNotIn('age_months', a)
            self.assertFalse(a['error'])

    def test_corrupt_image_is_reported_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.jpg'
            original = b'broken image data'
            path.write_bytes(original)
            self.assertTrue(inspect(path)['error'])
            self.assertEqual(path.read_bytes(), original)


class SplitTests(unittest.TestCase):
    def test_identity_and_source_unions_are_transitive(self):
        rows = [
            {'chicken_id': 'a', 'source_family': 'one', 'pixel_sha256': 'p1'},
            {'chicken_id': 'a', 'source_family': 'two', 'pixel_sha256': 'p2'},
            {'chicken_id': 'b', 'source_family': 'two', 'pixel_sha256': 'p3'},
        ]
        self.assertEqual(len(set(group_components(rows))), 1)

    def test_repeated_birds_never_cross_splits(self):
        rows = [{'chicken_id': f'bird-{i//2}', 'source_family': f'family-{i//2}',
                 'pixel_sha256': f'pixel-{i}'} for i in range(40)]
        first = create_splits(rows, 42)
        self.assertEqual(first, create_splits(rows, 42))
        groups = [{rows[i]['chicken_id'] for i in indices} for indices in first.values()]
        self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
        self.assertEqual(sum(map(len, first.values())), 40)

    def test_actual_family_manifest_does_not_claim_verified_individuals(self):
        root = Path(__file__).resolve().parents[1]
        manifest = root / 'reports/dataset_audit/visual_family_manifest.csv'
        with self.assertRaises(ValueError):
            load_review(manifest)
        rows = load_review(manifest, content_family_experiment=True)
        self.assertEqual(len(rows), 151)
        self.assertTrue(all(r['identity_verified'] == 'unresolved' for r in rows))


if __name__ == '__main__':
    unittest.main()
