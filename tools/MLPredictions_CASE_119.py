"""ML Predictions browser test CASE-119."""

from playwright.sync_api import expect

from tools.ml_predictions_browser import MLPredictionsBrowserCase


class MLPredictionsCase119(MLPredictionsBrowserCase):
    def test_case_119_november_recorded_egg_production_is_fourteen(self):
        row = self.november_actual_row('Egg Production')
        expect(row).to_have_count(1)
        expect(row.get_by_role('cell').nth(2)).to_have_text('14.00 eggs')
        expect(row.get_by_role('cell').nth(3)).to_have_text('Production records')
