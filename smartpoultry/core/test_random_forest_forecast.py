from datetime import date
from unittest import TestCase
from .random_forest_forecast import random_forest_forecast,fitted_forecast


class RandomForestForecastTests(TestCase):
    def test_actual_training_is_reproducible_with_chronological_holdout(self):
        data={date(2026,month,1):float(month*100) for month in range(1,7)}
        future=[date(2026,8,1),date(2026,9,1)]
        first=random_forest_forecast('test:revenue',data,date(2026,7,1),future)
        self.assertEqual(first['status'],'trained')
        self.assertEqual(first['validation_month'],'2026-06-01')
        self.assertEqual(first['validation_training_ends'],'2026-05-01')
        self.assertEqual(first['held_out_months'],1)
        self.assertEqual(first['training_samples'],5)
        self.assertIsNotNone(first['validation_mae'])
        fitted_forecast.cache_clear()
        second=random_forest_forecast('test:revenue',data,date(2026,7,1),future)
        self.assertEqual(first['forecasts'],second['forecasts'])

    def test_current_partial_month_cannot_leak_into_training(self):
        data={date(2026,month,1):100 for month in range(1,5)}
        future=[date(2026,6,1)]
        first=random_forest_forecast('test:cutoff',data,date(2026,5,1),future)
        data[date(2026,5,1)]=9999999
        second=random_forest_forecast('test:cutoff',data,date(2026,5,1),future)
        self.assertEqual(first['data_sha256'],second['data_sha256'])
        self.assertEqual(first['forecasts'],second['forecasts'])

    def test_missing_months_are_not_fabricated_as_zero_training_labels(self):
        data={date(2026,1,1):100,date(2026,5,1):200}
        report=random_forest_forecast('test:missing',data,date(2026,7,1),[date(2026,8,1)])
        self.assertEqual(report['observed_months'],2)
        self.assertEqual(report['status'],'insufficient_history')
        self.assertEqual(report['forecasts'],[None])
