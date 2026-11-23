"""Scenario Analysis browser test CASE-141."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["141", *sys.argv[1:]]))

import re

from playwright.sync_api import expect

from tools.scenario_analysis_browser import ScenarioAnalysisBrowserCase


class ScenarioAnalysisCase141(ScenarioAnalysisBrowserCase):
    def test_case_141_scenario_analysis(self):
        self.apply_change('abc')
        expect(self.page.get_by_text(re.compile(r'(numeric|valid number).*percent|percent.*(numeric|number)', re.I))).to_be_visible()
