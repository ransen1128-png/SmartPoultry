"""Rooster Age Estimator browser test CASE-120."""

from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase120(RoosterAgeBrowserCase):
    def test_case_120_quick_estimate_requires_photo(self):
        self.submit_without_photo('age_only')
