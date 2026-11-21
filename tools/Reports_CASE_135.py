"""Reports browser test CASE-135."""

import re

from playwright.sync_api import expect

from tools.reports_browser import ReportsBrowserCase


class ReportsCase135(ReportsBrowserCase):
    def test_case_135_reports(self):
        response = self.apply_expense_filter(
            self.branch.name, start='2026-11-21', end='2026-11-01',
        )
        self.assertEqual(response.status, 400)
        message = self.page.locator('#branchReportError')
        expect(message).to_be_visible()
        export = self.page.locator('#branchExpensesCsv')
        expect(export).not_to_have_attribute('href', re.compile(r'.+'))
        expect(message).to_contain_text('End date must be on or after start date')
