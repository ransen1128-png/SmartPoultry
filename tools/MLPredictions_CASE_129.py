"""ML Predictions browser test CASE-129."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["129", *sys.argv[1:]]))

from tools.automation_browser import expect

import re

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase129(MLPredictionsBrowserCase):
    def test_case_129_november_recorded_profit_is_a_5026_loss(self):
        row = self.november_actual_row('Profit')
        expect(row).to_have_count(1)
        expect(row.get_by_role('cell').nth(2)).to_have_text(re.compile(r'^-5,?026\.00 PHP$'))
        expect(row.get_by_role('cell').nth(3)).to_have_text('Recorded revenue minus recorded expenses')
