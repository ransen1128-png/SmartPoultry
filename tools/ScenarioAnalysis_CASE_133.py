"""Scenario Analysis browser test CASE-133."""

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase133(ScenarioAnalysisBrowserCase):
    def test_case_133_scenario_analysis(self):
        self.apply_change('10%', 'mortality_increase')
        self.assert_results(revenue='\u20b1320.38', expenses='\u20b15,422.30', profit='-\u20b15,101.92')
