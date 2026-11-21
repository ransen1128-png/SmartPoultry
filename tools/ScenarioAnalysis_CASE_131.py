"""Scenario Analysis browser test CASE-131."""

import re

from playwright.sync_api import expect

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase131(ScenarioAnalysisBrowserCase):
    def test_case_131_scenario_analysis(self):
        self.apply_change('')
        expect(self.page.get_by_text(re.compile(r'(enter|provide|required).*percent|percent.*required', re.I))).to_be_visible()
