"""Reports browser test CASE-139."""

import re

from playwright.sync_api import expect

from tools.reports_browser import ReportsBrowserCase


class ReportsCase139(ReportsBrowserCase):
    def test_case_139_reports(self):
        self.assertTrue(self.apply_expense_filter(self.branch.name).ok)
        expect(self.page.get_by_role('heading', name='Feed delivered by flock')).to_be_visible()
        row = self.page.locator('#feedUsageBody tr').filter(
            has=self.page.get_by_role('cell', name=self.branch.name, exact=True),
        )
        expect(row).to_have_count(1)
        cells = row.get_by_role('cell')
        expect(cells.nth(1)).to_contain_text('flock not recorded')
        expect(cells.nth(2)).to_have_text(re.compile(r'^50(?:\.0+)? kg$'))
        expect(cells.nth(3)).to_have_text('\u20b12000.00')
        expect(cells.nth(5)).to_have_text('Not available')
