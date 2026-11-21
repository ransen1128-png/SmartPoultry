"""Rooster Age Estimator browser test CASE-121."""

from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase121(RoosterAgeBrowserCase):
    def test_case_121_full_analysis_requires_photo(self):
        message = self.submit_without_photo('full')
        self.assertTrue(
            self.page.locator('#appDialog[open]').is_visible(),
            f'Expected a required-field dialog, but the page displayed an inline alert: {message}',
        )
