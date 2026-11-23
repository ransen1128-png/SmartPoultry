"""Scenario Analysis browser test CASE-142."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["142", *sys.argv[1:]]))

import re

from playwright.sync_api import expect

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase142(ScenarioAnalysisBrowserCase):
    def test_case_142_scenario_analysis(self):
        self.apply_change('')
        expect(self.page.get_by_text(re.compile(r'(enter|provide|required).*percent|percent.*required', re.I))).to_be_visible()
