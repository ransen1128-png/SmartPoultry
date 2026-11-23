"""Rooster Age Estimator browser test CASE-132."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["132", *sys.argv[1:]]))

from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase132(RoosterAgeBrowserCase):
    def test_case_132_full_analysis_requires_photo(self):
        self.submit_without_photo('full')
