"""Scenario Analysis browser test CASE-143."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["143", *sys.argv[1:]]))

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase143(ScenarioAnalysisBrowserCase):
    def test_case_143_scenario_analysis(self):
        self.apply_change('10%')
        self.assert_results(revenue='\u20b1332.00', expenses='\u20b15,858.00', profit='-\u20b15,526.00')
