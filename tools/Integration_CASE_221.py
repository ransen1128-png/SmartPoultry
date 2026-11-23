"""SmartPoultry integration INT-037 (CASE-221)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['221', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.rooster_age_browser import RoosterAgeBrowserCase
from core.models import RoosterAgeEstimate
import os
from pathlib import Path


class IntegrationCase221(RoosterAgeBrowserCase):
    def test_int_037(self):
        configured = os.environ.get('SMARTPOULTRY_INTEGRATION_ROOSTER_PHOTO')
        if not configured:
            self.skipTest('Set SMARTPOULTRY_INTEGRATION_ROOSTER_PHOTO and configure the local estimator models.')
        photo = Path(configured).expanduser().resolve(strict=True)
        for mode in ('age_only', 'full'):
            with self.subTest(mode=mode):
                self.open_estimator()
                self.page.locator('#photos').element_handle().send_keys(str(photo))
                combined = self.page.locator('#useSpurApi')
                if combined.is_visible():
                    combined.uncheck()
                self.page.locator(f'form.estimator-workspace button[value="{mode}"]').click()
                expect(self.page.locator('.rooster-age-estimate')).to_be_visible(timeout=120000)
                estimate = RoosterAgeEstimate.objects.filter(user=self.user).latest('pk')
                self.assertEqual(estimate.analysis.get('analysis_mode'), mode)
                self.assertEqual(estimate.analysis.get('age_prediction_status'), 'experimental')
                if mode == 'full':
                    self.assertIn('anatomy', estimate.analysis)
                self.open_saved_estimate(estimate)
