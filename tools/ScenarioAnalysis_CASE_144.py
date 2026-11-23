"""Scenario Analysis browser test CASE-144."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["144", *sys.argv[1:]]))

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase144(ScenarioAnalysisBrowserCase):
    def test_case_144_scenario_analysis(self):
        self.apply_change('10%', 'mortality_increase')
        self.assert_results(revenue='\u20b1320.38', expenses='\u20b15,422.30', profit='-\u20b15,101.92')
