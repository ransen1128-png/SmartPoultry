"""ML Predictions browser test CASE-127."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["127", *sys.argv[1:]]))

from math import isfinite

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase127(MLPredictionsBrowserCase):
    def test_case_127_profit_chart_shows_six_months(self):
        chart = self.plotted_data('profitPredictionChart')
        self.assertEqual(chart['labels'], self.forecast_months)
        predictions = chart['series']['Predicted Profit (PHP)']
        self.assertEqual(len(predictions), 6)
        self.assertTrue(all(isfinite(value) for value in predictions))
