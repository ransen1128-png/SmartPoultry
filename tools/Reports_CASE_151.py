"""Reports browser test CASE-151."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["151", *sys.argv[1:]]))

from tools.reports_browser import ReportsBrowserCase


class ReportsCase151(ReportsBrowserCase):
    def test_case_151_reports(self):
        self.assertTrue(self.apply_expense_filter(self.branch.name).ok)
        self.assert_expense_total(2358)
        with self.page.expect_download() as download:
            self.page.get_by_role('link', name='Export CSV', exact=True).click()
        self.assertEqual(download.value.suggested_filename, 'branch-expenses.csv')
