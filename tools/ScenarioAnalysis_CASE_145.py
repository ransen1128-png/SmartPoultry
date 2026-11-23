"""Scenario Analysis browser test CASE-145."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["145", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase145(ScenarioAnalysisBrowserCase):
    def test_case_145_scenario_analysis(self):
        for label, loss in (('Nov 2026', '5026.00'), ('Predicted December 2026', '1675.33')):
            row = self.page.get_by_role('row').filter(has=self.page.get_by_role('cell', name=label, exact=True))
            cell = row.get_by_role('cell').nth(3)
            expect(cell).to_be_visible()
            self.assertEqual(cell.inner_text().replace(',', ''), f'\u20b1-{loss}')
