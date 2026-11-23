"""SmartPoultry integration INT-017 (CASE-201)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['201', *sys.argv[1:]]))

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase
import ScenarioAnalysis_CASE_143 as workflow_1


class IntegrationCase201(ScenarioAnalysisBrowserCase):
    def test_int_017(self):
        workflow_1.ScenarioAnalysisCase143.test_case_143_scenario_analysis(self)
