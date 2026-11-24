"""ML Predictions browser test CASE-128."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["128", *sys.argv[1:]]))

from math import isfinite

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase128(MLPredictionsBrowserCase):
    def test_case_128_egg_chart_shows_actual_and_forecast_series(self):
        chart = self.plotted_data('productionForecastChart')
        self.assertEqual(set(chart['series']), {'Actual Eggs', 'Forecast Eggs'})
        actual = chart['series']['Actual Eggs']
        forecast = chart['series']['Forecast Eggs']
        # Six past weeks, then the next six; forecasts are not drawn over past weeks.
        self.assertEqual(len(chart['labels']), 12)
        self.assertEqual(len(set(chart['labels'])), 12)
        self.assertEqual((len(actual), len(forecast)), (12, 12))
        self.assertEqual(sum(actual[:6]), 14)
        self.assertEqual((actual[6:], forecast[:6]), ([None] * 6, [None] * 6))
        self.assertTrue(all(isfinite(value) for value in forecast[6:]))
