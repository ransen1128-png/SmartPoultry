"""SmartPoultry integration INT-018 (CASE-202)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['202', *sys.argv[1:]]))

from tools.reports_browser import ReportsBrowserCase
import Reports_CASE_147 as workflow_1
import Reports_CASE_150 as workflow_2


class IntegrationCase202(ReportsBrowserCase):
    def test_int_018(self):
        workflow_1.ReportsCase147.test_case_147_reports(self)
        workflow_2.ReportsCase150.test_case_150_reports(self)
