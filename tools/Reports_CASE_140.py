"""Reports browser test CASE-140."""

from tools.reports_browser import ReportsBrowserCase


class ReportsCase140(ReportsBrowserCase):
    def test_case_140_reports(self):
        self.assertTrue(self.apply_expense_filter(self.branch.name).ok)
        self.assert_expense_total(2358)
        with self.page.expect_download() as download:
            self.page.get_by_role('link', name='Export expenses CSV').click()
        self.assertEqual(download.value.suggested_filename, 'branch-expenses.csv')
