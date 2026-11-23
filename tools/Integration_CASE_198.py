"""SmartPoultry integration INT-014 (CASE-198)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['198', *sys.argv[1:]]))

from tools.ml_predictions_browser import MLPredictionsBrowserCase
import MLPredictions_CASE_126 as workflow_1
import MLPredictions_CASE_129 as workflow_2
import MLPredictions_CASE_130 as workflow_3


class IntegrationCase198(MLPredictionsBrowserCase):
    def test_int_014(self):
        workflow_1.MLPredictionsCase126.test_case_126_november_revenue_and_following_month_forecasts(self)
        workflow_2.MLPredictionsCase129.test_case_129_november_recorded_profit_is_a_5026_loss(self)
        workflow_3.MLPredictionsCase130.test_case_130_november_recorded_egg_production_is_fourteen(self)
