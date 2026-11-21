"""Reports browser test CASE-137."""

from playwright.sync_api import expect

from tools.reports_browser import ReportsBrowserCase


class ReportsCase137(ReportsBrowserCase):
    def test_case_137_reports(self):
        response = self.apply_expense_filter('Unassigned farm costs')
        self.assertTrue(response.ok)
        self.assert_expense_total(3000)
        row = self.page.locator('#branchExpensesBody tr').filter(
            has=self.page.get_by_role('cell', name='Unassigned inventory / farm costs', exact=True),
        )
        expect(row.get_by_role('cell', name='feed', exact=True)).to_be_visible()
