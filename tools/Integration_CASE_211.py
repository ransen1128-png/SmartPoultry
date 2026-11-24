"""SmartPoultry integration INT-027 (CASE-211)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['211', *sys.argv[1:]]))

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase
from tools.automation_browser import expect


class IntegrationCase211(ScenarioAnalysisBrowserCase):
    def test_int_027(self):
        self.apply_change('10%', scenario='egg_price_increase')
        # Only egg revenue (4 eggs x PHP 8 = PHP 32) rises by 10%; meat revenue (PHP 300) is unchanged.
        expect(self.panel.locator('[data-result="revenue"]')).to_have_text('\u20b1335.20')
