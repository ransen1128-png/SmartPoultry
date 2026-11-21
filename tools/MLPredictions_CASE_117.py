"""ML Predictions browser test CASE-117."""

from math import isfinite

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase117(MLPredictionsBrowserCase):
    def test_case_117_egg_chart_shows_actual_and_forecast_series(self):
        chart = self.plotted_data('productionForecastChart')
        self.assertEqual(set(chart['series']), {'Actual Eggs', 'Forecast Eggs'})
        actual = chart['series']['Actual Eggs']
        forecast = chart['series']['Forecast Eggs']
        self.assertEqual(len(actual), len(chart['labels']))
        self.assertEqual(sum(actual), 14)
        self.assertEqual(len(forecast), len(chart['labels']))
        self.assertTrue(all(isfinite(value) for value in forecast))
