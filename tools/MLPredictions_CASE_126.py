"""ML Predictions browser test CASE-126."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["126", *sys.argv[1:]]))

from math import isfinite

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase126(MLPredictionsBrowserCase):
    def test_case_126_november_revenue_and_following_month_forecasts(self):
        chart = self.plotted_data('predictionChart')
        november = chart['labels'].index('Nov 2026')
        actual = chart['series']['Actual Revenue']
        forecast = chart['series']['Predicted Revenue']
        self.assertEqual(actual[november], 332)
        self.assertIsNone(forecast[november])
        self.assertEqual(chart['labels'][november + 1:], self.forecast_months)
        self.assertTrue(all(value is None for value in actual[november + 1:]))
        self.assertTrue(all(isfinite(value) for value in forecast[november + 1:]))
