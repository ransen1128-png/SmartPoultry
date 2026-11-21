"""Scenario Analysis browser test CASE-132."""

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase132(ScenarioAnalysisBrowserCase):
    def test_case_132_scenario_analysis(self):
        self.apply_change('10%')
        self.assert_results(revenue='\u20b1332.00', expenses='\u20b15,858.00', profit='-\u20b15,526.00')
