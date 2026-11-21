"""ML Predictions browser test CASE-116."""

from math import isfinite

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase116(MLPredictionsBrowserCase):
    def test_case_116_profit_chart_shows_six_months(self):
        chart = self.plotted_data('profitPredictionChart')
        self.assertEqual(chart['labels'], self.forecast_months)
        predictions = chart['series']['Predicted Profit (PHP)']
        self.assertEqual(len(predictions), 6)
        self.assertTrue(all(isfinite(value) for value in predictions))
