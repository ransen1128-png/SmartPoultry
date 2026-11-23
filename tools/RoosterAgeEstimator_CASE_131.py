"""Rooster Age Estimator browser test CASE-131."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["131", *sys.argv[1:]]))

from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase131(RoosterAgeBrowserCase):
    def test_case_131_quick_estimate_requires_photo(self):
        self.submit_without_photo('age_only')
