"""Rooster Age Estimator browser test CASE-134."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["134", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase134(RoosterAgeBrowserCase):
    def test_case_134_view_selected_saved_analysis(self):
        selected = self.saved_estimate()
        self.saved_estimate(age_display='Experimental estimate: 11.0 months')
        card = self.open_saved_estimate(selected)
        expect(card.locator('.rooster-age-estimate')).to_have_text(self.age_display)
