"""Rooster Age Estimator browser test CASE-123."""

from playwright.sync_api import expect

from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase123(RoosterAgeBrowserCase):
    def test_case_123_view_selected_saved_analysis(self):
        selected = self.saved_estimate()
        self.saved_estimate(age_display='Experimental estimate: 11.0 months')
        card = self.open_saved_estimate(selected)
        expect(card.locator('.rooster-age-estimate')).to_have_text(self.age_display)
