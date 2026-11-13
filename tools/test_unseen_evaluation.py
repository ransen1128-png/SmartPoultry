"""Verify that evaluation gates reject leakage and unsupported provenance."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from evaluate_unseen_chickens import validate
from audit_spur_dataset import inspect


class UnseenEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.path = self.base/'fixture.png'
        Image.new('RGB', (20, 20), 'red').save(self.path)
        self.row = dict(image=str(self.path), age_months='3', chicken_id='verified-fixture',
                        age_verified='yes', identity_verified='yes', not_in_training_verified='yes',
                        record_reference='Test fixture record; never used for training')

    def test_identical_photo_is_rejected_even_with_another_identity(self):
        _, issues = validate([self.row], [inspect(self.path)], self.base)
        self.assertTrue(any('Identical training-corpus' in reason for issue in issues for reason in issue['reasons']))

    def test_missing_provenance_and_nonfinite_age_are_rejected(self):
        _, issues = validate([{**self.row, 'record_reference':'', 'age_months':'nan'}], [], self.base)
        self.assertEqual(len(issues[0]['reasons']), 2)

    def test_duplicate_evaluation_frames_do_not_count_twice(self):
        _, issues = validate([self.row, {**self.row,'chicken_id':'another-fixture'}], [], self.base)
        self.assertTrue(any('Duplicate within' in reason for issue in issues for reason in issue['reasons']))


if __name__ == '__main__': unittest.main()
