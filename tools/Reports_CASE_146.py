"""Reports browser test CASE-146."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["146", *sys.argv[1:]]))

from tools.automation_browser import expect

import re


from tools.reports_browser import ReportsBrowserCase


class ReportsCase146(ReportsBrowserCase):
    def test_case_146_reports(self):
        self.fill_expense_filter(self.branch.name, start='2026-11-21', end='2026-11-01')
        self.page.get_by_role('button', name='Apply Filter', exact=True).click()
        message = self.page.locator('#branchReportError')
        expect(message).to_be_visible()
        export = self.page.locator('#branchExpensesCsv')
        expect(export).not_to_have_attribute('href', re.compile(r'.+'))
        expect(export).to_have_attribute('aria-disabled', 'true')
        expect(message).to_contain_text('End date must be on or after start date')
