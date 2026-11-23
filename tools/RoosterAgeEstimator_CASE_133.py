"""Rooster Age Estimator browser test CASE-133."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["133", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase133(RoosterAgeBrowserCase):
    def test_case_133_spur_box_without_outline_is_not_measured(self):
        card = self.open_saved_estimate(self.saved_estimate())
        expect(card.locator('.rooster-age-estimate')).to_have_text(self.age_display)
        expect(card.get_by_text('Spur detected', exact=False).first).to_be_visible()
        expect(card.get_by_text('Spur outline not detected.', exact=False)).to_be_visible()
        expect(card.get_by_text('Not measured', exact=False)).to_contain_text('a detected spur outline is required')
