"""ML Predictions browser test CASE-115."""

from math import isfinite

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase115(MLPredictionsBrowserCase):
    def test_case_115_november_revenue_and_following_month_forecasts(self):
        chart = self.plotted_data('predictionChart')
        november = chart['labels'].index('Nov 2026')
        actual = chart['series']['Actual Revenue']
        forecast = chart['series']['Predicted Revenue']
        self.assertEqual(actual[november], 332)
        self.assertIsNone(forecast[november])
        self.assertEqual(chart['labels'][november + 1:], self.forecast_months)
        self.assertTrue(all(value is None for value in actual[november + 1:]))
        self.assertTrue(all(isfinite(value) for value in forecast[november + 1:]))
