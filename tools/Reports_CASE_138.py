"""Reports browser test CASE-138."""

from playwright.sync_api import expect

from tools.reports_browser import ReportsBrowserCase


class ReportsCase138(ReportsBrowserCase):
    def test_case_138_reports(self):
        self.assertTrue(self.apply_expense_filter(self.branch.name).ok)
        self.assert_expense_total(2358)
        self.assertTrue(self.apply_expense_filter('All branches').ok)
        self.assert_expense_total(5358)
        expect(self.page.locator('#branchExpensesBody').get_by_role(
            'cell', name='Unassigned inventory / farm costs', exact=True,
        )).to_be_visible()
