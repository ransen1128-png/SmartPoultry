"""ML Predictions browser test CASE-118."""

import re
from playwright.sync_api import expect

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase118(MLPredictionsBrowserCase):
    def test_case_118_november_recorded_profit_is_a_5026_loss(self):
        row = self.november_actual_row('Profit')
        expect(row).to_have_count(1)
        expect(row.get_by_role('cell').nth(2)).to_have_text(re.compile(r'^-5,?026\.00 PHP$'))
        expect(row.get_by_role('cell').nth(3)).to_have_text('Recorded revenue minus recorded expenses')
