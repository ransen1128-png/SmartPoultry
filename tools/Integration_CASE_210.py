"""SmartPoultry integration INT-026 (CASE-210)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['210', *sys.argv[1:]]))

from tools.rooster_age_browser import RoosterAgeBrowserCase
import RoosterAgeEstimator_CASE_135 as workflow_1


class IntegrationCase210(RoosterAgeBrowserCase):
    def test_int_026(self):
        workflow_1.RoosterAgeEstimatorCase135.test_case_135_unscaled_measurement_uses_pixels(self)
