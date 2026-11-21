"""Scenario Analysis browser test CASE-130."""

import re

from playwright.sync_api import expect

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase130(ScenarioAnalysisBrowserCase):
    def test_case_130_scenario_analysis(self):
        self.apply_change('abc')
        expect(self.page.get_by_text(re.compile(r'(numeric|valid number).*percent|percent.*(numeric|number)', re.I))).to_be_visible()
