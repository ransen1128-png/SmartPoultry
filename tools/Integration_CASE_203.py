"""SmartPoultry integration INT-019 (CASE-203)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['203', *sys.argv[1:]]))

from tools.reports_browser import ReportsBrowserCase
import Reports_CASE_151 as workflow_1


class IntegrationCase203(ReportsBrowserCase):
    def test_int_019(self):
        workflow_1.ReportsCase151.test_case_151_reports(self)
