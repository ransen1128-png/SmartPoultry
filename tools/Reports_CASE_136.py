"""Reports browser test CASE-136."""

from tools.reports_browser import ReportsBrowserCase


class ReportsCase136(ReportsBrowserCase):
    def test_case_136_reports(self):
        response = self.apply_expense_filter(self.branch.name)
        self.assertTrue(response.ok)
        self.assert_expense_total(2358)
