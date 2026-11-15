"""Hosted age inference must reuse one model across concurrent requests."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


class AgeRuntimeConcurrencyTests(TestCase):
    def test_concurrent_first_predictions_load_one_checkpoint_and_match(self):
        from core import rooster_age_classifier as age
        from core.age_model_registry import candidate_entry
        variant='finetuned' if candidate_entry() else 'original'
        content=(Path(__file__).resolve().parents[2]/'spurs images/4months.jpg').read_bytes()
        age._load_ready_model.cache_clear()
        try:
            with patch.object(age.models,'resnet18',wraps=age.models.resnet18) as constructor:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    predictions=list(pool.map(lambda _:age.predict_rooster_age(BytesIO(content),variant),range(2)))
                self.assertEqual(constructor.call_count,1)
            self.assertIsNotNone(predictions[0])
            self.assertEqual(predictions[0],predictions[1])
        finally:age._load_ready_model.cache_clear()
