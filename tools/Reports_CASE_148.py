"""Reports browser test CASE-148."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["148", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.reports_browser import ReportsBrowserCase


class ReportsCase148(ReportsBrowserCase):
    def test_case_148_reports(self):
        response = self.apply_expense_filter('Unassigned farm costs')
        self.assertTrue(response.ok)
        self.assert_expense_total(3000)
        row = self.page.locator('#branchExpensesBody tr').filter(
            has=self.page.get_by_role('cell', name='Unassigned inventory / farm costs', exact=True),
        )
        expect(row.get_by_role('cell', name='Feed', exact=True)).to_be_visible()
