"""Reports browser test CASE-147."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["147", *sys.argv[1:]]))

from tools.reports_browser import ReportsBrowserCase


class ReportsCase147(ReportsBrowserCase):
    def test_case_147_reports(self):
        response = self.apply_expense_filter(self.branch.name)
        self.assertTrue(response.ok)
        self.assert_expense_total(2358)
