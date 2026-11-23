"""SmartPoultry integration INT-020 (CASE-204)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['204', *sys.argv[1:]]))

from tools.reports_browser import ReportsBrowserCase
import Reports_CASE_153 as workflow_1


class IntegrationCase204(ReportsBrowserCase):
    def test_int_020(self):
        workflow_1.ReportsCase153.test_case_153_reports(self)
